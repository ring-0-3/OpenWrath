#!/usr/bin/env bash
# Shell-side tests for the OpenWrath onboarding scripts: tools/setup.sh and tools/dev-env.sh.
#
#   bash tests/test_shell.sh
#
# CI-safe: every test runs against SYNTHETIC fixtures (fake directory trees) inside a private
# tmpdir with an isolated $HOME, and against COPIES of the scripts in a throwaway repo tree, so
# the real tools/dev-env.local, the real $HOME, and the user's data are never touched. Nothing
# here needs the EA Mod SDK, real game data, or a .NET build. Steps that genuinely would (the
# dotnet build + round-trip) are exercised only indirectly via --no-build and are documented as
# CI-excluded in tests/README.md.
#
# WSL coverage: dev-env.sh / setup.sh hard-code /mnt for the Windows-side search, so the "it picks
# up /mnt/<drive>/... paths" assertions run inside a bubblewrap (bwrap) sandbox that binds a fake
# /mnt. When bwrap is unavailable the pickup assertions SKIP cleanly (the non-destructive WSL
# fallback is still proven without it, and the Python suite covers the WSL logic in full).

set -u
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SETUP="$REPO_ROOT/tools/setup.sh"
DEVENV="$REPO_ROOT/tools/dev-env.sh"

P=0; F=0; S=0
pass() { printf '  PASS  %s\n' "$1"; P=$((P + 1)); }
fail() { printf '  FAIL  %s: %s\n' "$1" "${2:-}"; F=$((F + 1)); }
skip() { printf '  SKIP  %s: %s\n' "$1" "${2:-}"; S=$((S + 1)); }

# contains <haystack> <needle> -> 0 if needle is a substring
contains() { case "$1" in *"$2"*) return 0 ;; *) return 1 ;; esac; }

# A fresh throwaway "repo" (tools/ holding copies of the scripts + an empty source/) and an empty
# fake $HOME. Echoes the base dir; caller rm -rf's it.
new_sandbox() {
    local base
    base="$(mktemp -d "${TMPDIR:-/tmp}/openwrath-sh.XXXXXX")"
    mkdir -p "$base/repo/tools" "$base/repo/source" "$base/home"
    cp "$SETUP" "$DEVENV" "$base/repo/tools/"
    printf '%s\n' "$base"
}

# A fake uname that reports a WSL kernel for `-r` (used to force the WSL code path on a non-WSL host).
make_fake_uname() {
    local dir="$1"
    mkdir -p "$dir"
    cat > "$dir/uname" <<'EOF'
#!/usr/bin/env bash
[ "$1" = "-r" ] && { echo "5.15.0-microsoft-standard-WSL2"; exit 0; }
echo microsoft
EOF
    chmod +x "$dir/uname"
}

# True if bwrap can bind a fake /mnt (needed for the WSL pickup assertions).
BWRAP_PROBE_DONE=0; BWRAP_OK=0
bwrap_ok() {
    if [ "$BWRAP_PROBE_DONE" = 1 ]; then return "$((1 - BWRAP_OK))"; fi
    BWRAP_PROBE_DONE=1
    command -v bwrap >/dev/null 2>&1 || return 1
    local src; src="$(mktemp -d "${TMPDIR:-/tmp}/bwrap-probe.XXXXXX")"
    if bwrap --ro-bind /nix /nix --ro-bind /etc /etc --ro-bind /run /run --bind "$src" /mnt \
             --proc /proc --dev /dev "$(command -v bash)" -c 'true' 2>/dev/null; then
        BWRAP_OK=1
    fi
    rm -rf "$src"
    return "$((1 - BWRAP_OK))"
}

# ---------------------------------------------------------------------------------------------
# 1. Syntax checks (both scripts, both shells; dev-env.sh is documented dual-shell).
# ---------------------------------------------------------------------------------------------
t_syntax() {
    local sh f ok=1
    for sh in bash zsh; do
        command -v "$sh" >/dev/null 2>&1 || { skip "syntax: $sh -n" "$sh not installed"; continue; }
        for f in "$SETUP" "$DEVENV"; do
            if "$sh" -n "$f" 2>/dev/null; then
                pass "syntax: $sh -n $(basename "$f")"
            else
                fail "syntax: $sh -n $(basename "$f")" "parse error"
                ok=0
            fi
        done
    done
    return "$ok"
}

