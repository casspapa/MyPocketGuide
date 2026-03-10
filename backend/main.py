"""
My Pocket Guide — FastAPI Bidi-streaming server.

State is seeded at create_session() per Google's documented pattern.
Reference: https://google.github.io/adk-docs/sessions/state/
"""

import asyncio
import base64
import json
import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from google.adk.agents.live_request_queue import LiveRequestQueue
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from backend.agent import root_agent

APP_NAME = "museum-tour-guide"
app = FastAPI(title="Museum Tour Guide")
@app.on_event("startup")
async def startup_cleanup():
    await _cleanup_stale_sessions(max_age_hours=24)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required")

session_service = DatabaseSessionService(db_url=DATABASE_URL)

async def _cleanup_stale_sessions(max_age_hours: int = 24) -> None:
    """Delete guest sessions and their events older than max_age_hours."""
    try:
        import asyncpg
        raw_url = DATABASE_URL
        if "+asyncpg" in raw_url:
            raw_url = raw_url.replace("postgresql+asyncpg", "postgresql")
        conn = await asyncpg.connect(raw_url)

        # Delete orphaned events first (foreign-key-safe order)
        old_sessions = await conn.fetch(
            "SELECT id FROM sessions WHERE app_name = $1 "
            "AND update_time < NOW() - MAKE_INTERVAL(hours => $2)",
            APP_NAME, max_age_hours,
        )
        session_ids = [r["id"] for r in old_sessions]

        if session_ids:
            deleted_events = await conn.fetchval(
                "DELETE FROM events WHERE app_name = $1 "
                "AND session_id = ANY($2) RETURNING COUNT(*)",
                APP_NAME, session_ids,
            )
            deleted_sessions = await conn.fetchval(
                "DELETE FROM sessions WHERE app_name = $1 "
                "AND id = ANY($2) RETURNING COUNT(*)",
                APP_NAME, session_ids,
            )
            logger.info(
                f"Startup cleanup: deleted {deleted_sessions} sessions, "
                f"{deleted_events} events"
            )
        else:
            logger.info("Startup cleanup: nothing to delete")

        await conn.close()
    except Exception as e:
        logger.warning(f"Session cleanup skipped: {e}")

runner = Runner(
    app_name=APP_NAME,
    agent=root_agent,
    session_service=session_service,
)

RUN_CONFIG = RunConfig(
    streaming_mode=StreamingMode.BIDI,
    response_modalities=["AUDIO"],
    input_audio_transcription=types.AudioTranscriptionConfig(),
    output_audio_transcription=types.AudioTranscriptionConfig(),
    # Context window compression — Google's documented pattern for 128k models.
    # Without this: sessions cap at 15 min (audio) or 2 min (audio+video).
    # With this: unlimited session duration + older conversation gets summarised
    # so the model never runs out of space.
    # Reference: https://google.github.io/adk-docs/streaming/dev-guide/part4/
    context_window_compression=types.ContextWindowCompressionConfig(
        trigger_tokens=100000,      # Start compressing at ~78% of 128k
        sliding_window=types.SlidingWindow(
            target_tokens=80000,    # Compress down to ~62%, keep recent turns
        ),
    ),
)

INITIAL_SESSION_STATE = {
    "visitor_profile": "Not yet collected",
    "current_exhibit": "",
    "current_gallery": "",
}


@app.get("/config")
async def get_config():
    return {
        "recaptcha_site_key": os.getenv("RECAPTCHA_SITE_KEY", ""),
    }


@app.post("/verify-recaptcha")
async def verify_recaptcha(body: dict):
    import httpx
    secret = os.getenv("RECAPTCHA_SECRET_KEY", "")
    token = body.get("token", "")
    if not secret or not token:
        return {"success": True}  # Fail open if not configured
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={"secret": secret, "response": token},
        )
        result = resp.json()
    return {"success": result.get("success", False), "score": result.get("score", 0)}


