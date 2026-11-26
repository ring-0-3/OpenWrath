#!/usr/bin/env bash
# mesh-repack-gate.sh — the W3DMesh RE-PACK EQUALITY GATE (finding 0025; the Blender keystone).
#
#   tools/mesh-repack-gate.sh --from-binary <stream.manifest> [--sample N] [--seed S] [--all]
#
# The decidable test that validates the SEMANTIC-DECODE ∘ PACKER pair on EA's actual bytes:
#
#   shipped W3DMesh  --decompile --semantic-mesh-->  authoring <Vertices>/<Normals>/<TexCoords>/<BoneInfluences>
#                    --compile (W3DMeshProcessor.BuildVertexData)-->  re-packed W3DMeshVertexData
#                    --byte-compare to the shipped packed bytes-->  BYTEEXACT ⇒ the pair is a faithful EA
#                                                                   reimplementation, proven on shipped data.
#
# It reuses the REAL compiler packer (not a second copy): the semantic XML carries <Vertices> and no <VertexData>,
# so IsRuntimeMesh=false and the compiler runs BuildVertexData — single source of truth (CLAUDE.md invariant 3).
# The stream is BRING-YOUR-OWN (no EA data in this repo); its .bin/.relo/.imp siblings must be DECOMPRESSED.
#
# Sampling is REPRODUCIBLE (seeded) AND STRATIFIED: every distinct vertex-declaration LAYOUT present in the
# corpus is forced into the sample (coverage of the "weird" on purpose — verification-blind-spots §1), then a
# seeded-random fill brings the total up to --sample. --all gates the whole corpus. Results are bucketed HONESTLY
# (invariant 5): BYTEEXACT / SIZEOK_VALDIFF / SIZEDIFF / RAW-FALLBACK, with first-diff offsets for mismatches and
# an explicit exercised-vs-unexercised packer-path matrix. Reuses tools/compare-stream.py's manifest parser.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BAB="$ROOT/Debug/BinaryAssetBuilder.dll"
DEC="$ROOT/Debug/bab-decompile.dll"
SCHEMA="${KW_SCHEMA:-$ROOT/schemas/kw/xsd/CnC3Types.xsd}"
BM="${KW_BASEMANIFESTS:-$HOME/kw-mod-sdk/base-manifests}"
RM="$BM/global_common_2.manifest;$BM/static_common_2.manifest;$BM/global_english_2.manifest"
MESH_TYPE="c2b1a262"   # W3DMesh TypeId

source "$ROOT/tools/verify-inputs-preflight.sh" 2>/dev/null && verify_inputs_preflight 2>/dev/null || true

if [[ "${1:-}" != "--from-binary" ]]; then
  echo "usage: tools/mesh-repack-gate.sh --from-binary <stream.manifest> [--sample N] [--seed S] [--all]"; exit 2
fi
STREAM_MF="${2:?--from-binary requires a <stream.manifest> path}"; shift 2
SAMPLE=300; SEED=42; ALL=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --sample) SAMPLE="$2"; shift 2;;
    --seed)   SEED="$2"; shift 2;;
    --all)    ALL=1; shift;;
    *) echo "  WARN: ignoring unknown arg '$1'"; shift;;
  esac
done
[[ -f "$STREAM_MF" ]] || { echo "  ERROR: stream manifest not found: $STREAM_MF"; exit 1; }

export DOTNET_ROLL_FORWARD=LatestMajor DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/dec" "$WORK/new"

echo "[1/4] decompile all W3DMesh SEMANTICALLY from $STREAM_MF"
dotnet "$DEC" decompile-stream "$STREAM_MF" --rm "$RM" --schema "$SCHEMA" --type "$MESH_TYPE" \
  --semantic-mesh --outdir "$WORK/dec" >"$WORK/dec.log" 2>&1 || true
NDEC=$(find "$WORK/dec" -maxdepth 1 -name '*.xml' | wc -l)
echo "      decompiled $NDEC mesh XML(s)"
[[ "$NDEC" -gt 0 ]] || { echo "  ERROR: semantic decompile produced no XML"; tail -5 "$WORK/dec.log"; exit 1; }

echo "[2/4] select sample (seed=$SEED sample=$SAMPLE all=$ALL; stratified by declaration layout)"
SAMPLE="$SAMPLE" SEED="$SEED" ALL="$ALL" DECDIR="$WORK/dec" STREAM_MF="$STREAM_MF" \
python3 "$ROOT/tools/mesh-repack-gate.py" select >"$WORK/sample.txt"
NSEL=$(wc -l <"$WORK/sample.txt")
echo "      selected $NSEL mesh(es) for recompile"

echo "[3/4] recompile the sample through W3DMeshProcessor.BuildVertexData"
c=0
while IFS= read -r xml; do
  [[ -n "$xml" ]] || continue
  cp "$WORK/dec/$xml" "$WORK/one.xml"
  ( cd "$WORK" && dotnet "$BAB" "one.xml" -dr:"$WORK" -od:"$WORK/new/c$c" -sp:"$SCHEMA" -rm:"$RM" \
      -sc:false -bc:false >>"$WORK/comp.log" 2>&1 || true )
  c=$((c+1))
done <"$WORK/sample.txt"

echo "[4/4] byte-compare the re-packed sample to the ORIGINAL shipped stream"
NEWDIR="$WORK/new" DECDIR="$WORK/dec" SAMPLE_LIST="$WORK/sample.txt" STREAM_MF="$STREAM_MF" \
python3 "$ROOT/tools/mesh-repack-gate.py" compare
