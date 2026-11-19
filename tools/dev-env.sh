#!/usr/bin/env bash
# Development environment wiring for the Kane's Wrath toolchain.
#
#   source tools/dev-env.sh
#
# This repo ships only our MIT code and git-ignores all EA / Mod-SDK data (schemas, SDK XML, base-game
# manifests) — see SETUP.md. This script re-connects a working tree to YOUR LOCAL copy of that data so the
# compiler, decompiler, and tools/roundtrip.sh "just work" during development. It:
#   1. loads machine-specific paths from tools/dev-env.local (git-ignored) if present, else uses the defaults
#      below (override any of them via dev-env.local or by exporting before sourcing);
#   2. symlinks schemas/ into the repo from your schema source if the repo copy is absent (e.g. a fresh clone);
#   3. exports KW_DATAROOT / KW_BASEMANIFESTS / KW_SCHEMA (consumed by tools/roundtrip.sh and documented in
#      SETUP.md) plus the dotnet roll-forward flags;
#   4. validates each path and prints a status line.
#
# It contains NO EA content — only paths pointing at data you already own. Safe to commit.

# Resolve repo root whether sourced from bash or zsh.
_dev_src="${BASH_SOURCE[0]:-${(%):-%x}}"
KWT_ROOT="$(cd "$(dirname "$_dev_src")/.." && pwd)"

# 1) machine-specific overrides (git-ignored)
[ -f "$KWT_ROOT/tools/dev-env.local" ] && . "$KWT_ROOT/tools/dev-env.local"

# Defaults — override in tools/dev-env.local
: "${KW_SDK:=$HOME/kw-mod-sdk}"                              # the Kane's Wrath Mod SDK checkout
: "${KW_DATAROOT:=$KW_SDK/KanesWrathXMLFiles}"              # SDK asset XML (compiler data root)
: "${KW_BASEMANIFESTS:=$HOME/kw-mod-sdk/base-manifests}" # RefPack-decompressed base-stream manifests (-rm)
: "${KW_SCHEMA_SRC:=}"                                       # dir that CONTAINS kw/xsd/CnC3Types.xsd (for symlink)

# 2) ensure schemas/ exists in the repo (it is git-ignored, so a fresh clone won't have it)
if [ ! -e "$KWT_ROOT/schemas/kw/xsd/CnC3Types.xsd" ]; then
    if [ -n "$KW_SCHEMA_SRC" ] && [ -e "$KW_SCHEMA_SRC/kw/xsd/CnC3Types.xsd" ]; then
        ln -sfn "$KW_SCHEMA_SRC" "$KWT_ROOT/schemas"
        echo "dev-env: linked schemas/ -> $KW_SCHEMA_SRC"
    fi
fi
: "${KW_SCHEMA:=$KWT_ROOT/schemas/kw/xsd/CnC3Types.xsd}"     # root XSD passed as -sp / --schema

# 3) export for the toolchain + harness
export KW_DATAROOT KW_BASEMANIFESTS KW_SCHEMA
export DOTNET_ROLL_FORWARD=LatestMajor DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1

# 4) validate + report
_dev_ok=1
_chk() { if [ -e "$2" ]; then echo "  [ok]   $1 = $2"; else echo "  [MISS] $1 = $2"; _dev_ok=0; fi; }
echo "dev-env: Kane's Wrath toolchain ($KWT_ROOT)"
_chk "KW_SCHEMA      " "$KW_SCHEMA"
_chk "KW_DATAROOT    " "$KW_DATAROOT"
_chk "KW_BASEMANIFESTS" "$KW_BASEMANIFESTS"
if [ "$_dev_ok" = 1 ]; then
    echo "dev-env: ready. Try:  tools/roundtrip.sh GlobalData/Armor.xml"
else
    echo "dev-env: some data is missing. Set paths in tools/dev-env.local (see tools/dev-env.local.example)."
fi
unset _dev_src _dev_ok
