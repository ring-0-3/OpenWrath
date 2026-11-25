# Design — shareable zero-EA mods via diff + assemble-at-install

**Status:** Design (📋 planned) · 2026-11-24 · motivating finding:
[0016](../findings/0016-static-mod-stream-is-complete-replacement-not-overlay.md)

> **⚠ Open architecture decision (2026-11-24).** Zero-EA is a confirmed hard requirement, so assemble-at-install is
> the path. **But the installer's shape is not yet settled** — the first attempt at the *light* form (splice the diff
> into the recipient's own *sparse* patch overlay, then ship that overlay) **crashed the game at launch** (0016). The
> pivotal unknown: can a mod-provided sparse `static_mod` defer to the base, or must a mod's stream be *complete*? A
> **control test** (verbatim-sparse standalone, lowercase like SecondIsomer) is in progress to decide:
> - **light installer** — splice the ~1 KB diff into the recipient's sparse patch overlay (small output), *if* sparse
>   mod streams load; or
> - **heavy installer** — assemble a *complete* stream (~200 MB) from the recipient's full base chain + the diff,
>   locally (SecondIsomer's complete 779 MB `static_mod` is the precedent that complete works).
> Either way the shared artifact stays zero-EA; only the recipient-side output size differs.
>
> **`mod bake` is NOT this installer.** `bake` splices into an *existing complete* stream that is already installed
> (e.g. SecondIsomer's); a zero-EA mod's recipient has only the *sparse* patch overlay, so the installer must either
> accept sparse (light) or build the complete stream itself (heavy) — `bake` assumes the complete target already
> exists. The installer *reuses* bake's splice engine (`_apply_overrides`), not its target-resolution.

## The opportunity finding 0016 opened

A loadable static overlay needs a **complete entry list + version-matched TypeHashes + instance data only for the
assets it changes** — *not* every asset's bytes (0016). The recipient **already owns** the first two things: their
installed patch `Static_mod` overlay *is* a complete, version-matched entry list, and their Core/1.0 `static_common`
is the full byte pool behind it. So a sharer needs to ship only **the authored diff** (the changed assets' bytes +
where they go), and a small installer assembles the loadable stream on the recipient's own game.

That keeps the shared artifact **zero EA bytes on the wire** while producing a stream that loads — closing the gap
0015/0016 left. `mod build-local` already does the recipient-side assembly for the *local* operator; Option 1 is
"run that assembly on the recipient, from a portable diff bundle, with EA kept entirely on the recipient's disk."

## Two halves

### 1. The diff bundle (producer side) — zero EA, shareable

`openwrath mod package --diff <project>` produces `<name>.owdiff` (a plain directory or zip) containing **only
user-authored content**:

- **`manifest.toml`** — mod name; target stream (`static_mod`); per override: `{type, instance, TypeId,
  InstanceId, TypeHash, op: replace|insert}`; the OpenWrath/schema version it was built against.
- **The authored source** — the mod's own override XML (`src/*.xml`) and, for `insert`s, the sliced zero-EA overlay
  `mod package` already builds ([0015]): new assets via `xi:include`, sliced `inheritFrom` bases with their
  `<Defines>` macro context. This is the user's derivative of a game they own — standard mod output, not EA files.
- **Optionally, the prebuilt `.asset` bytes** for each override (the compiled instance+relo+imp). These are the
  user's *authored* bytes (their edited values), not EA's — includable, but see the portability trade-off below.

**The same zero-EA gate as `mod package`** ([0015]) guards it: the bundle's declared id set must equal what the
producer compiled; any EA/base asset that leaked in ⇒ refuse. No EA manifest, entry list, art, or stream ships.

### 2. The installer (recipient side) — EA stays on the recipient's disk

`openwrath mod install-diff <name>.owdiff` (recipient needs OpenWrath + their own game; **no SDK needed for the
`replace`-only, prebuilt-bytes case**) does, per the corrected model:

1. **Locate the recipient's own overlay** — `_install_overlay_stream(cfg, stream)` finds their patch `Static_mod`
   (read-only EA) and extracts a working copy. (Already built for `build-local`.)
2. **Version-match gate (0010)** — for each override, the recipient overlay's TypeHash for that type MUST equal the
   bundle's. Equal ⇒ the prebuilt bytes are layout-correct for this install (splice them directly). Unequal ⇒ this
   is schema drift: abort with a precise message, or (if the bundle shipped source + the recipient has the SDK)
   recompile recipient-side so the bytes match the recipient's schema. This is the **portability boundary**, and it
   is *checkable*, not assumed.
3. **Assemble** — REPLACE each existing target via `splice_asset` (immune to drift by construction); INSERT new
   assets via `insert_asset` with the `_insert_drift_guard` / `--adopt-schema` path. Reuses the shared
   `_apply_overrides` engine (one source of the splice/insert format, with `build-local` and `bake`).
4. **Pack + install** — pack a mod big that shadows the recipient's `data\Static_mod.*` (+ the `.version` verbatim),
   fsync + `big_is_complete` ([0007]), install into `Mods/<name>/`, print the master-SkuDef `add-config` line. The
   produced big is EA-derived (it rides the recipient's own overlay) → it lives **only on the recipient's disk**,
   exactly like `build-local`'s output. Nothing EA ever crossed the wire.

## Prebuilt bytes vs recompile-on-install — the portability trade-off

| | Prebuilt `.asset` bytes | Recompile from source on install |
|---|---|---|
| Recipient needs | OpenWrath only (replace case) | OpenWrath **+ SDK** |
| Robust to recipient schema drift | No — gated, aborts on mismatch | Yes — compiles to the recipient's schema |
| Bundle size | tiny (≈1 KB/asset) | tiny (XML) |
| Trust surface | data only | runs the compiler on recipient |

**Recommendation:** ship **both** in the bundle — prefer prebuilt bytes when the version-match gate passes (fast,
no SDK), fall back to recompile when the recipient has the SDK and the gate fails. Never silently splice
version-mismatched bytes (that is the 0010 crash class).

## REPLACE is the clean path; INSERT inherits 0015's constraints

- **REPLACE** (editing an existing asset, e.g. the missile fire-rate): the entry already exists in the recipient's
  overlay; splicing the authored bytes is immune to schema drift (keeps the stream's TypeHash). This is the 90% case
  and the one to ship first.
- **INSERT** (brand-new asset): needs a *new* entry in the overlay, carrying our compiler's TypeHash → subject to
  the 0010 drift guard, and the new asset's cross-stream references must resolve as imports against the recipient's
  base ([0015]). Supported via the existing insert + `--adopt-schema` machinery, but flagged as the sharp-edged case.

## Gates & boundaries (verify, don't assert)

- **Zero-EA on the wire:** the `.owdiff` bundle contains only user-declared ids / authored source / the user's
  compiled bytes — enforced by the [0015] gate at build time. No EA manifest, entry list, art, or stream.
- **Version-match (0010):** the recipient-side TypeHash check is a hard gate; mismatch aborts (or recompiles), never
  a silent splice.
- **Integrity (0007):** fsync + `big_is_complete` on the assembled big; back up any file replaced; reversible by
  removing the owned `Mods/<name>/` folder + the SkuDef line.
- **BYO/EA read-only:** the recipient's game files are only *read*; all writes land in the owned `Mods/<name>/`.
- **Reuse map:** `cmd_mod_package` (the diff/zero-EA gate), `_install_overlay_stream`, `_insert_drift_guard`,
  `_apply_overrides`, `splice_asset.py` / `insert_asset.py`, `pack_big` + `big_is_complete`, the `.version` emit.

## Open questions to settle before/with implementation

- **Entry-list completeness across installs:** the recipient's overlay entry count (21,747 at 1.3/Patch103) is
  assumed to match the producer's. If a recipient is on a different patch, the version-match gate catches per-type
  drift, but a *missing target entry* (an asset the recipient's overlay lacks) must also be handled — detect and
  report, don't crash.
- **In-game confirmation of the deferral model** (0016's remaining launch): Option 1's correctness rests on the
  base+overlay/deferral behaviour. The `build-local` in-game test confirms it once; Option 1 inherits that result.
- **Bundle trust/signing:** a `.owdiff` is data, but `install-diff` runs on someone else's machine. Document the
  reversible/owned-folder guarantees; consider a later signed-bundle option.

## See also

- [0016](../findings/0016-static-mod-stream-is-complete-replacement-not-overlay.md) — the base+overlay/deferral model
  (why this is possible and cheap).
- [0015](../findings/0015-standalone-overlay-override-needs-sliced-inheritfrom-base.md) — the zero-EA diff builder
  (the bundle's source half).
- [0010](../findings/0010-insert-must-match-target-stream-type-schema-hash.md) — the version-match gate.
- `modkit/openwrath` (`cmd_mod_build_local` is the local sibling; Option 1 is its recipient-side form).