# ---------------------------------------------------------------------------------------------
# 2. setup.sh --help exits 0 and prints the usage banner.
# ---------------------------------------------------------------------------------------------
t_setup_help() {
    local out rc
    out="$(bash "$SETUP" --help 2>&1)"; rc=$?
    if [ "$rc" -ne 0 ]; then fail "setup --help exits 0" "rc=$rc"; return; fi
    if contains "$out" "One-command developer setup"; then
        pass "setup --help exits 0 and prints usage"
    else
        fail "setup --help exits 0 and prints usage" "banner missing"
    fi
}

# ---------------------------------------------------------------------------------------------
# 3. setup.sh does NOT hang on a non-TTY and returns 0 (stdin from /dev/null, no --non-interactive).
# ---------------------------------------------------------------------------------------------
t_setup_no_hang() {
    local base rc
    base="$(new_sandbox)"
    HOME="$base/home" timeout 30 bash "$base/repo/tools/setup.sh" --no-build </dev/null >/dev/null 2>&1
    rc=$?
    rm -rf "$base"
    if [ "$rc" -eq 124 ]; then
        fail "setup non-TTY does not hang" "timed out"
    elif [ "$rc" -eq 0 ]; then
        pass "setup non-TTY returns without hanging"
    else
        fail "setup non-TTY does not hang" "rc=$rc"
    fi
}

# ---------------------------------------------------------------------------------------------
# 4. setup.sh detects a synthetic SDK/schema/manifests tree and writes a correct dev-env.local
#    into the throwaway repo (never the real one).
# ---------------------------------------------------------------------------------------------
t_setup_writes_local() {
    local base h local_file out rc
    base="$(new_sandbox)"
    h="$base/home"
    mkdir -p "$h/kw-mod-sdk/kw/xsd" "$h/kw-mod-sdk/KanesWrathXMLFiles/GlobalData" "$h/kw-mod-sdk/base-manifests"
    echo '<xsd/>' > "$h/kw-mod-sdk/kw/xsd/CnC3Types.xsd"
    printf '\0\0' > "$h/kw-mod-sdk/base-manifests/static_common_2.manifest"

    out="$(HOME="$h" bash "$base/repo/tools/setup.sh" --non-interactive --no-build </dev/null 2>&1)"; rc=$?
    local_file="$base/repo/tools/dev-env.local"

    if [ "$rc" -ne 0 ]; then fail "setup writes dev-env.local" "rc=$rc"; rm -rf "$base"; return; fi
    if [ ! -f "$local_file" ]; then fail "setup writes dev-env.local" "file not created"; rm -rf "$base"; return; fi

    local body; body="$(cat "$local_file")"
    local ok=1
    # $HOME is folded back to the literal token $HOME by quote_path, so assert on the literal text.
    contains "$body" 'KW_DATAROOT="$HOME/kw-mod-sdk/KanesWrathXMLFiles"'   || { fail "setup dev-env.local KW_DATAROOT" "got: $body"; ok=0; }
    contains "$body" 'KW_BASEMANIFESTS="$HOME/kw-mod-sdk/base-manifests"'  || { fail "setup dev-env.local KW_BASEMANIFESTS" "got: $body"; ok=0; }
    contains "$body" 'KW_SCHEMA="$HOME/kw-mod-sdk/kw/xsd/CnC3Types.xsd"'   || { fail "setup dev-env.local KW_SCHEMA" "got: $body"; ok=0; }
    # The written file must round-trip through dev-env.sh: source it in the sandbox repo and confirm
    # the three vars export to the real fixture paths (proving quote_path's $HOME folding is correct).
    if [ "$ok" = 1 ]; then
        local rt
        rt="$(HOME="$h" bash -c 'source "'"$base"'/repo/tools/dev-env.sh" >/dev/null 2>&1; printf "%s\n%s\n%s\n" "$KW_DATAROOT" "$KW_BASEMANIFESTS" "$KW_SCHEMA"')"
        if contains "$rt" "$h/kw-mod-sdk/KanesWrathXMLFiles" && contains "$rt" "$h/kw-mod-sdk/base-manifests"; then
            pass "setup detects fixtures and writes a correct, sourceable dev-env.local"
        else
            fail "setup dev-env.local round-trip" "resolved: $rt"
        fi
    fi
    rm -rf "$base"
}

