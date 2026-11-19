#!/usr/bin/env bash
# Build a MASTER StringHashes.xml.
#
#   tools/build-stringhashes.sh <cache-dir> [file1.xml file2.xml ...]   # paths relative to $KW_DATAROOT
#
# Some values are stored in compiled assets only as one-way hashes (module `id` tags, `StringHash` fields).
# The decompiler can recover the original strings only from a reverse table. The compiler emits one
# (StringHashes.xml) per build via `-scd:<dir>`, and — because it LOADS any existing StringHashes.xml in that
# dir before adding to it — compiling many source files through the SAME cache dir ACCUMULATES them into one
# master table. Pass the result to `bab-decompile ... --stringhashes <cache>/StringHashes.xml` to recover the
# inherited id/StringHash strings that a single-file compile can't see.
#
# Run `source tools/dev-env.sh` first.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BAB="$ROOT/Debug/BinaryAssetBuilder.dll"
SCHEMA="${KW_SCHEMA:-$ROOT/schemas/kw/xsd/CnC3Types.xsd}"
DR="${KW_DATAROOT:?set KW_DATAROOT (source tools/dev-env.sh)}"
BM="${KW_BASEMANIFESTS:?set KW_BASEMANIFESTS (source tools/dev-env.sh)}"
RM="$BM/global_common_2.manifest;$BM/static_common_2.manifest;$BM/global_english_2.manifest"
export DOTNET_ROLL_FORWARD=LatestMajor DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1

CACHE="${1:?cache/output dir for the master StringHashes.xml}"; shift
FILES=("$@")
mkdir -p "$CACHE"
echo "accumulating StringHashes from ${#FILES[@]} files into $CACHE ..."
i=0
for SRC in "${FILES[@]}"; do
  i=$((i+1))
  dotnet "$BAB" "$SRC" -dr:"$DR" -od:"$CACHE/_out" -sp:"$SCHEMA" -rm:"$RM" -sc:false -bc:false -scd:"$CACHE" >/dev/null 2>&1 || true
  [[ $((i % 25)) -eq 0 ]] && echo "  ...$i/${#FILES[@]}"
done
if [[ -f "$CACHE/StringHashes.xml" ]]; then
  echo "master -> $CACHE/StringHashes.xml ($(wc -c < "$CACHE/StringHashes.xml") bytes)"
else
  echo "WARNING: no StringHashes.xml was produced (did any file compile?)"
fi
