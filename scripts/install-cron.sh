#!/usr/bin/env bash
# Install nhl-stats cron jobs.
# See OPERATIONS.md for schedule rationale.
#
# Schedule:
#   Daily at 10:00 UTC (6am ET): games, boxscores, PBP, game logs
#   Sunday at 12:00 UTC (8am ET): full update including shots and advanced stats
#
# To migrate to a central scheduler, remove these cron entries
# (run uninstall-cron.sh) and replicate the two schedules above.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="${PROJECT_DIR}/scripts/update.sh"
LOG_DIR="${PROJECT_DIR}/data/logs"
MARKER="# nhl-stats-update"

# Remove existing entries first
crontab -l 2>/dev/null | grep -v "$MARKER" | grep -v "# nhl-stats-publish" | crontab - 2>/dev/null || true

# Add new entries
(crontab -l 2>/dev/null || true; cat <<EOF
0 10 * * * ${SCRIPT} --daily ${MARKER}-daily
0 12 * * 0 ${SCRIPT} ${MARKER}-full
30 10 * * * cd ${PROJECT_DIR} && bash scripts/publish.sh >> ${LOG_DIR}/cron.log 2>&1 # nhl-stats-publish
EOF
) | crontab -

echo "Installed cron jobs:"
crontab -l | grep -E "nhl-stats-(update|publish)"
echo ""
echo "Daily update:  10:00 UTC (6am ET) every day"
echo "Full update:   12:00 UTC (8am ET) every Sunday"
echo "Publish:       10:30 UTC (6:30am ET) every day"
