# Shared BYO input-integrity preflight for the round-trip gates. Source this AFTER $ROOT is set, then
# call verify_inputs_preflight before any compile/round-trip runs. One copy of the enforcement
# semantics so the two gates can't drift apart.
#
# The round-trip gate is what stamps "verified byte-exact". If it can produce a green result without
# first checking the inputs are the pristine ground truth, the oracle's unstated assumption is
# unguarded — exactly the hole finding 0013 fell through. So the gate refuses to run on drifted inputs.
# Semantics map to tools/verify-inputs.py's exit codes (DRIFT is a dedicated code, never 1/2):
#   0 (OK)          -> inputs match the committed baseline; proceed.
#   5 (DRIFT)       -> an input differs from the baseline; HARD-ABORT before the round-trip.
#   3/4/other       -> no baseline yet, or can't resolve roots; WARN and continue, so current work is
#                      not blocked before the clean set + inputs.sha256 land. Enforcement switches on
#                      automatically the moment inputs.sha256 is committed.
verify_inputs_preflight() {
    local vi="$ROOT/tools/verify-inputs.py"
    [ -f "$vi" ] || return 0            # tool absent (e.g. a shipped context) -> nothing to enforce
    local rc=0
    python3 "$vi" || rc=$?
    case "$rc" in
        0) : ;;                          # inputs match the baseline -> proceed silently
        5) echo "verify-inputs: refusing to run the round-trip on drifted inputs (above) — a 'verified'" >&2
           echo "               result must not rest on a mutated input (finding 0013/0014)." >&2
           exit 5 ;;
        *) : ;;                          # verify-inputs.py already explained (no baseline / no roots) -> continue
    esac
}
