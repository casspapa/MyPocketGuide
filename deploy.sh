#!/usr/bin/env bash
# =============================================================================
# My Pocket Guide — Cloud Run deployment script
# =============================================================================
# Usage:
#   cp .env.example .env          # fill in your values
#   source .env && ./deploy.sh
#
# Or pass vars inline:
#   GCP_PROJECT=my-project DB_PASS=secret ./deploy.sh
# =============================================================================
set -euo pipefail

# ── Required — must be set in environment ────────────────────────────────────
: "${GCP_PROJECT:?GCP_PROJECT is required (your Google Cloud project ID)}"
: "${CLOUDSQL_INSTANCE:?CLOUDSQL_INSTANCE is required (e.g. project:region:instance)}"
: "${DB_USER:?DB_USER is required}"
: "${DB_PASS:?DB_PASS is required}"
: "${DB_NAME:?DB_NAME is required (e.g. museum_sessions)}"
: "${RAG_CORPUS:?RAG_CORPUS is required (full Vertex AI corpus resource name)}"
: "${RECAPTCHA_SITE_KEY:?RECAPTCHA_SITE_KEY is required}"
: "${RECAPTCHA_SECRET_KEY:?RECAPTCHA_SECRET_KEY is required}"

# ── Optional with sensible defaults ──────────────────────────────────────────
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-museum-tour-guide}"
AGENT_MODEL="${AGENT_MODEL:-gemini-live-2.5-flash-native-audio}"
RAG_LOCATION="${RAG_LOCATION:-us-west1}"
CLOUDSQL_SOCKET_DIR="/cloudsql/${CLOUDSQL_INSTANCE}"

# ── Build the DATABASE_URL from parts (no raw password in this file) ─────────
DATABASE_URL="postgresql+asyncpg://${DB_USER}:${DB_PASS}@/${DB_NAME}?host=${CLOUDSQL_SOCKET_DIR}"

echo "🚀 Deploying ${SERVICE_NAME} to ${REGION}..."
echo "   Project : ${GCP_PROJECT}"
echo "   Model   : ${AGENT_MODEL}"
echo "   SQL     : ${CLOUDSQL_INSTANCE}"
echo ""

gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --region "${REGION}" \
  --project "${GCP_PROJECT}" \
  --add-cloudsql-instances "${CLOUDSQL_INSTANCE}" \
  --set-env-vars "GOOGLE_GENAI_USE_VERTEXAI=true,\
GOOGLE_CLOUD_PROJECT=${GCP_PROJECT},\
GOOGLE_CLOUD_LOCATION=${REGION},\
AGENT_MODEL=${AGENT_MODEL},\
RAG_LOCATION=${RAG_LOCATION},\
RAG_CORPUS=${RAG_CORPUS},\
DATABASE_URL=${DATABASE_URL},\
RECAPTCHA_SITE_KEY=${RECAPTCHA_SITE_KEY},\
RECAPTCHA_SECRET_KEY=${RECAPTCHA_SECRET_KEY}" \
  --allow-unauthenticated \
  --timeout=3600

echo ""
echo "✅ Deployment complete."
echo "   Service URL: $(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --project ${GCP_PROJECT} --format 'value(status.url)')"