#!/usr/bin/env bash
# NHL Stats data update script
# Called by cron — see OPERATIONS.md for schedule and configuration.
#
# Usage:
#   ./scripts/update.sh          # Full update (all sources)
#   ./scripts/update.sh --daily  # Daily update (games, boxscores, PBP, game logs only)
#
# Logs are written to data/logs/update-YYYY-MM-DD.log
# Exit code 0 = success, 1 = partial failure, 2 = total failure

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${PROJECT_DIR}/data/logs"
LOG_FILE="${LOG_DIR}/update-$(date +%Y-%m-%d).log"

mkdir -p "$LOG_DIR"

echo "=== NHL Stats Update: $(date -Iseconds) ===" >> "$LOG_FILE"
echo "Args: $*" >> "$LOG_FILE"

# Activate virtual environment
source "${PROJECT_DIR}/.venv/bin/activate"

# Run update, capturing output
if python -m src.cli update "$@" >> "$LOG_FILE" 2>&1; then
    echo "=== Completed successfully: $(date -Iseconds) ===" >> "$LOG_FILE"
    exit 0
else
    echo "=== Completed with errors: $(date -Iseconds) ===" >> "$LOG_FILE"
    exit 1
fi