@app.websocket("/ws/{user_id}/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    session_id: str,
) -> None:
    await websocket.accept()
    logger.info(f"WebSocket connected: user={user_id} session={session_id}")

    session = await session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id,
    )
    if not session:
        session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id,
            state=INITIAL_SESSION_STATE,
        )
        logger.info(f"Session created with initial state: {session_id}")
    else:
        logger.info(f"Session resumed: {session_id}")

    live_request_queue = LiveRequestQueue()
    gemini_ready = asyncio.Event()

    async def upstream_task() -> None:
        try:
            try:
                await asyncio.wait_for(gemini_ready.wait(), timeout=30.0)
            except asyncio.TimeoutError:
                logger.warning(f"Gemini ready timeout for {session_id}, proceeding anyway")

            await websocket.send_text(json.dumps({"type": "ready"}))
            logger.info(f"Sent ready signal: user={user_id} session={session_id}")

            live_request_queue.send_content(
                types.Content(parts=[types.Part(text="[START]")])
            )
            logger.info(f"Sent [START] nudge: user={user_id} session={session_id}")

            while True:
                message = await websocket.receive()

                if "bytes" in message and message["bytes"]:
                    audio_bytes = message["bytes"]
                    blob = types.Blob(
                        mime_type="audio/pcm;rate=16000",
                        data=audio_bytes,
                    )
                    live_request_queue.send_realtime(blob)
                    continue

                raw = message.get("text")
                if not raw:
                    continue

                data = json.loads(raw)
                msg_type = data.get("type")

                if msg_type == "text":
                    content = types.Content(
                        parts=[types.Part(text=data["text"])]
                    )
                    live_request_queue.send_content(content)

                elif msg_type == "image":
                    try:
                        image_bytes = base64.b64decode(data.get("data", ""))
                        blob = types.Blob(
                            mime_type="image/jpeg",
                            data=image_bytes,
                        )
                        live_request_queue.send_realtime(blob)
                        logger.info("Camera frame sent via send_realtime (native vision)")
                    except Exception as e:
                        logger.warning(f"Image send failed: {e}")

                elif msg_type == "close":
                    break

        except WebSocketDisconnect:
            logger.info(f"Client disconnected: {user_id}/{session_id}")
            live_request_queue.close()
        except Exception as e:
            logger.error(f"Upstream error: {e}")
            live_request_queue.close()
            try:
                await websocket.close(code=1011, reason="Internal error")
            except Exception:
                pass

    async def downstream_task() -> None:
        first_event = True
        try:
            async for event in runner.run_live(
                user_id=user_id,
                session_id=session_id,
                live_request_queue=live_request_queue,
                run_config=RUN_CONFIG,
            ):
                if first_event:
                    first_event = False
                    gemini_ready.set()
                    logger.info(f"Gemini Live confirmed ready: {session_id}")

                structured = _extract_structured_event(event)
                if structured:
                    await websocket.send_text(json.dumps(structured))

                await websocket.send_text(
                    event.model_dump_json(exclude_none=True, by_alias=True)
                )

        except WebSocketDisconnect:
            pass
        except Exception as e:
            if "1000" in str(e):
                logger.info(f"Gemini Live session ended cleanly: {session_id}")
            else:
                logger.error(f"Downstream error: {e}")
        finally:
            gemini_ready.set()

    try:
        await asyncio.gather(
            upstream_task(),
            downstream_task(),
            return_exceptions=True,
        )
    finally:
        live_request_queue.close()
        logger.info(f"Session closed: {user_id}/{session_id}")


def _extract_structured_event(event) -> dict | None:
    try:
        if not event.content or not event.content.parts:
            return None
        for part in event.content.parts:
            if not hasattr(part, "function_response") or not part.function_response:
                continue
            response = part.function_response.response
            name = part.function_response.name
            if name == "identify_exhibit" and isinstance(response, dict):
                if response.get("status") == "success":
                    return {
                        "type": "exhibit_identified",
                        "exhibit_id": response.get("exhibit_id"),
                        "exhibit_name": response.get("exhibit_name"),
                        "gallery": response.get("gallery"),
                    }
    except Exception as e:
        logger.debug(f"_extract_structured_event skipped: {e}")
    return None


@app.get("/health")
async def health():
    return {"status": "ok", "agent": root_agent.name}


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")