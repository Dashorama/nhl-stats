#!/usr/bin/env bash
# Publish pipeline: generate site data, deploy to Vercel, post to Bluesky.
# Runs after update.sh (cron 10:30 UTC). Each step fails independently.
#
# Required env vars: BLUESKY_HANDLE, BLUESKY_APP_PASSWORD, SITE_URL
# Vercel auth uses stored CLI credentials (~/.local/share/com.vercel.cli/auth.json)

set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
[ -f "${HOME}/.env.nhl-stats" ] && source "${HOME}/.env.nhl-stats"
LOG_FILE="${PROJECT_DIR}/data/logs/publish-$(date +%Y-%m-%d).log"
mkdir -p "${PROJECT_DIR}/data/logs"

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG_FILE"; }

# NOTE: This script is scheduled 30 minutes after update.sh (10:00 UTC → 10:30 UTC).
# The gap is a fixed delay, not a dependency lock. If update.sh ever takes >30 minutes,
# this script will deploy stale data. Extend the gap in install-cron.sh if needed.

: "${BLUESKY_HANDLE:?BLUESKY_HANDLE is required}"
: "${BLUESKY_APP_PASSWORD:?BLUESKY_APP_PASSWORD is required}"

INJURIES_ARGS=()
SKIP_SOCIAL=""

log "=== Publish pipeline start ==="
source "${PROJECT_DIR}/.venv/bin/activate"

# Step 1: Scrape injuries (gates social posting on failure)
log "Scraping injuries..."
if python -m src.cli injuries >> "$LOG_FILE" 2>&1; then
    log "  injuries OK"
else
    log "  injuries FAILED — player stories and social post disabled"
    INJURIES_ARGS=("--injuries-unavailable")
    SKIP_SOCIAL="1"
fi

# Step 2: Fetch RSS (non-fatal)
log "Fetching RSS..."
PYTHONPATH="${PROJECT_DIR}" python "${PROJECT_DIR}/scripts/fetch_rss.py" >> "$LOG_FILE" 2>&1 \
    || log "  RSS fetch failed (non-fatal)"

# Step 3: Generate data files (fatal — deploy without this is pointless)
log "Generating data files..."
if ! PYTHONPATH="${PROJECT_DIR}" python "${PROJECT_DIR}/scripts/generate.py" "${INJURIES_ARGS[@]}" >> "$LOG_FILE" 2>&1; then
    log "  generate FAILED — aborting"
    exit 1
fi

# Step 4: Deploy to Vercel (fatal)
log "Deploying to Vercel..."
if ! (cd "${PROJECT_DIR}/site" && vercel deploy --yes >> "$LOG_FILE" 2>&1); then
    log "  deploy FAILED"
    exit 1
fi
log "  deploy OK"

# Step 5: Post to Bluesky (non-fatal; skipped if injuries unavailable)
if [ -n "$SKIP_SOCIAL" ]; then
    log "  Bluesky skipped (injury data unavailable)"
else
    log "Posting to Bluesky..."
    PYTHONPATH="${PROJECT_DIR}" SITE_URL="${SITE_URL:-}" \
        python "${PROJECT_DIR}/scripts/social.py" >> "$LOG_FILE" 2>&1 \
        && log "  Bluesky OK" \
        || log "  Bluesky failed (non-fatal)"
fi

log "=== Publish pipeline complete ==="
