#!/usr/bin/env bash
# blender-roundtrip-gate.sh — the BLENDER EXPORTER round-trip gate (finding 0028; the
# acceptance test for the Blender exporter, NOT a regression footnote).
#
#   tools/blender-roundtrip-gate.sh --from-binary <stream.manifest> [--sample N] [--seed S]
#                                   [--graph-sample M] [--all] [--mesh-only] [--graph-only]
#
# This is the 0025 re-pack equality gate (tools/mesh-repack-gate.sh) WITH BLENDER INSERTED
# IN THE LOOP. 0025 proved `decode ∘ packer == shipped`; this proves the added delta —
#
#   shipped  --decompile --semantic-mesh-->  authoring XML
#            --Blender import--> datablocks --SAVE .blend / RELOAD (fresh process)--> --export-->  XML'
#            --compile (the SAME W3DMeshProcessor packer)-->  re-packed bytes
#            --byte-compare to shipped-->  BYTEEXACT ⇒ Blender preserved every authoring
#                                          attribute losslessly.
#
# The import→save and reload→export run as TWO SEPARATE Blender processes, so the export
# process sees ONLY the .blend files (never the decoded XML). A green therefore proves the
# Blender datablocks (saved + reloaded) carried the data — not a sidecar/decoded-file copy
# (docs/design/blender-integration.md, staging step 3; the anti-bypass property).
#
# REUSE (no second packer / comparator / sampler — CLAUDE.md invariant 3):
#   * tools/mesh-repack-gate.py  select (stratified+seeded) and compare (byte buckets)
#   * tools/compare-stream.py     stream format + the graph-type comparison (--type)
#   * openwrath_import.cli        build_compile_argv (the ONE compile invocation)
# Covers W3DMesh (incl. its <FXShader> block) AND the graph types W3DContainer /
# W3DHierarchy / W3DCollisionBox. Buckets are honest (invariant 5). The stream is
# bring-your-own; its .bin/.relo/.imp siblings must be DECOMPRESSED.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BAB="$ROOT/Debug/BinaryAssetBuilder.dll"
DEC="$ROOT/Debug/bab-decompile.dll"
SCHEMA="${KW_SCHEMA:-$ROOT/schemas/kw/xsd/CnC3Types.xsd}"
BM="${KW_BASEMANIFESTS:-$HOME/kw-mod-sdk/base-manifests}"
RM="$BM/global_common_2.manifest;$BM/static_common_2.manifest;$BM/global_english_2.manifest"
BLENDER="${BLENDER:-blender}"
GATE_PY="$ROOT/tools/blender-roundtrip-gate.py"
DRIVER="$ROOT/tools/blender_roundtrip_driver.py"

source "$ROOT/tools/verify-inputs-preflight.sh" 2>/dev/null && verify_inputs_preflight 2>/dev/null || true

if [[ "${1:-}" != "--from-binary" ]]; then
  echo "usage: tools/blender-roundtrip-gate.sh --from-binary <stream.manifest> [--sample N] [--seed S] [--graph-sample M] [--all] [--mesh-only] [--graph-only]"; exit 2
fi
STREAM_MF="${2:?--from-binary requires a <stream.manifest> path}"; shift 2
SAMPLE=40; SEED=42; GRAPH_SAMPLE=20; ALL=0; MESH_ONLY=0; GRAPH_ONLY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --sample) SAMPLE="$2"; shift 2;;
    --seed) SEED="$2"; shift 2;;
    --graph-sample) GRAPH_SAMPLE="$2"; shift 2;;
    --all) ALL=1; shift;;
    --mesh-only) MESH_ONLY=1; shift;;
    --graph-only) GRAPH_ONLY=1; shift;;
    *) echo "  WARN: ignoring unknown arg '$1'"; shift;;
  esac
done
[[ -f "$STREAM_MF" ]] || { echo "  ERROR: stream manifest not found: $STREAM_MF"; exit 1; }
command -v "$BLENDER" >/dev/null 2>&1 || { echo "  ERROR: '$BLENDER' not on PATH (set BLENDER=)"; exit 1; }

export DOTNET_ROLL_FORWARD=LatestMajor DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT

FAIL=0

# Derive TypeIds from the stream manifest (never hardcoded — invariant 3).
tid_of() { STREAM_MF="$STREAM_MF" TNAME="$1" python3 "$GATE_PY" type-tid; }
TID_MESH="$(tid_of W3DMesh)"
[[ -n "$TID_MESH" ]] || { echo "  ERROR: could not derive W3DMesh TypeId from the stream"; exit 1; }

