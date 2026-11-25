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

**"Byte-exact" is byte-exact on the comparator's *compared subset*.** `compare-stream.py` matches on
(TypeId, InstanceId) and **wildcards TypeHash / InstanceHash** — so header-identity fields are *harvested-and-attested*,
not oracle-verified. The engine *does* check TypeHash at load (0010/0016), so a wrong one is **byte-exact-green yet
crash-in-game**. Harvest such fields from the shipped manifest (never the wrong-game scaffold — 0020's TW-vs-KW trap),
and never let a green gate imply an uncompared field is right. (`docs/design/verification-blind-spots.md` §
"the comparator's own blind spot".)

## Durable references — read these; do not rely on chat memory

- `docs/design/verification-blind-spots.md` — oracle blind spots (incl. **the comparator's own blind spot** and the
  fresh-context reuse-duplication tax), test provenance, fresh-vs-shared-context.
- `docs/findings/` — dated truths; **0012** (RefPack), **0013** (schema-edit remediation), **0014/0018/0019/0020**
  (art pipeline — see SOLVED below), **0021** (texture/geometry mechanism recon).
- `docs/design/community-mods-as-frontier-reference.md` — study community mods for *mechanism*, reimplement clean;
  community ≠ ground truth. `docs/design/blender-integration.md` — authoring tier + the re-pack decidable gate.
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

## SOLVED: the W3D art pipeline + particles are byte-exact (findings 0014/0018/0019/0020 — do NOT re-derive)

The whole **W3D model graph** (`W3DAnimation`, `W3DMesh`, `W3DContainer`, `W3DHierarchy`, `W3DCollisionBox`) **plus
`FXParticleSystemTemplate`** round-trip **byte-exact vs shipped** `static_common` (sample-verified; see COVERAGE).
Read the findings before touching art types. **The decision rule — do not presuppose the mesh/anim approach:** a
type needs a **runtime pass-through** (emit the shipped compiled bytes verbatim, write them straight back — no
re-encode) *only if it carries a lossy/typeless block* (anim's compressed channels; mesh's packed `VertexData`).
**Plain structural types + particles use the ORDINARY pipeline** — register + hand-written/existing marshalers, the
generic decompiler walk. Reaching for pass-through on a plain type is overfitting the previous answer (0019).

**Reuse map (do NOT re-derive — invariant 3):** schema reach is added **in code**, never a BYO `.xsd` edit
(`SchemaSet.BindRuntimeAnimationChannels` / `AugmentRuntimeMeshVertexData`, finding 0014); shared decompiler
renderers live on `AssetInput` (`RenderUShortList`, `ReadBlobBase64`) — call them, don't copy; the **reference-choice**
emit is general (`SchemaIndex.GetReferenceChoiceElement`/`IsReferenceChoiceType` + `StructReader.TryEmitReferenceChoice`);
the **required-but-null polymorphic module** → empty-wrapper rule is schema-driven (`SchemaIndex.GetRequiredElementNames`,
0020); `TypeId = FastHash(name)`, **TypeHash harvested from the shipped manifest** (never the TW scaffold — 0020).

**Frontier — textures (0021, mechanism recon, NOT yet built):** new content enters as asset **records**
(`Texture`/`OnDemandTexture`/`PackedTextureImage` + the model graph) referencing raw **D3D9 DDS**; `Texture` fields are
`pipelineOnly` (compile-time re-encode) so the **pixel path is stated-tier, never byte-exact** (EA's DXT compressor
isn't bit-reproducible). The records are tractable. Build order (oracle-strongest first): **loose-file
`add-search-path` override** (the route the 4K pack rides — cheapest, no record modeling, in-game-acceptance gate) →
**`PackedTextureImage`/`OnDemandTextureImage`** (plain data records → byte-exact) → **`Texture` shipped-payload
pass-through** (open a shipped record first to confirm its layout) → new record-borne content last. Full plan + the
community-mod discipline: `docs/findings/0021-*.md` + `docs/design/community-mods-as-frontier-reference.md`.
