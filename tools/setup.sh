#!/usr/bin/env bash
# One-command developer setup for the OpenWrath toolchain (compiler + decompiler).
#
#   tools/setup.sh                   # guided: check prereqs, wire your data, build, smoke-test
#   tools/setup.sh --non-interactive # accept detected/default values, never prompt (CI / scripts)
#   tools/setup.sh --no-build        # skip the dotnet build step
#   tools/setup.sh --help
#
# What it does, in order:
#   1. checks prerequisites (.NET SDK >= 8, python3);
#   2. finds or asks for the three data inputs you supply — the schema XSD, the SDK asset XML, and the
#      base-stream manifests — validates each, and records them in tools/dev-env.local (git-ignored);
#   3. builds source/BinaryAssetBuilder.sln;
#   4. if the data is present, runs a tiny round-trip (GlobalData/Armor.xml) as a smoke test.
#
# It writes NO game data into the repo — only paths to data you already have, in the git-ignored local file.
# On WSL it also searches Windows-side locations under /mnt/*; dotnet runs inside WSL (Linux) as usual and
# just reads those files over /mnt.
set -euo pipefail
shopt -s nullglob

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL="$ROOT/tools/dev-env.local"
DEPTH=4   # max search depth under each candidate base when auto-detecting data

# ---- options ---------------------------------------------------------------
INTERACTIVE=1
DO_BUILD=1
usage() {
    sed -n '2,19p' "$0" | sed 's/^#\( \|$\)//'
}
for a in "$@"; do
    case "$a" in
        --non-interactive|--yes|-y) INTERACTIVE=0 ;;
        --no-build)                 DO_BUILD=0 ;;
        -h|--help)                  usage; exit 0 ;;
        *) echo "setup: unknown option '$a' (try --help)" >&2; exit 2 ;;
    esac
done
# Never block waiting for input when there's no terminal (CI, pipes, </dev/null).
[ -t 0 ] || INTERACTIVE=0

# ---- pretty output ---------------------------------------------------------
if [ -t 1 ] && command -v tput >/dev/null 2>&1 && [ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]; then
    C_G="$(tput setaf 2)"; C_R="$(tput setaf 1)"; C_Y="$(tput setaf 3)"; C_B="$(tput bold)"; C_0="$(tput sgr0)"
else
    C_G=""; C_R=""; C_Y=""; C_B=""; C_0=""
fi
ok()   { printf '  %s[ok]%s   %s\n'   "$C_G" "$C_0" "$*"; }
bad()  { printf '  %s[FAIL]%s %s\n'   "$C_R" "$C_0" "$*"; }
warn() { printf '  %s[skip]%s %s\n'   "$C_Y" "$C_0" "$*"; }
hdr()  { printf '\n%s== %s ==%s\n'    "$C_B" "$*" "$C_0"; }

# ---- state -----------------------------------------------------------------
PREREQ_OK=1
DOTNET_OK=0
BUILD_OK=0
SMOKE_OK=0
RES_SCHEMA=""
RES_DATAROOT=""
RES_BASEMANIFESTS=""

# ---- WSL detection ---------------------------------------------------------
is_wsl() {
    case "$(uname -r 2>/dev/null)" in
        *[Mm]icrosoft*|*[Ww][Ss][Ll]*) return 0 ;;
    esac
    grep -qiE 'microsoft|wsl' /proc/version 2>/dev/null
}