# ---------------------------------------------------------------------------------------------
# 5. dev-env.sh path resolution: env overrides win, report distinguishes present vs missing.
# ---------------------------------------------------------------------------------------------
t_devenv_resolution() {
    local base h out
    base="$(new_sandbox)"; h="$base/home"
    mkdir -p "$base/repo/schemas/kw/xsd" "$base/fix/dataroot/GlobalData"
    echo '<xsd/>' > "$base/repo/schemas/kw/xsd/CnC3Types.xsd"

    out="$(HOME="$h" KW_SCHEMA="$base/repo/schemas/kw/xsd/CnC3Types.xsd" \
           KW_DATAROOT="$base/fix/dataroot" KW_BASEMANIFESTS="$base/fix/NOPE" \
           bash -c 'source "'"$base"'/repo/tools/dev-env.sh" 2>&1; echo "EXP|$KW_SCHEMA|$KW_DATAROOT|$KW_BASEMANIFESTS"')"

    local ok=1
    contains "$out" "[ok]   KW_SCHEMA" || { fail "dev-env report present schema" "$out"; ok=0; }
    contains "$out" "[ok]   KW_DATAROOT" || { fail "dev-env report present dataroot" "$out"; ok=0; }
    contains "$out" "[MISS] KW_BASEMANIFESTS" || { fail "dev-env report missing basemanifests" "$out"; ok=0; }
    contains "$out" "some data is missing" || { fail "dev-env summary flags missing data" "$out"; ok=0; }
    contains "$out" "EXP|$base/repo/schemas/kw/xsd/CnC3Types.xsd|$base/fix/dataroot|$base/fix/NOPE" \
        || { fail "dev-env exports env-overridden vars verbatim" "$out"; ok=0; }
    [ "$ok" = 1 ] && pass "dev-env.sh resolves env overrides and reports present/missing"
    rm -rf "$base"
}

# All three present -> "ready".
t_devenv_ready() {
    local base h out
    base="$(new_sandbox)"; h="$base/home"
    mkdir -p "$base/repo/schemas/kw/xsd" "$base/fix/dataroot/GlobalData" "$base/fix/bm"
    echo '<xsd/>' > "$base/repo/schemas/kw/xsd/CnC3Types.xsd"
    out="$(HOME="$h" KW_SCHEMA="$base/repo/schemas/kw/xsd/CnC3Types.xsd" \
           KW_DATAROOT="$base/fix/dataroot" KW_BASEMANIFESTS="$base/fix/bm" \
           bash -c 'source "'"$base"'/repo/tools/dev-env.sh" 2>&1')"
    if contains "$out" "dev-env: ready" && ! contains "$out" "[MISS]"; then
        pass "dev-env.sh reports ready when all three inputs exist"
    else
        fail "dev-env.sh ready state" "$out"
    fi
    rm -rf "$base"
}

# ---------------------------------------------------------------------------------------------
# 6. WSL fallback is NON-DESTRUCTIVE: forcing WSL (fake uname) with no /mnt must leave the native
#    $HOME defaults intact (no bwrap needed).
# ---------------------------------------------------------------------------------------------
t_devenv_wsl_nondestructive() {
    local base h out
    base="$(new_sandbox)"; h="$base/home"
    mkdir -p "$base/repo/schemas/kw/xsd" "$base/fakebin"
    echo '<xsd/>' > "$base/repo/schemas/kw/xsd/CnC3Types.xsd"
    make_fake_uname "$base/fakebin"
    out="$(HOME="$h" PATH="$base/fakebin:$PATH" \
           bash -c 'source "'"$base"'/repo/tools/dev-env.sh" >/dev/null 2>&1; echo "$KW_DATAROOT|$KW_BASEMANIFESTS"')"
    if contains "$out" "$h/kw-mod-sdk/KanesWrathXMLFiles" && contains "$out" "$h/kw-mod-sdk/base-manifests"; then
        pass "dev-env.sh WSL fallback is additive (native defaults kept when /mnt absent)"
    else
        fail "dev-env.sh WSL non-destructive" "$out"
    fi
    rm -rf "$base"
}

