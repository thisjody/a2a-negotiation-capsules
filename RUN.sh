#!/usr/bin/env bash
# demo2 — one-command runner. Builds a venv the first time, then plays the demo.
#   bash RUN.sh              # the paced terminal run (this is the demo)
#   bash RUN.sh --step       # you drive: press Enter between beats
#   bash RUN.sh --fast       # no pauses
#   bash RUN.sh --browser    # render + open the self-contained page instead
# Any other flags pass straight through to narrate.py.
set -e
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if [ ! -d .venv ]; then
  echo "one-time setup (~20s, only the first run)…"
  "$PY" -m venv .venv
  ./.venv/bin/pip install -q "capsule-emit>=0.7.0" "agent-action-capsule>=0.2.0" >/dev/null 2>&1
  echo "setup done."
fi

if [ "$1" = "--browser" ]; then
  shift
  echo "rendering the page (nothing runs in the terminal)…"
  ./.venv/bin/python narrate.py --fast --bundle evidence --html "$PWD/evidence/index.html" "$@" >/dev/null 2>&1
  PAGE="$PWD/evidence/index.html"
  echo "→ opening $PAGE"
  if command -v open >/dev/null 2>&1; then open "$PAGE"
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$PAGE"
  else echo "open it yourself:  $PAGE"; fi
else
  echo
  ./.venv/bin/python narrate.py --bundle evidence "$@"
fi