# ---- prerequisites ---------------------------------------------------------
check_prereqs() {
    hdr "Prerequisites"
    if command -v dotnet >/dev/null 2>&1; then
        local v maj
        v="$(dotnet --version 2>/dev/null || echo '')"
        maj="${v%%.*}"
        if [[ "$maj" =~ ^[0-9]+$ ]] && [ "$maj" -ge 8 ]; then
            DOTNET_OK=1
            ok ".NET SDK $v"
            if [ "$maj" -gt 8 ]; then
                warn "installed .NET major is $maj; projects target net8.0 — DOTNET_ROLL_FORWARD=LatestMajor handles this (set for you by this script and dev-env.sh)."
            fi
        else
            PREREQ_OK=0
            bad ".NET SDK '$v' found, but 8.0+ is required. Install .NET SDK 8 or newer: https://dotnet.microsoft.com/download"
        fi
    else
        PREREQ_OK=0
        bad ".NET SDK not found. Install 8.0+ from https://dotnet.microsoft.com/download $(is_wsl && echo '(install it INSIDE WSL).')"
    fi
    if command -v python3 >/dev/null 2>&1; then
        ok "python3 $(python3 --version 2>&1 | awk '{print $2}')"
    else
        PREREQ_OK=0
        bad "python3 not found (needed by tools/roundtrip.sh). Install python3."
    fi
    return 0
}

# ---- detection helpers -----------------------------------------------------
# find_first <name> <base>...  -> first matching FILE path, or nonzero
find_first() {
    local name="$1" base hit; shift
    for base in "$@"; do
        [ -d "$base" ] || continue
        hit="$(find "$base" -maxdepth "$DEPTH" -type f -name "$name" -print 2>/dev/null | head -n1)"
        [ -n "$hit" ] && { printf '%s\n' "$hit"; return 0; }
    done
    return 1
}
# find_first_dir <name> <base>...  -> first matching DIR path, or nonzero
find_first_dir() {
    local name="$1" base hit; shift
    for base in "$@"; do
        [ -d "$base" ] || continue
        hit="$(find "$base" -maxdepth "$DEPTH" -type d -name "$name" -print 2>/dev/null | head -n1)"
        [ -n "$hit" ] && { printf '%s\n' "$hit"; return 0; }
    done
    return 1
}
# The curated set of places to look for the user's data (never scans all of $HOME).
search_bases() {
    local b=() d u
    b+=("$ROOT/schemas" "$HOME/kw-mod-sdk" "$HOME/cnc-kw-sdk" "$HOME/cnc-kw-godmod" \
        "$HOME/Downloads" "$HOME/Documents")
    if is_wsl && [ -d /mnt ]; then
        for d in /mnt/*/; do
            [ -d "$d" ] || continue
            b+=("${d}kw-mod-sdk" "${d}cnc-kw-sdk")
            for u in "${d}Users"/*/; do
                [ -d "$u" ] || continue
                b+=("${u}kw-mod-sdk" "${u}cnc-kw-sdk" "${u}Downloads" "${u}Documents")
            done
        done
    fi
    printf '%s\n' "${b[@]}"
}

detect_schema() {
    # Prefer the repo's own kw schema, then any .../kw/xsd/CnC3Types.xsd, then any CnC3Types.xsd.
    [ -f "$ROOT/schemas/kw/xsd/CnC3Types.xsd" ] && { printf '%s\n' "$ROOT/schemas/kw/xsd/CnC3Types.xsd"; return 0; }
    local base hits kw
    for base in "$@"; do
        [ -d "$base" ] || continue
        hits="$(find "$base" -maxdepth "$DEPTH" -type f -name CnC3Types.xsd 2>/dev/null)"
        [ -z "$hits" ] && continue
        kw="$(printf '%s\n' "$hits" | grep '/kw/xsd/' | head -n1)"
        [ -n "$kw" ] && { printf '%s\n' "$kw"; return 0; }
        printf '%s\n' "$hits" | head -n1
        return 0
    done
    return 1
}

detect_basemanifests() {
    local mf
    mf="$(find_first 'static_common_2.manifest' "$@")" \
        || mf="$(find_first 'global_common_2.manifest' "$@")" \
        || mf=""
    if [ -n "$mf" ]; then dirname "$mf"; return 0; fi
    find_first_dir 'base-manifests' "$@"
}

