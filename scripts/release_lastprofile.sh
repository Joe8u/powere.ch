#!/usr/bin/env bash
set -euo pipefail

RELEASE="${1:-2024-08_release}"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

mkdir -p "$ROOT/data/lastprofile/curated/$RELEASE"
cp "$ROOT"/data/lastprofile/processed/2024/*.csv "$ROOT/data/lastprofile/curated/$RELEASE/"

# Manifest-Header
cat > "$ROOT/data/lastprofile/curated/$RELEASE/manifest.yaml" <<'YAML'
release_id: 2024-08
namespace: lastprofile
year: 2024
timezone: Europe/Zurich
unit: MW
freq: 15min
files:
YAML

# Einträge anhängen (zsh/bash-sicher)
for f in "$ROOT/data/lastprofile/curated/$RELEASE"/*.csv; do
  rows=$(( $(wc -l < "$f") - 1 ))
  if command -v shasum >/dev/null 2>&1; then
    sha=$(shasum -a 256 "$f" | awk '{print $1}')
  else
    sha=$(sha256sum "$f" | awk '{print $1}')
  fi
  base=$(basename "$f")
  printf "  - name: %s\n    rows: %s\n    sha256: %s\n" "$base" "$rows" "$sha"
done >> "$ROOT/data/lastprofile/curated/$RELEASE/manifest.yaml"

rm -f "$ROOT/data/lastprofile/curated/current"
ln -s "$RELEASE" "$ROOT/data/lastprofile/curated/current"

echo "[OK] curated release: $RELEASE"
