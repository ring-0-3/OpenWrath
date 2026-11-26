#!/usr/bin/env bash
# Run both OpenWrath add-on test tiers.
#
#   blender/tests/run_tests.sh
#
#   1. Parser tests        — system python3, no Blender needed (always runs).
#   2. Self-consistency    — the decidable gate, under Blender's bundled python.
#                            Skipped (not failed) if `blender` is not on PATH.
#
# Point the gate at your own locally-decompiled mesh instead of the synthetic cube:
#   OW_MESH_FIXTURE=/path/to/mymesh.xml blender/tests/run_tests.sh
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BLENDER_DIR="$(dirname "$HERE")"

echo "== [1/2] parser tests (system python) =="
python3 "$HERE/test_parser.py"

echo
echo "== [2/2] self-consistency gate (Blender) =="
if command -v blender >/dev/null 2>&1; then
  blender --background --python "$HERE/test_self_consistency.py"
else
  echo "SKIP: 'blender' not on PATH — install Blender 4.1+ to run the decidable gate."
fi
