# Findings

A catalogue of the **non-obvious truths** we've hit while building OpenWrath and making mods with it — the
things that cost an afternoon to figure out and that nobody had written down. Recording them here is the whole
point of the project: *observability over obscurity*. A modding ecosystem gatekept by tribal knowledge is one
where the knowledge dies with the people who leave. This folder is the opposite of that.

Each finding is small, dated, and — this matters — **honest about its status**:

- **Verified** — demonstrated from the bytes, the compiler source, the schema, or a reproducible measurement.
  The evidence is cited so you can re-check it.
- **Hypothesis** — our current best explanation, not yet proven. Written down anyway (a documented guess you
  can test beats an undocumented one you can't), and clearly marked so nobody mistakes it for fact. When a
  hypothesis is confirmed or refuted, the finding is updated and its status flipped.

Findings are about **data formats, the schema, the compiler/decompiler's own behaviour, and how authored data
behaves** — the lawful, data-side surface this toolchain works on. They are not a teardown of the game engine.

## Format

Each file is `NNNN-short-slug.md` with: **Status + date**, **Context** (where it bites), **Finding** (the
truth), **Evidence** (how we know), **How to apply** (what to do about it), and **See also**.

## Index

| # | Finding | Status |
|---|---------|--------|
| [0001](0001-joiner-matches-list-elements-by-id-only.md) | The node-joiner matches override list elements by `id` only — non-`id`-keyed elements append instead of replacing | Verified |
| [0002](0002-insertposition-top-is-parent-scoped.md) | `insertPosition="Top"` prepends to the whole parent, not to the sibling group — can break schema order | Verified |
| [0003](0003-gameobject-child-order-is-a-schema-sequence.md) | GameObject children are an ordered sequence; `VisionInfo` comes last | Verified |
| [0004](0004-locomotorset-resolution-is-per-condition.md) | A unit's locomotor is chosen per `Condition`; duplicate conditions resolve *last-wins* | Verified |
| [0005](0005-mods-must-live-in-one-target-stream.md) | Overrides must be spliced into the target's single stream — a separate stream doesn't override | Verified |
| [0006](0006-new-assets-need-stream-insert.md) | A mod can *add* a brand-new asset to a stream (not just replace one) via append-only manifest insert | Verified |
| [0007](0007-big-repack-must-be-fsynced-and-verified.md) | A big repack must be fsynced + integrity-verified before install, or a truncated archive ships silently | Verified |
| [0008](0008-xinclude-xpointer-not-honored.md) | **Compiler bug (FIXED):** `xi:include` xpointer wasn't honored (custom `ResolveXIncludes` ignored it, not Mvp.Xml) — fixed to splice only the selected node-set; GDICommando now round-trips byte-exact | Fixed |
| [0009](0009-decompiler-logiccommand-instance-read-desync.md) | **Decompiler desync = schema drift (RESOLVED):** `inspect` can't read `LogicCommand` because it's a *layout-drifted* type in SI; our retail-schema reader desyncs to `RawAsset`. Non-drifted types read fine from the same stream. Subsumed by 0010 | Resolved |
| [0010](0010-insert-must-match-target-stream-type-schema-hash.md) | **Schema drift (crash + tooling):** SI diverged from retail on **12 types**; INSERTing a new asset of a drifted type crashes on load. Built `openwrath schema`, a bake-time drift guard, and `--adopt-schema`. Drift is *hash-only* (adopt-safe) or *layout* (unsafe — e.g. `ObjectCreationList`); decompiler read success is the discriminator | Verified + tooled |
| [0011](0011-hitscan-units-do-not-detonate-launched-projectiles.md) | **Hitscan hardpoints can't fire projectiles:** a hitscan weapon slot (sniper, laser) never *launches* a projectile — delivery is a *modeled* hardpoint property, not data. Proven against the Redeemer (hitscan laser + rockets on **separate** hardpoints). Only weapon-level instant nuggets apply; projectile delivery needs a modeled hardpoint or a `WeaponOCLNugget` spawn | Verified |
| [0012](0012-refpack-manifest-detection-only-matches-0x10-variant.md) | **Decompiler fix too narrow (fix pending):** the manifest reader's RefPack guard matches only `0x10FB`, but RefPack is identified by its *second* byte `0xFB` (flags byte varies: `0x10/0x11/0x90/0x91`). The `0x90` variant still misreports as Xbox360 big-endian — the original bug, narrowed not closed. Live instance of overfitting + duplicated-knowledge drift | Verified (fix pending) |
| [0013](0013-subagent-modified-byo-ea-schema-in-place.md) | **Subagent silently edited a BYO EA schema (caught in review):** to pass XSD validation, a subagent widened the git-ignored `AssetTypeW3D.xsd` in place — invisible to git, no backup, made the "byte-exact verified" result non-reproducible from a clean clone. Root cause: a spec with a deliverable but no *boundary*. Fix: BYO/EA files read-only; handle the runtime form in code | Verified — caught in review |
| [0014](0014-runtime-w3danimation-dispatch-depends-on-schema-stamped-typeid.md) | **Schema binding is load-bearing (Resolved, verify pending):** W3DAnimation runtime channels need their `TypeId` schema-*stamped* for dispatch / reference-resolution / hashing — not just validation — so "relax validation only" could never work. Fixed by binding EA's own runtime channel types into `W3DAnimation.Channels` **in code** (`SchemaSet.BindRuntimeAnimationChannels`), never by editing the BYO schema file. Downstream consequence of fixing 0013 | Resolved (verify pending) |
| [0015](0015-standalone-overlay-override-needs-sliced-inheritfrom-base.md) | **Zero-EA standalone overlay (mod package):** a whole-file inheritFrom include drags referenced base siblings in as local copies (EA content); xi:include xpointer can select a top-level asset (extends 0008) but can't do a scoped *override* (needs the base as a tentative instance in `<Includes>`). Fix: slice the inheritFrom base (+ ancestors + macro context) to a single-asset include so deps stay imports, and GATE on emitted-ids==declared-ids. Verified byte-identical no-change + two real mods | Verified |
| [0016](0016-static-mod-stream-is-complete-replacement-not-overlay.md) | **The static `_mod` stream REPLACES `static_common` (not an overlay):** EA's own 1.03 patch ships a *complete* `Static_mod` (21,747 assets, all types incl. art) + `Static.version`; SI does the same. So a loadable binary static mod must ship the **full, version-matched** dataset — a zero-EA *partial* standalone can't load (`mod package` output is a correct zero-EA **diff**, not a drop-in). Also: inputs/COVERAGE are version-**blind** — the correct base is the running **patch** `Static_mod` (1.3), not Core/1.0. Explains 0005; the complete-probe crash was 1.0-vs-1.3 `DefaultHotKeys` drift (0010), not incompleteness | Verified (EA-patch + SI + 3 confirming reads) |

**See also:** the GameObject byte-exact breakthrough — one schema-default field the compiler wrote into former
alignment padding (`SetAnimsToLastFrameOnConstructionComplete`) — is documented in
[`../reference/COVERAGE.md`](../reference/COVERAGE.md) (the GameObject section), the archetypal "removed a byte
of obscurity" result.
