#!/usr/bin/env bash
# Usage:  bash restructure_engine.sh          (dry run, changes nothing)
#         APPLY=1 bash restructure_engine.sh  (does it)
set -euo pipefail

if ROOT=$(git rev-parse --show-toplevel 2>/dev/null); then
  HAVE_GIT=1
else
  ROOT=$(pwd); HAVE_GIT=0
fi
cd "$ROOT"
[ -d backend/engine ] || { echo "Run this from the project root (the folder that contains backend/)."; exit 1; }

ENG=backend/engine
APPLY=${APPLY:-0}

# old module name | new path under engine/ (no .py)
MAP=(
  "types|simulation/types"
  "runner|simulation/pipeline"
  "settings_resolver|simulation/config/resolver"
  "platforms|simulation/config/platforms"
  "culture|simulation/config/culture"
  "scenarios|simulation/config/scenarios"
  "population|simulation/population/builder"
  "profile_traits|simulation/population/traits"
  "archetypes|simulation/population/archetypes"
  "priors|simulation/reaction/priors"
  "behavior|simulation/behavior/crowd_brain"
  "timeline|simulation/runtime/timeline"
  "montecarlo|simulation/runtime/montecarlo"
  "aggregate|simulation/results/aggregate"
  "scoring|simulation/results/scoring"
  "evidence|simulation/results/evidence"
)

run() { if [ "$APPLY" = "1" ]; then eval "$@"; else echo "[dry] $*"; fi; }

# GNU sed (Linux/Docker) vs BSD sed (macOS)
if sed --version >/dev/null 2>&1; then SEDI=(sed -i -E); else SEDI=(sed -i '' -E); fi

if [ "$HAVE_GIT" = "1" ]; then
  [ -z "$(git status --porcelain)" ] || { echo "Working tree not clean. Commit or stash first."; exit 1; }
  MV="git mv"
else
  MV="mv"
  BACKUP="backend.bak.$(date +%Y%m%d-%H%M%S)"
  echo "No git repository found. A full backup will be made first: $BACKUP"
  run "cp -a backend '$BACKUP'"
fi

# 1) folders + __init__.py (deduplicated)
dirs=$(for e in "${MAP[@]}"; do
  d="$ENG/$(dirname "${e#*|}")"
  while [ "$d" != "$ENG" ]; do echo "$d"; d="$(dirname "$d")"; done
done | sort -u)
for d in $dirs; do
  run "mkdir -p '$d'"
  run "[ -f '$d/__init__.py' ] || touch '$d/__init__.py'"
done

# 2) move files
for e in "${MAP[@]}"; do
  old="${e%%|*}"; new="${e#*|}"
  if [ -f "$ENG/$old.py" ]; then
    run "$MV '$ENG/$old.py' '$ENG/$new.py'"
  else
    echo "SKIP (not found): $ENG/$old.py"
  fi
done

# 3) rewrite imports everywhere under backend/ (skip backups)
for e in "${MAP[@]}"; do
  old="${e%%|*}"; new="${e#*|}"; dotted="engine.$(echo "$new" | tr '/' '.')"
  files=$(grep -rlE "\bengine\.${old}\b" backend --include=*.py 2>/dev/null || true)
  for f in $files; do
    run "${SEDI[*]} 's/\\bengine\\.${old}\\b/${dotted}/g' '$f'"
  done
done

echo "Done. Now run the checks."