# ---- validators ------------------------------------------------------------
valid_schema()   { [ -f "$1" ] && [ "$(basename "$1")" = "CnC3Types.xsd" ]; }
valid_basemanifests() { [ -d "$1" ] && compgen -G "$1/*.manifest" >/dev/null 2>&1; }
valid_dataroot() {
    local c="$1"
    [ -d "$c" ] || return 1
    [ -d "$c/KanesWrathXMLFiles" ] && return 0
    { [ -d "$c/GlobalData" ] || [ -d "$c/GDI" ]; } && return 0
    compgen -G "$c/*.xml" >/dev/null 2>&1
}
# If the user points at an SDK root that contains KanesWrathXMLFiles, store the inner dir (the real -dr).
normalize_dataroot() {
    local c="$1"
    if [ -d "$c/KanesWrathXMLFiles" ]; then printf '%s\n' "$c/KanesWrathXMLFiles"; else printf '%s\n' "$c"; fi
}

# ---- resolve one input: honour env/local -> detected -> prompt --------------
# wire_input <label> <current> <detected> <validator-fn> <hint>  -> echoes resolved path (or "")
wire_input() {
    local label="$1" cur="$2" det="$3" vfn="$4" hint="$5" val="" reply tries=0
    if [ -n "$cur" ] && "$vfn" "$cur"; then val="$cur"; fi
    if [ -z "$val" ] && [ -n "$det" ] && "$vfn" "$det"; then val="$det"; fi

    if [ "$INTERACTIVE" = 0 ]; then
        printf '%s\n' "$val"
        return 0
    fi

    if [ -n "$val" ]; then
        printf '  %s found: %s\n' "$label" "$val" >&2
        read -r -p "  use this? [Y/n] or type a path: " reply </dev/tty || reply=""
        case "$reply" in
            ""|[Yy]|[Yy][Ee][Ss]) : ;;
            *) val="$reply" ;;
        esac
    else
        printf '  %s not found. %s\n' "$label" "$hint" >&2
        read -r -p "  enter path (blank to skip): " reply </dev/tty || reply=""
        val="$reply"
    fi

    while [ -n "$val" ] && ! "$vfn" "$val"; do
        printf '  not valid for %s: %s\n' "$label" "$val" >&2
        tries=$((tries + 1))
        [ "$tries" -ge 3 ] && { val=""; break; }
        read -r -p "  enter a valid path (blank to skip): " reply </dev/tty || reply=""
        val="$reply"
    done
    printf '%s\n' "$val"
}

