#!/usr/bin/env bash
# Top-level test runner for the OpenWrath onboarding toolchain.
#
#   tests/run.sh          # run everything, print a combined pass/fail/skip summary
#
# Runs both CI-safe suites and aggregates them:
#   1. the Python modkit suite (modkit/tests/test_openwrath.py) — the openwrath CLI;
#   2. the shell suite (tests/test_shell.sh)                      — tools/setup.sh + tools/dev-env.sh.
#
# Everything here passes on a machine with NO EA/game data and NO .NET SDK: the suites use only
# synthetic fixtures in isolated tmpdirs. Checks that genuinely need the real Mod SDK or a dotnet
# build are SKIPPED with a visible reason, never failed or faked (see tests/README.md for the full
# CI-excluded list). Needs neither pytest nor dotnet installed. Exit status is nonzero if anything
# failed.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PY_OUT=""; PY_RC=0; SH_OUT=""; SH_RC=0

hr() { printf '\n========================================================================\n'; }

hr; echo "SUITE 1/2: Python modkit (modkit/tests/test_openwrath.py)"; hr
if command -v python3 >/dev/null 2>&1; then
    PY_OUT="$(cd "$ROOT" && python3 modkit/tests/test_openwrath.py 2>&1)"; PY_RC=$?
    printf '%s\n' "$PY_OUT"
else
    PY_RC=1
    echo "  ERROR: python3 not found — cannot run the modkit suite."
fi

hr; echo "SUITE 2/2: shell (tests/test_shell.sh)"; hr
SH_OUT="$(cd "$ROOT" && bash tests/test_shell.sh 2>&1)"; SH_RC=$?
printf '%s\n' "$SH_OUT"

# ---- aggregate --------------------------------------------------------------------------------
# Python script mode prints a final "<p> passed, <f> failed".
py_pass="$(printf '%s\n' "$PY_OUT" | sed -n 's/^\([0-9]\+\) passed, \([0-9]\+\) failed$/\1/p' | tail -1)"
py_fail="$(printf '%s\n' "$PY_OUT" | sed -n 's/^\([0-9]\+\) passed, \([0-9]\+\) failed$/\2/p' | tail -1)"
# Shell suite prints "SHELL SUMMARY: passed=<p> failed=<f> skipped=<s>".
sh_pass="$(printf '%s\n' "$SH_OUT" | sed -n 's/^SHELL SUMMARY: passed=\([0-9]\+\) failed=\([0-9]\+\) skipped=\([0-9]\+\)$/\1/p' | tail -1)"
sh_fail="$(printf '%s\n' "$SH_OUT" | sed -n 's/^SHELL SUMMARY: passed=\([0-9]\+\) failed=\([0-9]\+\) skipped=\([0-9]\+\)$/\2/p' | tail -1)"
sh_skip="$(printf '%s\n' "$SH_OUT" | sed -n 's/^SHELL SUMMARY: passed=\([0-9]\+\) failed=\([0-9]\+\) skipped=\([0-9]\+\)$/\3/p' | tail -1)"
: "${py_pass:=?}" "${py_fail:=?}" "${sh_pass:=?}" "${sh_fail:=?}" "${sh_skip:=0}"

hr; echo "COMBINED SUMMARY"; hr
printf '  python (modkit):  %s passed, %s failed\n' "$py_pass" "$py_fail"
printf '  shell  (scripts): %s passed, %s failed, %s skipped\n' "$sh_pass" "$sh_fail" "$sh_skip"
if [ "$sh_skip" != 0 ] && [ "$sh_skip" != "?" ]; then
    echo
    echo "  skipped (need a real environment, see tests/README.md):"
    printf '%s\n' "$SH_OUT" | sed -n 's/^  SKIP  /    - /p'
fi
echo

if [ "$PY_RC" -eq 0 ] && [ "$SH_RC" -eq 0 ]; then
    echo "RESULT: all suites PASSED"
    exit 0
else
    echo "RESULT: FAILURES (python rc=$PY_RC, shell rc=$SH_RC)"
    exit 1
fi
