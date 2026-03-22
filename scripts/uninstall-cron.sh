#!/usr/bin/env bash
# Remove nhl-stats cron jobs.
# Run this before migrating to a central scheduler.

set -euo pipefail

MARKER="# nhl-stats-update"

crontab -l 2>/dev/null | grep -v "$MARKER" | grep -v "# nhl-stats-publish" | crontab - 2>/dev/null || true

echo "Removed nhl-stats cron jobs."
echo "Current crontab:"
crontab -l 2>/dev/null || echo "(empty)"