# ---- write the git-ignored machine config ----------------------------------
# quote_path <abs-path> -> shell-quoted, with a leading $HOME folded back to literal $HOME
quote_path() {
    local p="$1"
    # The single-quoted printf templates are intentional: we want the literal text $HOME written to the file.
    # shellcheck disable=SC2016
    case "$p" in
        "$HOME"/*) printf '"$HOME/%s"' "${p#"$HOME"/}" ;;
        "$HOME")   printf '"$HOME"' ;;
        *)         printf '"%s"' "$p" ;;
    esac
}
write_local() {
    local tmp
    tmp="$(mktemp)"
    {
        printf '# Machine-local paths for the OpenWrath toolchain (git-ignored).\n'
        printf '# Generated by tools/setup.sh on %s. Edit freely; re-run setup.sh to regenerate.\n' "$(date +%Y-%m-%d)"
        printf '# Sourced by tools/dev-env.sh; any value left unset falls back to dev-env.sh defaults.\n\n'
        [ -n "$RES_DATAROOT" ]      && printf 'KW_DATAROOT=%s\n'      "$(quote_path "$RES_DATAROOT")"
        [ -n "$RES_BASEMANIFESTS" ] && printf 'KW_BASEMANIFESTS=%s\n' "$(quote_path "$RES_BASEMANIFESTS")"
        # Only record KW_SCHEMA when it is NOT the repo's own schemas/ copy (which dev-env.sh resolves by default).
        if [ -n "$RES_SCHEMA" ] && [ "$RES_SCHEMA" != "$ROOT/schemas/kw/xsd/CnC3Types.xsd" ]; then
            printf 'KW_SCHEMA=%s\n' "$(quote_path "$RES_SCHEMA")"
        fi
    } >"$tmp"
    mv "$tmp" "$LOCAL"
}

# ---- data wiring -----------------------------------------------------------
wire_data() {
    hdr "Data inputs"

    # Pre-populate "current" values from an existing dev-env.local (idempotent re-runs) and the environment.
    local cur_schema="${KW_SCHEMA:-}" cur_dr="${KW_DATAROOT:-}" cur_bm="${KW_BASEMANIFESTS:-}" cur_sdk="${KW_SDK:-}"
    if [ -f "$LOCAL" ]; then
        # Read the existing local file in a subshell so it can't pollute our environment, then capture each
        # value on its own line (so unset values stay as empty lines in their correct positions).
        local loaded=()
        # shellcheck source=/dev/null
        mapfile -t loaded < <( ( set +u; . "$LOCAL" >/dev/null 2>&1; printf '%s\n' \
            "${KW_SCHEMA:-}" "${KW_DATAROOT:-}" "${KW_BASEMANIFESTS:-}" "${KW_SDK:-}" ) || true )
        [ -z "$cur_schema" ] && cur_schema="${loaded[0]:-}"
        [ -z "$cur_dr" ]     && cur_dr="${loaded[1]:-}"
        [ -z "$cur_bm" ]     && cur_bm="${loaded[2]:-}"
        [ -z "$cur_sdk" ]    && cur_sdk="${loaded[3]:-}"
    fi
    # Derive a dataroot from a known SDK root if we have one but no explicit dataroot.
    [ -z "$cur_dr" ] && [ -n "$cur_sdk" ] && [ -d "$cur_sdk/KanesWrathXMLFiles" ] && cur_dr="$cur_sdk/KanesWrathXMLFiles"

    # shellcheck disable=SC2016  # literal "$HOME" is intended in this message
    printf '  searching common locations under $HOME%s ...\n' "$(is_wsl && echo ' and /mnt/*')"
    local bases=()
    mapfile -t bases < <(search_bases)

    local det_schema det_dr det_bm
    det_schema="$(detect_schema "${bases[@]}")"                 || det_schema=""
    det_dr="$(find_first_dir KanesWrathXMLFiles "${bases[@]}")"  || det_dr=""
    det_bm="$(detect_basemanifests "${bases[@]}")"              || det_bm=""

    RES_SCHEMA="$(wire_input 'schema (CnC3Types.xsd)' "$cur_schema" "$det_schema" valid_schema \
        'Point it at the CnC3Types.xsd from your Mod SDK.')"
    RES_DATAROOT="$(wire_input 'data root (KanesWrathXMLFiles)' "$cur_dr" "$det_dr" valid_dataroot \
        'Point it at your KanesWrathXMLFiles dir (or the SDK dir that contains it).')"
    [ -n "$RES_DATAROOT" ] && RES_DATAROOT="$(normalize_dataroot "$RES_DATAROOT")"
    RES_BASEMANIFESTS="$(wire_input 'base manifests (*.manifest)' "$cur_bm" "$det_bm" valid_basemanifests \
        'Point it at the dir holding your decompressed base-stream *.manifest files.')"

    write_local
    printf '\n'
    if [ -n "$RES_SCHEMA" ];        then ok "schema       -> $RES_SCHEMA";          else warn "schema not set"; fi
    if [ -n "$RES_DATAROOT" ];      then ok "data root    -> $RES_DATAROOT";        else warn "data root not set"; fi
    if [ -n "$RES_BASEMANIFESTS" ]; then ok "base manifests -> $RES_BASEMANIFESTS"; else warn "base manifests not set"; fi
    printf '  recorded in %s\n' "$LOCAL"
    return 0
}

# ---- build -----------------------------------------------------------------
do_build() {
    hdr "Build"
    if [ "$DO_BUILD" = 0 ]; then warn "skipped (--no-build)"; return 0; fi
    if [ "$DOTNET_OK" != 1 ]; then bad "skipping build: .NET SDK 8+ not available (see Prerequisites)."; return 0; fi
    export DOTNET_ROLL_FORWARD=LatestMajor DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
    local log
    log="$(mktemp)"
    printf '  building source/BinaryAssetBuilder.sln (Debug, x64) ...\n'
    if dotnet build "$ROOT/source/BinaryAssetBuilder.sln" -c Debug -p:Platform=x64 >"$log" 2>&1; then
        ok "build succeeded"
        rm -f "$log"
        BUILD_OK=1
    else
        bad "build failed — last lines:"
        tail -n 25 "$log" | sed 's/^/      /'
        printf '      (full log: %s)\n' "$log"
        BUILD_OK=0
    fi
    return 0
}

# ---- smoke test ------------------------------------------------------------
smoke_test() {
    hdr "Smoke test (round-trip)"
    if [ "$BUILD_OK" != 1 ]; then
        warn "skipped: a successful build is required first."
        return 0
    fi
    if [ -z "$RES_SCHEMA" ] || [ -z "$RES_DATAROOT" ] || [ -z "$RES_BASEMANIFESTS" ]; then
        warn "skipped: data inputs incomplete. Once you have them, run:"
        printf '      source tools/dev-env.sh && tools/roundtrip.sh GlobalData/Armor.xml\n'
        return 0
    fi
    printf '  running tools/roundtrip.sh GlobalData/Armor.xml ...\n'
    if ( set +u +e; . "$ROOT/tools/dev-env.sh" >/dev/null 2>&1; "$ROOT/tools/roundtrip.sh" GlobalData/Armor.xml ); then
        ok "round-trip passed (GlobalData/Armor.xml)"
        SMOKE_OK=1
    else
        bad "round-trip did not pass. Run it directly to see details:"
        printf '      source tools/dev-env.sh && tools/roundtrip.sh GlobalData/Armor.xml\n'
        SMOKE_OK=0
    fi
    return 0
}

# ---- summary ---------------------------------------------------------------
summary() {
    hdr "Summary"
    if [ "$PREREQ_OK" = 1 ]; then ok "prerequisites"; else bad "prerequisites — install the missing tool(s) above"; fi
    if [ -n "$RES_SCHEMA" ] && [ -n "$RES_DATAROOT" ] && [ -n "$RES_BASEMANIFESTS" ]; then
        ok "data wired (tools/dev-env.local)"
    else
        warn "data incomplete — edit tools/dev-env.local or re-run tools/setup.sh"
    fi
    if [ "$DO_BUILD" = 0 ]; then
        warn "build not run (--no-build)"
    elif [ "$BUILD_OK" = 1 ]; then
        ok "build"
    else
        bad "build — see errors above"
    fi
    if [ "$SMOKE_OK" = 1 ]; then
        ok "smoke test"
    fi

    printf '\n%sNext:%s\n' "$C_B" "$C_0"
    printf '  source tools/dev-env.sh                 # load your data paths into this shell\n'
    printf '  tools/roundtrip.sh GlobalData/Armor.xml # the correctness gate (expect 207/207)\n'
    printf '  see SETUP.md for compile/decompile usage and the full reference.\n'
    return 0
}

# ---- main ------------------------------------------------------------------
printf '%sOpenWrath developer setup%s\n' "$C_B" "$C_0"
[ "$INTERACTIVE" = 0 ] && printf '  (non-interactive: accepting detected/default values)\n'
check_prereqs
wire_data
do_build
smoke_test
summary
