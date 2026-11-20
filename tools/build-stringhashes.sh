#!/usr/bin/env bash
# Build a MASTER StringHashes.xml reverse table from your own SDK XML corpus.
#
#   tools/build-stringhashes.sh <out.xml> [file1.xml file2.xml ...]   # source paths relative to $KW_DATAROOT
#
# Some values are stored in compiled assets only as one-way hashes (module `id` tags, `StringHash` fields,
# asset ids/refs). The decompiler can recover the original strings only from a reverse table. The compiler
# emits one (StringHashes.xml) per build via `-scd:<dir>`.
#
# Under the VERSION5 format this toolchain targets, a compiler process OVERWRITES rather than accumulates its
# table, so compiling many files through one shared dir keeps only the last file's strings. To cover the whole
# corpus this script compiles EACH source file into its OWN output dir, then UNIONS every emitted table into a
# single master with tools/merge-stringhashes.py (keyed on hash; genuine hash collisions are logged + counted).
#
# A monolithic include (e.g. global.xml / Static.xml) aborts the whole build if any one included file uses a
# type this port does not yet model, which would starve the harvest; compiling file-by-file isolates those so
# every other file still contributes. Per-file nonzero exit codes are expected and tolerated (the trailing
# StringHashTable-asset compile step exits nonzero AFTER the table is written).
#
# With no file list, every *.xml under $KW_DATAROOT is harvested. Run `source tools/dev-env.sh` first.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BAB="$ROOT/Debug/BinaryAssetBuilder.dll"
SCHEMA="${KW_SCHEMA:-$ROOT/schemas/kw/xsd/CnC3Types.xsd}"
DR="${KW_DATAROOT:?set KW_DATAROOT (source tools/dev-env.sh)}"
BM="${KW_BASEMANIFESTS:?set KW_BASEMANIFESTS (source tools/dev-env.sh)}"
RM="$BM/global_common_2.manifest;$BM/static_common_2.manifest;$BM/global_english_2.manifest"
export DOTNET_ROLL_FORWARD=LatestMajor DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1

OUT="${1:?output path for the master StringHashes.xml}"; shift || true
FILES=("$@")
if [[ ${#FILES[@]} -eq 0 ]]; then
  mapfile -t FILES < <(cd "$DR" && find . -name '*.xml' | sed 's#^\./##' | sort)
fi

HARVEST="$(mktemp -d)"
trap 'rm -rf "$HARVEST"' EXIT
echo "harvesting StringHashes from ${#FILES[@]} source files ..."
i=0; wrote=0
for SRC in "${FILES[@]}"; do
  i=$((i+1))
  d="$HARVEST/h$i"; mkdir -p "$d"
  timeout 600 dotnet "$BAB" "$SRC" -dr:"$DR" -od:"$d/_out" -sp:"$SCHEMA" -rm:"$RM" -sc:false -bc:false -scd:"$d" >/dev/null 2>&1 || true
  rm -rf "$d/_out"
  [[ -f "$d/StringHashes.xml" ]] && wrote=$((wrote+1))
  [[ $((i % 100)) -eq 0 ]] && echo "  ...$i/${#FILES[@]} ($wrote tables)"
done
echo "$wrote/${#FILES[@]} files emitted a table; merging ..."
python3 "$ROOT/tools/merge-stringhashes.py" "$OUT" "$HARVEST"
