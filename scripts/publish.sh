#!/usr/bin/env bash
# Publish pipeline: generate site data, deploy to Vercel, post to Bluesky.
# Runs after update.sh (cron 10:30 UTC). Each step fails independently.
#
# Required env vars: BLUESKY_HANDLE, BLUESKY_APP_PASSWORD, SITE_URL
# Vercel auth uses stored CLI credentials (~/.local/share/com.vercel.cli/auth.json)

set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Cron runs with a minimal PATH — ensure we can find node, vercel, etc.
export PATH="${HOME}/.local/bin:/usr/local/bin:${PATH}"

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
INJURIES_FAILED=""

log "=== Publish pipeline start ==="
source "${PROJECT_DIR}/.venv/bin/activate"

# Step 1: Scrape injuries (gates social posting on failure)
log "Scraping injuries..."
if python -m src.cli injuries >> "$LOG_FILE" 2>&1; then
    log "  injuries OK"
else
    log "  injuries FAILED — injury-dependent stories will skip social"
    INJURIES_ARGS=("--injuries-unavailable")
    INJURIES_FAILED="1"
fi

# Step 2: Fetch RSS (non-fatal)
log "Fetching RSS..."
PYTHONPATH="${PROJECT_DIR}" python "${PROJECT_DIR}/scripts/fetch_rss.py" >> "$LOG_FILE" 2>&1 \
    || log "  RSS fetch failed (non-fatal)"

# Step 2b: Scrape NHL EDGE tracking data (non-fatal)
log "Scraping NHL EDGE tracking data..."
PYTHONPATH="${PROJECT_DIR}" python "${PROJECT_DIR}/scripts/scrape_edge.py" >> "$LOG_FILE" 2>&1 \
    || log "  EDGE scrape failed (non-fatal — tracking data will be stale)"

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

# Step 5: Post to Bluesky (non-fatal; skipped if injuries failed AND story needs injury data)
SKIP_SOCIAL=""
if [ -n "$INJURIES_FAILED" ]; then
    STORY_JSON="${PROJECT_DIR}/site/public/data/story.json"
    STORY_TYPE=$(python -c "import json,sys;print(json.load(open(sys.argv[1]))['story_type'])" "$STORY_JSON" 2>/dev/null || echo "")
    SUBJECT_TYPE=$(python -c "import json,sys;print(json.load(open(sys.argv[1])).get('subject_type',''))" "$STORY_JSON" 2>/dev/null || echo "")
    case "$STORY_TYPE" in
        StoryType.NEWS_COMBO|StoryType.EXTREME_SHOOTER)
            SKIP_SOCIAL="1"
            ;;
        StoryType.FALLBACK)
            [ "$SUBJECT_TYPE" = "player" ] && SKIP_SOCIAL="1"
            ;;
    esac
fi
if [ -n "$SKIP_SOCIAL" ]; then
    log "  Bluesky skipped (injury data unavailable, story_type=${STORY_TYPE} needs it)"
else
    log "Posting to Bluesky..."
    PYTHONPATH="${PROJECT_DIR}" SITE_URL="${SITE_URL:-}" \
        python "${PROJECT_DIR}/scripts/social.py" >> "$LOG_FILE" 2>&1 \
        && log "  Bluesky OK" \
        || log "  Bluesky failed (non-fatal)"
fi

log "=== Publish pipeline complete ==="
