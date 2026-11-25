# CLAUDE.md — OpenWrath working agreement

**OpenWrath** is a native-Linux, open modding toolchain for *C&C 3: Kane's Wrath* (SAGE engine): a byte-faithful
compiler, a lossless decompiler, and the archive/stream tools. It ships **no EA content** — you bring your own
legally-owned data.

## The one principle

Correctness is a **decidable property, not a claim.** The authority is EA's actual bytes: a change is correct
*iff* the asset round-trips **byte-exact vs shipped data** (`tools/roundtrip.sh --from-binary`). "Trust me" is not
part of the design — **verify, don't assert.**

## Standing invariants — do not violate

1. **BYO / EA files are READ-ONLY.** Never edit schemas, game data, SDK XML, or streams **in place**. OpenWrath's
   additions live in *owned, tracked* files or *in code* — never as a silent edit to a bring-your-own file.
   (finding 0013)
2. **Never hardcode to match a sample; never overfit the oracle.** A fix must encode the *rule*, not *this
   instance's answer*. One-line test: *would it produce correct bytes for an instance we never sampled?* If you
   can't answer yes with a reason, it's overfit. No magic constant that equals the expected output; no
   `if id == "..."`; **never widen the comparator** to silence a diff. (finding 0012;
   `docs/design/verification-blind-spots.md`)
3. **Single sources of truth — never re-derive format knowledge.** Before writing a format detail, grep for the
   existing authority and reuse it. (E.g. RefPack is identified by `byte[1] == 0xFB` — one shared `IsRefPack()`;
   render floats via the shared helper, don't copy it.) Duplicated knowledge drifts; it is the root cause behind
   0012 and the W3D dup-seeds.
4. **Verify inputs, not just outputs.** The oracle silently assumes pristine ground truth — don't. Baseline BYO
   inputs from a *verified-clean* set (official SDK for shared SAGE types; Steam-verified game data for
   KW-specific truth), committed as `inputs.sha256`, enforced by a `verify-inputs` preflight that **refuses on
   drift**. **Never seed the baseline from the current (possibly-dirty) tree.** **Pristine is not enough — the
   clean set must also match the *patch version the engine actually runs*** (finding 0016: a `Core/1.0` baseline
   is pristine yet `0010`-crashes a 1.3 engine). Record the patch version in the baseline; the KW-specific base is
   the **running patch's stream** (e.g. the patch `Static_mod`), not an older `Core/x.x`. "Matches shipped bytes"
   is meaningless without naming the patch.
5. **Honest coverage.** Report what was *sampled*, not assumed. Byte-exact where proven; honestly bucketed
   otherwise. Publish the gaps — never a silent green checkmark.

## Subagent spec template — every delegated task carries three parts

A subagent deliverable MUST include all three, or it drifts:
- **(a) Oracle-backed bounded goal** — the measurable finish line, checked against ground truth.
- **(b) Reuse map** — the existing helpers/authorities it must reuse and must NOT re-derive.
- **(c) Boundaries** — what's off-limits (BYO/EA files, the comparator, out-of-scope types).

Fresh-context subagents produce the best work *given all three*. (a)-only is how the W3DAnimation pillar ended up
with duplicated helpers **and** an in-place schema edit. See the fresh-vs-shared-context section in the
blind-spots doc.

## Review discipline

**The thing that verifies a change must not be the thing that wrote it.** Read the *diff*, not just the test
result: did it generalize or overfit? input-derived or output-derived? did it add a duplicate? For a value-diff,
is it a StringHash (→ harvest) or source-drift (→ document and bucket, don't patch the compiler)?

## Durable references — read these; do not rely on chat memory

- `docs/design/verification-blind-spots.md` — oracle blind spots, test provenance, fresh-vs-shared-context.
- `docs/findings/` — dated truths; **0012** (RefPack fix pending), **0013** (schema-edit remediation).
- `docs/reference/COVERAGE.md` — the per-type ground-truth matrix.
- `ROADMAP.md` — go-forward plan + the input-integrity preflight.

## SOLVED: loadable mods that override base gameplay (finding 0017 — do NOT re-derive)

A **loadable, (near-)zero-EA mod that overrides base KW gameplay on retail 1.3 is SOLVED** and verified in-game
(2026-11-25). The complete recipe, byte-level structure, full failure catalog, and the builder are in
**`docs/findings/0017-overlay-mod-overrides-base-gameplay-the-complete-recipe.md`** — read it before touching mod
packaging. One-line shape: a **sparse differential** `static_mod` (complete entry list, data only for your edits,
`\x02` defer to `static_common_2`) + a **low-LOD twin** (`static_l_mod`→`static_mod`) + the **WorldBuilder
companion** (`worldbuilder_mod`) + **three `.version` redirect files** (`_mod\n`) + **the base's max-chunk header
kept** (not recomputed — the final crash) + unique per-stream checksum. Builder: `modkit/lib/build_overlay.py`
(+ `retag_checksum.py`), verified byte-exact against the working artifact. Key gotchas that burned a whole session:
**R23/tournament maps crash at match-start on their own** (always test on a standard map; distinguish launch-crash
vs match-crash vs loaded-but-ignored); the gameplay schema is **identical 1.2↔1.3** (defer to `static_common_2` is
version-safe; the "1.3 patch" is textures). Distribution: OpenWrath's **default is strict zero-EA** (ship the diff +
a bundled recipient-side assembler; the drop-in carries EA-derived entry-list metadata and is **LOCAL-ONLY**).
0016's "must be complete data"/checksum-collision theories are **withdrawn** (see its banner); 0005 is **refined**
(an overlay IS consulted, via the `.version` redirect). Only one overlay owns a family → overlay mods are mutually
exclusive; stacking needs merging diffs into one overlay (planned `multi-mod merger`).
