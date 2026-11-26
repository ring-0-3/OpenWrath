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

echo "== [1/5] parser tests (system python) =="
python3 "$HERE/test_parser.py"

echo
echo "== [2/5] texture decidable-anchor tests (system python) =="
python3 "$HERE/test_textures.py"

echo
echo "== [3/5] exporter capture/writer tests (system python) =="
python3 "$HERE/test_export.py"

echo
echo "== [4/5] self-consistency gate (Blender) =="
if command -v blender >/dev/null 2>&1; then
  blender --background --python "$HERE/test_self_consistency.py"
else
  echo "SKIP: 'blender' not on PATH — install Blender 4.1+ to run the decidable gate."
fi

echo
echo "== [5/5] exporter round-trip gate: unmodified byte-exact tier + edit detection (Blender) =="
if command -v blender >/dev/null 2>&1; then
  blender --background --python "$HERE/test_export_roundtrip.py"
else
  echo "SKIP: 'blender' not on PATH — install Blender 4.1+ to run the exporter gate."
fi
