#!/usr/bin/env bash
# Build a snapshot of the bundle source under app/server/_bundle_source/.
# Run BEFORE `databricks bundle deploy` so the "Bundle source" tab inside the app
# has up-to-date files to serve.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/app/server/_bundle_source"

echo "Snapshotting bundle source into: $DEST"
rm -rf "$DEST"
mkdir -p "$DEST"

# Top-level bundle files (the ones a reader would expect to see first).
# Deliberately excluded:
#   DEPLOYMENT.md   - internal handover notes from the demo deploy
#   architecture.md - data is rendered live in the Architecture tab
for f in README.md dab_instructions.md databricks.yml resources.json; do
  if [ -f "$ROOT/$f" ]; then
    cp "$ROOT/$f" "$DEST/"
  fi
done

# Pipeline + SDK + jobs sources
cp -R "$ROOT/src" "$DEST/src"

# App sources (exclude __pycache__, *.pyc, and the snapshot directory itself)
mkdir -p "$DEST/app"
rsync -a \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='_bundle_source' \
  --exclude='.DS_Store' \
  "$ROOT/app/" "$DEST/app/"

# Helper scripts
if [ -d "$ROOT/scripts" ]; then
  cp -R "$ROOT/scripts" "$DEST/scripts"
fi

# Strip macOS noise
find "$DEST" -name ".DS_Store" -delete 2>/dev/null || true

# Databricks Apps source upload classifies *.py as Notebook objects which strips
# the .py extension on the way in. To keep .py files browsable AS PYTHON in the
# Bundle source viewer, append .txt so the upload treats them as plain files.
# The bundle.py route strips the trailing .txt back off when listing + serving.
find "$DEST" -type f -name "*.py" -exec mv {} {}.txt \;

echo "Files snapshotted:"
find "$DEST" -type f | wc -l
echo "Size:"
du -sh "$DEST" | awk '{print $1}'
