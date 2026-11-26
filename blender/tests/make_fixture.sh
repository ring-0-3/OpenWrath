#!/usr/bin/env bash
# make_fixture.sh — regenerate the self-consistency gate's fixtures FROM the CLI, so the
# gate runs against GROUND-TRUTH-SHAPED input (what bab-decompile actually emits) instead
# of a hand-authored proxy. This is the step that turns the decidable gate from
# "importer matches our belief about the XML shape" into "importer matches real output".
#
#   blender/tests/make_fixture.sh mesh  <stream.manifest> <MESH_ASSET_NAME>
#   blender/tests/make_fixture.sh model <stream.manifest> <CONTAINER_ASSET_NAME>
#
# Output goes to blender/tests/fixtures/local/ (GITIGNORED — never commit EA-derived XML).
# It prints the exact command to run the gate against the generated fixture.
#
# Reuses the SAME decode path and env conventions as tools/mesh-repack-gate.sh:
#   --semantic-mesh is REQUIRED (editable geometry); --schema is REQUIRED (so triangles
#   come out as <V>n</V> child elements, not a schemaless space-list attribute).
# Env (override as needed):
#   KW_SCHEMA        default schemas/kw/xsd/CnC3Types.xsd
#   KW_BASEMANIFESTS default ~/kw-mod-sdk/base-manifests  (-> global/static/english _2 as --rm)
#   KW_STRINGHASHES  optional StringHashes.xml
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEC="$ROOT/Debug/bab-decompile.dll"
OUT="$ROOT/blender/tests/fixtures/local"
SCHEMA="${KW_SCHEMA:-$ROOT/schemas/kw/xsd/CnC3Types.xsd}"
BM="${KW_BASEMANIFESTS:-$HOME/kw-mod-sdk/base-manifests}"
RM="$BM/global_common_2.manifest;$BM/static_common_2.manifest;$BM/global_english_2.manifest"
SH_OPT=(); [[ -n "${KW_STRINGHASHES:-}" ]] && SH_OPT=(--stringhashes "$KW_STRINGHASHES")

MODE="${1:-}"; MF="${2:-}"; NAME="${3:-}"
if [[ -z "$MODE" || -z "$MF" || -z "$NAME" ]]; then
  echo "usage: $0 <mesh|model> <stream.manifest> <ASSET_NAME>"; exit 2
fi
[[ -f "$DEC" ]]     || { echo "ERROR: bab-decompile not built: $DEC (run tools/setup then build)"; exit 1; }
[[ -f "$MF" ]]      || { echo "ERROR: stream manifest not found: $MF"; exit 1; }
[[ -f "$SCHEMA" ]]  || { echo "ERROR: schema not found: $SCHEMA (set KW_SCHEMA)"; exit 1; }

export DOTNET_ROLL_FORWARD=LatestMajor DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
mkdir -p "$OUT"

dec_one() {  # dec_one <ASSET_NAME>
  local a="$1"
  echo "  decompiling $a ..."
  dotnet "$DEC" decompile-stream "$MF" --only "$a" --outdir "$OUT" \
    --semantic-mesh --schema "$SCHEMA" --rm "$RM" "${SH_OPT[@]}" >/dev/null
}

# decompile-stream names files <TypeName>.<name>.xml; find the one for an asset (+ opt type).
find_xml() {  # find_xml <ASSET_NAME> [TYPE]
  local a="$1" ty="${2:-}"
  if [[ -n "$ty" && -f "$OUT/$ty.$a.xml" ]]; then echo "$OUT/$ty.$a.xml"; return; fi
  ls "$OUT"/*."$a".xml 2>/dev/null | head -1
}

if [[ "$MODE" == "mesh" ]]; then
  dec_one "$NAME"
  XML="$(find_xml "$NAME" W3DMesh)"
  [[ -n "$XML" && -f "$XML" ]] || { echo "ERROR: no XML produced for mesh '$NAME'"; exit 1; }
  echo
  echo "fixture ready: $XML"
  echo "run the gate against it:"
  echo "  OW_MESH_FIXTURE=\"$XML\" blender --background --python $ROOT/blender/tests/test_self_consistency.py"
  exit 0
fi

if [[ "$MODE" == "model" ]]; then
  dec_one "$NAME"
  CXML="$(find_xml "$NAME" W3DContainer)"
  [[ -n "$CXML" && -f "$CXML" ]] || { echo "ERROR: no XML produced for container '$NAME'"; exit 1; }
  # Reuse OUR parser to discover the referenced hierarchy + meshes (single source of truth).
  mapfile -t REFS < <(cd "$ROOT/blender" && python3 - "$CXML" <<'PY'
import sys
from openwrath_import import w3x_xml as wx
c = wx.parse_container(sys.argv[1])
if c.hierarchy: print(c.hierarchy)
for s in c.sub_objects:
    if s.render_kind == "Mesh" and s.render_name:
        print(s.render_name)
PY
)
  for r in "${REFS[@]}"; do [[ -n "$r" ]] && dec_one "$r"; done
  echo
  echo "container fixture ready: $CXML  (+ $(( ${#REFS[@]} )) referenced asset(s) in $OUT)"
  echo "run the gate against it:"
  echo "  OW_CONTAINER_FIXTURE=\"$CXML\" \\"
  echo "    blender --background --python $ROOT/blender/tests/test_self_consistency.py"
  echo "(the first referenced mesh is also a good --mesh gate; set OW_MESH_FIXTURE to one of the W3DMesh.*.xml files)"
  exit 0
fi

echo "unknown mode '$MODE' (expected mesh|model)"; exit 2
