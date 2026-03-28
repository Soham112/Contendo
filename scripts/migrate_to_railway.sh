#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# migrate_to_railway.sh — pack local backend/data and upload to Railway
#
# Required env vars:
#   RAILWAY_URL       e.g. https://contendo-production.up.railway.app
#   MIGRATION_SECRET  must match the MIGRATION_SECRET set in Railway Variables
#
# Usage:
#   RAILWAY_URL=https://contendo-production.up.railway.app \
#   MIGRATION_SECRET=your-secret \
#   bash scripts/migrate_to_railway.sh
# ---------------------------------------------------------------------------

: "${RAILWAY_URL:?RAILWAY_URL is not set}"
: "${MIGRATION_SECRET:?MIGRATION_SECRET is not set}"

ARCHIVE=/tmp/contendo_data.tar.gz
DATA_DIR="$(dirname "$0")/../backend/data"

echo "==> Packaging local data from $DATA_DIR ..."
tar -czf "$ARCHIVE" \
  -C "$DATA_DIR" \
  chroma_db \
  posts.db \
  hierarchy.db \
  profile.json

SIZE=$(du -sh "$ARCHIVE" | cut -f1)
echo "==> Archive size: $SIZE  ($ARCHIVE)"

echo "==> Uploading to $RAILWAY_URL/admin/migrate ..."
RESPONSE=$(curl -sS --max-time 300 \
  -X POST "$RAILWAY_URL/admin/migrate" \
  -H "x-migration-secret: $MIGRATION_SECRET" \
  -F "file=@$ARCHIVE;type=application/gzip")

echo ""
echo "==> Response from Railway:"
echo "$RESPONSE"
echo ""
echo "==> Migration complete — verify at $RAILWAY_URL/stats"
