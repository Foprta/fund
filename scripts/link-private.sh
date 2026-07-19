#!/usr/bin/env bash
# Symlink private overlay files into this public monorepo checkout.
# Usage: ./scripts/link-private.sh [path-to-fund-private]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ $# -ge 1 ]]; then
  PRIV="$1"
else
  for cand in "$ROOT/../fund-private" "$ROOT/../luna-fund-private"; do
    if [[ -d "$cand/src/api" ]]; then
      PRIV="$cand"
      break
    fi
  done
  PRIV="${PRIV:-$ROOT/../fund-private}"
fi

if [[ ! -d "$PRIV/src/api" ]]; then
  echo "Private overlay not found at: $PRIV" >&2
  echo "Clone https://github.com/Foprta/fund-private next to this repo, or pass its path." >&2
  exit 1
fi

link_one() {
  local src="$1" dest="$2"
  src="$(cd "$(dirname "$src")" && pwd)/$(basename "$src")"
  mkdir -p "$(dirname "$dest")"
  if [[ -e "$dest" || -L "$dest" ]]; then
    rm -rf "$dest"
  fi
  ln -s "$src" "$dest"
  echo "link $dest -> $src"
}

link_one "$PRIV/src/api/policy_local.py" "$ROOT/services/api/src/api/policy_local.py"
link_one "$PRIV/src/api/tools_local.py" "$ROOT/services/api/src/api/tools_local.py"
link_one "$PRIV/src/fund_core/models_local.py" "$ROOT/packages/fund_core/src/fund_core/models_local.py"
link_one "$PRIV/src/fund_core/queries_local.py" "$ROOT/packages/fund_core/src/fund_core/queries_local.py"
link_one "$PRIV/src/integrations/sync_sheets_local.py" "$ROOT/packages/integrations/src/integrations/sync_sheets_local.py"
link_one "$PRIV/migrations/versions/900_participant_local.py" "$ROOT/migrations/versions/900_participant_local.py"
link_one "$PRIV/scripts/seed_demo_local.py" "$ROOT/scripts/seed_demo_local.py"
link_one "$PRIV/tests/restricted_terms_local.py" "$ROOT/tests/restricted_terms_local.py"
link_one "$PRIV/local" "$ROOT/local"
link_one "$PRIV/tests_local" "$ROOT/tests_local"

echo "Done. Optional: uv pip install -e $PRIV   (do not uv-add into public pyproject.toml)"
echo "Merge phrase keys from $PRIV/.env.example into .env"