# ---- one reusable round-trip-and-compare for a single asset TYPE -----------------------
# args: <TypeName> <TID hex> <sample-size> <select-verb> <collision 0|1> <compare-fn>
roundtrip_type() {
  local tname="$1" tid="$2" ssize="$3" selverb="$4" collision="$5"
  local D="$WORK/$tname"
  mkdir -p "$D/dec" "$D/blend" "$D/exp" "$D/new"

  echo "[$tname 1/5] decompile all $tname from the stream (semantic mesh)"
  dotnet "$DEC" decompile-stream "$STREAM_MF" --rm "$RM" --schema "$SCHEMA" --type "$tid" \
    --semantic-mesh --outdir "$D/dec" >"$D/dec.log" 2>&1 || true
  local ndec; ndec=$(find "$D/dec" -maxdepth 1 -name '*.xml' | wc -l)
  echo "        decompiled $ndec $tname XML(s)"
  [[ "$ndec" -gt 0 ]] || { echo "  ERROR: no $tname decoded"; tail -5 "$D/dec.log"; FAIL=1; return; }

  echo "[$tname 2/5] select sample (seed=$SEED size=$ssize all=$ALL)"
  SAMPLE="$ssize" SEED="$SEED" ALL="$ALL" DECDIR="$D/dec" STREAM_MF="$STREAM_MF" \
    TID="$tid" TNAME="$tname" python3 "$GATE_PY" "$selverb" >"$D/sample.txt"
  local nsel; nsel=$(wc -l <"$D/sample.txt")
  echo "        selected $nsel $tname(s)"
  [[ "$nsel" -gt 0 ]] || { echo "  ERROR: empty sample for $tname"; FAIL=1; return; }

  echo "[$tname 3/5] build Blender jobs + run import→save→RELOAD→export (two processes)"
  SAMPLE_LIST="$D/sample.txt" DECDIR="$D/dec" BLENDDIR="$D/blend" EXPDIR="$D/exp" \
    IMP_JSON="$D/imp.json" EXP_JSON="$D/exp.json" COLLISION="$collision" \
    python3 "$GATE_PY" make-jobs
  "$BLENDER" --background --python "$DRIVER" -- import-save "$D/imp.json" >"$D/imp.log" 2>&1 \
    || { echo "  ERROR: Blender import-save failed"; tail -20 "$D/imp.log"; FAIL=1; return; }
  "$BLENDER" --background --python "$DRIVER" -- load-export "$D/exp.json" >"$D/exp.log" 2>&1 \
    || { echo "  ERROR: Blender load-export failed"; tail -20 "$D/exp.log"; FAIL=1; return; }
  grep -h "tiers=" "$D/exp.log" | sed 's/^/        /'
  local nexp; nexp=$(find "$D/exp" -maxdepth 1 -name '*.xml' | wc -l)
  echo "        exported $nexp $tname XML(s)"

  echo "[$tname 4/5] recompile the exported XML through the SAME packer (cli.build_compile_argv)"
  local c=0
  while IFS= read -r xml; do
    [[ -n "$xml" ]] || continue
    if [[ -f "$D/exp/$xml" ]]; then
      ( cd "$ROOT/blender" && python3 -m openwrath_import.cli compile \
          --bab "dotnet $BAB" --xml "$D/exp/$xml" --dataroot "$D/new/c$c" \
          --outdir "$D/new/c$c" --schema "$SCHEMA" --rm "$RM" >>"$D/comp.log" 2>&1 || true )
    fi
    c=$((c+1))
  done <"$D/sample.txt"

  echo "[$tname 5/5] byte-compare recompiled-from-export to the ORIGINAL shipped stream"
  "${@:6}" "$D"
}

compare_mesh() {  # $1 = type workdir
  local D="$1"
  NEWDIR="$D/new" DECDIR="$D/dec" SAMPLE_LIST="$D/sample.txt" STREAM_MF="$STREAM_MF" \
    python3 "$GATE_PY" compare-mesh || FAIL=1
}

compare_graph() {  # $1 = type workdir — compares ONLY the sampled instances to shipped
  local D="$1"
  NEWDIR="$D/new" SAMPLE_LIST="$D/sample.txt" STREAM_MF="$STREAM_MF" \
    python3 "$GATE_PY" compare-selected || FAIL=1
}

if [[ "$GRAPH_ONLY" -eq 0 ]]; then
  echo "================= W3DMesh (geometry + FXShader) ================="
  roundtrip_type "W3DMesh" "$TID_MESH" "$SAMPLE" "select-mesh" 0 compare_mesh
fi

if [[ "$MESH_ONLY" -eq 0 ]]; then
  for tname in W3DHierarchy W3DCollisionBox W3DContainer; do
    echo
    echo "================= $tname (graph type) ================="
    GTID="$(tid_of "$tname")"
    if [[ -z "$GTID" ]]; then echo "  SKIP: no $tname in the stream"; continue; fi
    roundtrip_type "$tname" "$GTID" "$GRAPH_SAMPLE" "select-type" 0 compare_graph
  done
fi

echo
echo "========================================================================"
if [[ "$FAIL" -eq 0 ]]; then
  echo "  VERDICT: GREEN — Blender import→export→recompile is BYTE-EXACT to shipped"
  echo "           for every sampled W3DMesh (incl. FXShader) + graph type."
  echo "========================================================================"
  exit 0
else
  echo "  VERDICT: RED — see mismatches above."
  echo "========================================================================"
  exit 1
fi
