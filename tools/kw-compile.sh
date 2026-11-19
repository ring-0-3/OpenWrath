#!/usr/bin/env bash
# Compile a Kane's Wrath asset XML into a v5 manifest + binary .asset files, natively on Linux (no Wine).
#
#   tools/kw-compile.sh <input.xml-relative-to-dataroot> <output-dir>
#
# Paths are taken from the environment (run `source tools/dev-env.sh` first), with repo-relative fallbacks.
# The -rm reference manifests resolve cross-stream references (audio/art in base-game streams) so compiled
# references carry their real TypeId instead of a schema placeholder. See SETUP.md.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BAB="$ROOT/Debug/BinaryAssetBuilder.dll"
SCHEMA="${KW_SCHEMA:-$ROOT/schemas/kw/xsd/CnC3Types.xsd}"
DR="${KW_DATAROOT:?set KW_DATAROOT (or: source tools/dev-env.sh)}"
BM="${KW_BASEMANIFESTS:?set KW_BASEMANIFESTS (or: source tools/dev-env.sh)}"

IN="${1:?input xml (relative to the data root) required}"
OUT="${2:?output dir required}"
RM="$BM/global_common_2.manifest;$BM/static_common_2.manifest;$BM/global_english_2.manifest"

export DOTNET_ROLL_FORWARD=LatestMajor DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
mkdir -p "$OUT"
exec dotnet "$BAB" "$IN" -dr:"$DR" -od:"$OUT" -sp:"$SCHEMA" -rm:"$RM" -sc:false -bc:false
