# 🏛️ My Pocket Guide — AI Tour Guide

> A real-time, voice-and-vision AI tour guide built with Google Agent Development Kit (ADK), Gemini Live 2.5 Flash native audio, and Vertex AI RAG. Point your phone at any exhibit and your personal guide narrates it — tailored to *you*.

Built for the [Gemini Live Agent Challenge](https://geminiliveagentchallenge.devpost.com/) · Category: **Live Agents** 🗣️

---

## ✨ What It Does

My Pocket Guide transforms a standard museum visit into a personalised, conversational experience:

1. **Meet Charon** — A concierge agent greets you by voice, learns your name, your passions (music, sport, gaming, whatever you're into), and what you want from the visit.
2. **Hand off to Puck** — Your tour guide agent takes over with a different voice and persona. It has your profile.
3. **Point your camera** — Aim your phone at any exhibit. Puck sees it in real time via native multimodal vision, calls the RAG knowledge base for verified facts, and narrates a story that connects the exhibit to *your* interests.
4. **Have a conversation** — Interrupt at any time. Ask questions. Ask what's nearby. The experience is live, not turn-based.

**Five galleries. 16 exhibits. Zero text boxes.**

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Browser / Mobile                    │
│  HTML + JS frontend                                      │
│  • WebSocket bidi-stream (PCM audio + JPEG frames)       │
│  • AudioWorklet for zero-latency playback                │
│  • Camera capture at max 1fps → send_realtime() blobs    │
└────────────────────┬────────────────────────────────────┘
                     │ WebSocket (wss://)
┌────────────────────▼────────────────────────────────────┐
│                  Cloud Run  (us-central1)                │
│  FastAPI + uvicorn                                       │
│  • Bidi-streaming WebSocket endpoint                     │
│  • LiveRequestQueue + Runner (ADK)                       │
│  • Startup session cleanup                               │
└──────┬─────────────────────────┬───────────────────────┘
       │ ADK multi-agent          │ asyncpg
┌──────▼──────────┐    ┌─────────▼──────────────────────┐
│  Concierge      │    │  Cloud SQL  (us-central1)       │
│  Agent (Charon) │    │  PostgreSQL — sessions + events │
│  • save_profile │    └────────────────────────────────┘
└──────┬──────────┘
       │ agent transfer
┌──────▼──────────────────────────────────────────────────┐
│  Tour Guide Agent (Puck)                                 │
│  gemini-live-2.5-flash-native-audio                      │
│  • Native multimodal vision (camera frames inline)       │
│  • identify_exhibit() — state sync + map update          │
│  • rag_search() — Vertex AI RAG knowledge base           │
└──────────────────────────┬──────────────────────────────┘
                           │
              ┌────────────▼──────────────┐
              │  Vertex AI RAG  (us-west1) │
              │  16 exhibit markdown files  │
              │  grounded facts + metadata  │
              └───────────────────────────┘
```

### Key design decisions

- **Region co-location**: Cloud Run and Gemini Live endpoint both in `us-central1` — critical for bidi-streaming latency. RAG corpus is in `us-west1` (one-off lookups tolerate cross-region round-trip).
- **Native vision over streaming tools**: Camera frames sent as `send_realtime(Blob(mime_type="image/jpeg"))` — uses the model's built-in multimodal capabilities instead of a custom streaming tool.
- **Independent tools**: `identify_exhibit` (state sync) and `rag_search` (knowledge retrieval) are intentionally independent — a failed identification never silently skips RAG lookup.
- **Context window compression**: `ContextWindowCompressionConfig` enables unlimited session duration by summarising old context rather than hard-capping the session.

---

## 🗂️ Repository Structure

```
my-pocket-guide/
├── backend/
│   ├── main.py                  # FastAPI app, WebSocket handler, ADK runner
│   ├── agent.py                 # Root agent (SequentialAgent wrapper)
│   └── agents/
│       ├── concierge_agent.py   # Charon — profile collection + handoff
│       └── tour_guide_agent.py  # Puck — vision + RAG narration
│   └── tools/
│       ├── identify_tool.py     # Exhibit identification + state sync
│       ├── rag_tool.py          # Vertex AI RAG search
│       └── profile_tool.py      # Save visitor profile to session state
├── frontend/
│   ├── index.html               # Single-page app
│   └── js/
│       ├── audio-player.js      # AudioWorklet for PCM playback
│       └── pcm-player-processor.js
├── data/
│   └── exhibits/                # 16 exhibit markdown files (RAG source)
├── scripts/
│   ├── ingest.py                # RAG corpus ingestion
│   ├── dedup_rag.py             # Remove duplicate RAG files
│   └── add_visual_ids.py        # Patch exhibit files with visual keywords
├── tests/
│   └── test_rag.py              # RAG integration tests
├── Dockerfile
├── deploy.sh                    # Cloud Run deployment script
├── .env.example                 # Environment variable template
└── requirements.txt
```

---

## 🚀 Spin-Up Instructions

### Prerequisites

- Python 3.12+
- Google Cloud project with billing enabled
- `gcloud` CLI authenticated (`gcloud auth login`)
- APIs enabled: Cloud Run, Cloud SQL Admin, Vertex AI, Secret Manager

### 1. Clone & install

```bash
git clone https://github.com/YOUR_USERNAME/my-pocket-guide.git
cd my-pocket-guide
python -m venv venv312 && source venv312/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your values — see comments in the file
```

### 3. Set up Cloud SQL

```bash
# Create instance (if not already exists)
gcloud sql instances create museum-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1

# Create database and user
gcloud sql databases create museum_sessions --instance=museum-db
gcloud sql users create museum_user --instance=museum-db --password=YOUR_PASSWORD
```

### 4. Ingest exhibit data into Vertex AI RAG

```bash
# First run: creates corpus and ingests all 16 exhibit files
python3 scripts/ingest.py

# Copy the RAG_CORPUS value printed at the end into your .env
```

### 5. Run locally

```bash
# Requires Cloud SQL proxy or a local PostgreSQL instance
# Set DATABASE_URL in .env to point to local DB

uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload
# Open http://localhost:8080
```

### 6. Deploy to Cloud Run

```bash
# Load your .env and deploy
source .env && ./deploy.sh
```

The script will print the service URL when complete.

### 7. Automated deployment (CI/CD)

Push to `main` branch triggers `.github/workflows/deploy.yml`. Configure these GitHub Secrets in your repo settings:

| Secret | Description |
|--------|-------------|
| `GCP_SA_KEY` | JSON key for a service account with Cloud Run Admin + Cloud SQL Client roles |
| `GCP_PROJECT` | Your Google Cloud project ID |
| `CLOUDSQL_INSTANCE` | `project:region:instance` |
| `DB_USER` / `DB_PASS` / `DB_NAME` | Database credentials |
| `RAG_CORPUS` | Full Vertex AI corpus resource name |
| `RECAPTCHA_SITE_KEY` / `RECAPTCHA_SECRET_KEY` | reCAPTCHA v3 keys |

---

## 🖼️ Galleries & Exhibits

| Gallery | Exhibits |
|---------|----------|
| 🦕 Echoes of the Deep | Hope the Blue Whale, Dippy the Diplodocus, The Coelacanth |
| 🏛️ Marble & Myth | Caryatid of the Erechtheion, The Parthenon Frieze, The Antikythera Mechanism |
| 🚀 Beyond the Horizon | The Willamette Meteorite, Apollo 11 Command Module, Hubble Space Telescope Replica |
| 🦑 Abyss | The Giant Squid Specimen, Megalodon Jaw Reconstruction, HMS Challenger Collection |
| 🎨 Brushstrokes of Time | The Mona Lisa, Trevi Fountain (Panini), Andy Warhol's Marilyn Monroe, Really Good (Shrigley) |

---

## 🧰 Tech Stack

| Component | Technology |
|-----------|-----------|
| AI Agents | Google ADK (Agent Development Kit) |
| LLM / Audio | Gemini Live 2.5 Flash (`gemini-live-2.5-flash-native-audio`) |
| Vision | Gemini native multimodal (camera frames via `send_realtime`) |
| Knowledge Base | Vertex AI RAG Engine |
| Backend | FastAPI + WebSocket bidi-streaming |
| Session Storage | Cloud SQL PostgreSQL (ADK `DatabaseSessionService`) |
| Deployment | Google Cloud Run (`us-central1`) |
| CI/CD | GitHub Actions |
| Audio Playback | Web Audio API + AudioWorklet (PCM) |

---

## 🔑 Google Cloud Services Used

- **Cloud Run** — serves the FastAPI backend and static frontend
- **Vertex AI** — Gemini Live 2.5 Flash model + RAG Engine corpus
- **Cloud SQL** — PostgreSQL for ADK session and event persistence
- **Artifact Registry** — container image storage (via `gcloud run deploy --source`)