import asyncio
import logging
import os
import vertexai
from vertexai.preview import rag
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

vertexai.init(
    project=os.getenv("GOOGLE_CLOUD_PROJECT"),
    location=os.getenv("RAG_LOCATION")
)

RAG_CORPUS = os.getenv("RAG_CORPUS")
RELEVANCE_THRESHOLD = 0.05
MAX_RETRIES = 2
RETRY_DELAY = 1.0


async def rag_search(query: str) -> dict:
    """
    Searches the museum exhibit knowledge base for factual information.
    Call this whenever a visitor asks about an exhibit or you need verified facts.

    Args:
        query: Natural language query about an exhibit

    Returns:
        Dictionary with found facts or a not_found indicator
    """
    try:
        def _sync_search():
            return rag.retrieval_query(
                rag_resources=[rag.RagResource(rag_corpus=RAG_CORPUS)],
                text=query,
                rag_retrieval_config=rag.RagRetrievalConfig(top_k=5)
            )

        # Retry once on transient failures (gRPC INTERNAL, UNAVAILABLE, etc.)
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                results = await asyncio.to_thread(_sync_search)
                break  # Success — exit retry loop
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"rag_search attempt {attempt + 1} failed: {e}, retrying in {RETRY_DELAY}s...")
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    raise  # Final attempt — let outer except handle it

        contexts = results.contexts.contexts

        if not contexts:
            return {"found": False, "message": "No exhibit information found", "facts": ""}

        relevant = [c for c in contexts if c.score >= RELEVANCE_THRESHOLD]

        if not relevant:
            return {
                "found": False,
                "message": "No relevant exhibit found",
                "facts": "",
                "best_score": round(contexts[0].score, 4)
            }

        combined = "\n\n".join([c.text for c in relevant])
        return {
            "found": True,
            "facts": combined,
            "source_count": len(relevant),
            "best_score": round(relevant[0].score, 4)
        }

    except Exception as e:
        logger.error(f"rag_search failed: {e}", exc_info=True)
        return {"found": False, "message": f"Search error: {str(e)}", "facts": ""}