# ---------------------------------------------------------------------------------------------
# 7. WSL pickup (bwrap): dev-env.sh fills unset vars from /mnt/<drive>/... when native defaults
#    are absent. Needs a bindable /mnt -> bwrap; skips cleanly otherwise.
# ---------------------------------------------------------------------------------------------
t_devenv_wsl_pickup() {
    if ! bwrap_ok; then skip "dev-env.sh WSL /mnt pickup" "bwrap unavailable (Python suite covers WSL logic)"; return; fi
    local base h out
    base="$(new_sandbox)"; h="$base/home"          # NOTE: no repo/schemas -> forces WSL schema source
    mkdir -p "$base/fakebin"
    make_fake_uname "$base/fakebin"
    local mnt="$base/mnt"
    mkdir -p "$mnt/c/kw-mod-sdk/KanesWrathXMLFiles/GlobalData" \
             "$mnt/c/kw-mod-sdk/base-manifests" \
             "$mnt/c/kw-mod-sdk/schemas/kw/xsd"
    echo '<xsd/>' > "$mnt/c/kw-mod-sdk/schemas/kw/xsd/CnC3Types.xsd"
    out="$(bwrap --ro-bind /nix /nix --ro-bind /etc /etc --ro-bind /usr /usr --ro-bind /run /run \
                 --bind "$base" "$base" --bind "$mnt" /mnt --proc /proc --dev /dev \
                 --setenv HOME "$h" --setenv PATH "$base/fakebin:$PATH" \
                 "$(command -v bash)" -c \
                 'source "'"$base"'/repo/tools/dev-env.sh" >/dev/null 2>&1; echo "$KW_DATAROOT|$KW_BASEMANIFESTS|$([ -e "$KW_SCHEMA" ] && echo schema-ok || echo schema-miss)"' 2>&1)"
    local ok=1
    contains "$out" "/mnt/c/kw-mod-sdk/KanesWrathXMLFiles" || { fail "dev-env WSL picks dataroot from /mnt" "$out"; ok=0; }
    contains "$out" "/mnt/c/kw-mod-sdk/base-manifests" || { fail "dev-env WSL picks base-manifests from /mnt" "$out"; ok=0; }
    contains "$out" "schema-ok" || { fail "dev-env WSL links schema from /mnt" "$out"; ok=0; }
    [ "$ok" = 1 ] && pass "dev-env.sh WSL picks up /mnt/<drive> paths and links the schema"
    rm -rf "$base"
}

# ---------------------------------------------------------------------------------------------
# 8. WSL pickup for setup.sh (bwrap): detection searches /mnt/<drive>/... and records those paths
#    in dev-env.local. Skips cleanly without bwrap.
# ---------------------------------------------------------------------------------------------
t_setup_wsl_pickup() {
    if ! bwrap_ok; then skip "setup.sh WSL /mnt detection" "bwrap unavailable (Python suite covers WSL logic)"; return; fi
    local base h out
    base="$(new_sandbox)"; h="$base/home"
    mkdir -p "$base/fakebin"
    make_fake_uname "$base/fakebin"
    local mnt="$base/mnt"
    mkdir -p "$mnt/c/kw-mod-sdk/kw/xsd" \
             "$mnt/c/kw-mod-sdk/KanesWrathXMLFiles/GlobalData" \
             "$mnt/c/kw-mod-sdk/base-manifests"
    echo '<xsd/>' > "$mnt/c/kw-mod-sdk/kw/xsd/CnC3Types.xsd"
    printf '\0\0' > "$mnt/c/kw-mod-sdk/base-manifests/static_common_2.manifest"
    out="$(bwrap --ro-bind /nix /nix --ro-bind /etc /etc --ro-bind /usr /usr --ro-bind /run /run \
                 --bind "$base" "$base" --bind "$mnt" /mnt --proc /proc --dev /dev \
                 --setenv HOME "$h" --setenv PATH "$base/fakebin:$PATH" \
                 "$(command -v bash)" "$base/repo/tools/setup.sh" --non-interactive --no-build </dev/null 2>&1)"
    local local_file="$base/repo/tools/dev-env.local" body
    body="$(cat "$local_file" 2>/dev/null || true)"
    local ok=1
    contains "$body" 'KW_DATAROOT="/mnt/c/kw-mod-sdk/KanesWrathXMLFiles"' || { fail "setup WSL records dataroot" "$body"; ok=0; }
    contains "$body" 'KW_BASEMANIFESTS="/mnt/c/kw-mod-sdk/base-manifests"' || { fail "setup WSL records base-manifests" "$body"; ok=0; }
    contains "$body" 'KW_SCHEMA="/mnt/c/kw-mod-sdk/kw/xsd/CnC3Types.xsd"' || { fail "setup WSL records schema" "$body"; ok=0; }
    [ "$ok" = 1 ] && pass "setup.sh detects Windows-side SDK under /mnt and records it"
    rm -rf "$base"
}

# ---------------------------------------------------------------------------------------------
echo "== shell suite (setup.sh / dev-env.sh) =="
t_syntax
t_setup_help
t_setup_no_hang
t_setup_writes_local
t_devenv_resolution
t_devenv_ready
t_devenv_wsl_nondestructive
t_devenv_wsl_pickup
t_setup_wsl_pickup

printf '\nSHELL SUMMARY: passed=%d failed=%d skipped=%d\n' "$P" "$F" "$S"
[ "$F" -eq 0 ]
