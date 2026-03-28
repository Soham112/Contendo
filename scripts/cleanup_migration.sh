#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# cleanup_migration.sh — remove the temporary migration endpoint
#
# Run this after you have verified data is live on Railway.
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MIGRATE_ROUTER="$REPO_ROOT/backend/routers/migrate.py"
MAIN_PY="$REPO_ROOT/backend/main.py"

# 1. Delete migrate.py
if [ -f "$MIGRATE_ROUTER" ]; then
  rm "$MIGRATE_ROUTER"
  echo "==> Deleted $MIGRATE_ROUTER"
else
  echo "==> $MIGRATE_ROUTER already gone, skipping"
fi

# 2. Remove the import line from main.py
sed -i '' '/from routers import migrate.*TEMPORARY MIGRATION/d' "$MAIN_PY"

# 3. Remove the include_router line from main.py
sed -i '' '/app\.include_router(migrate\.router).*TEMPORARY MIGRATION/d' "$MAIN_PY"

echo "==> Cleaned main.py"
echo ""
echo "Done — now commit and push to remove the migration endpoint from production"
