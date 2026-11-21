# 0006 — A mod can *add* a brand-new asset to a stream, via append-only manifest insert

**Status:** Verified · 2026-11-20

## Context

Finding [0005](0005-mods-must-live-in-one-target-stream.md) establishes that an override must live in the
stream that owns the asset. But some mods need an asset that *doesn't exist yet* — a new weapon, a new
projectile, a whole new unit. Replacing an existing asset (the splice path) can't do that. The first attempt
to reference a brand-new id failed at bake with *"stream … is missing some override ids"*, because the splice
tool only knows how to swap an asset already present.

## Finding

**A new asset can be added to a linked stream by appending — and because it is pure append, every existing
asset stays byte-identical.** A linked stream is a manifest (`48B header + N×44B AssetEntry + AssetRefBuf +
RefManNameBuf + AssetNameBuf + SrcNameBuf`) plus three parallel chunk buffers (`.bin/.relo/.imp`, each a 4-byte
prefix then per-asset chunks in manifest order). To insert one asset:

- append its entry to the end of the entry table (`AssetCount += 1`);
- append its instance/relo/imports chunks to the ends of `.bin/.relo/.imp`;
- append its 8-byte `(TypeId, InstanceId)` references to the end of `AssetRefBuf`, and its authored name /
  source name to the ends of their buffers;
- point the new entry's `AssetReferenceOffset` / `NameOffset` / `SourceFileNameOffset` at those **ends**.

Because every new byte goes at the **end** of its buffer, **no existing entry's offsets or chunk bytes change** —
so all pre-existing assets round-trip byte-identical, and only the header's four size/count fields move
(`AssetCount`, `TotalInstanceDataSize`, `AssetNameBufferSize`, `SourceFileNameBufferSize`).

Two enabling facts make this safe:
- **AssetReferences are self-contained** `(TypeId, InstanceId)` pairs — they do **not** index into
  `RefManNameBuf`, so that buffer is left untouched and references resolve globally across the loaded manifest
  set. A new asset may therefore reference assets defined anywhere already loaded.
- **A model/mesh is referenced by name**, not embedded — so a new projectile can wear an existing art model
  (e.g. the nuke missile mesh `NSNMSiloMis_AN`) just by naming it; the art resolves at runtime from the loaded
  art streams. No art pipeline needed to *reuse* existing art.

## Evidence

`modkit/lib/insert_asset.py` implements exactly this. Verified on SI's `static_mod` (43,994 assets): after
inserting one `WeaponTemplate`, a byte-compare showed **all 43,994 existing entries + every buffer prefix +
every `.bin/.relo/.imp` chunk byte-identical**; only the four expected header fields changed; and the new asset
**decompiled back correctly** (`ok=1 raw=0`) from the modified stream. The full flying-nuke-missile object
(`OpenWrathNukeMissile`, a new projectile wearing the nuke mesh) was then inserted and read back intact.

## How to apply

- To add a new asset with the modkit, just declare it in your mod source and bake. `openwrath mod bake` splits
  overrides into **replace** (id already in the stream → splice) and **new** (id absent → insert) automatically;
  the target stream must be pinned in `mod.toml` so it knows where to add. A new id with no pinned stream errors
  rather than guessing.
- Inserting is additive and reversible via the normal backup; existing content is provably untouched.
- This only *reuses* existing art/data by reference. Authoring genuinely new art/meshes/sounds is the separate
  content-pipeline work on the roadmap, not this.

## See also

- [0005](0005-mods-must-live-in-one-target-stream.md) — why it must be *this* stream.
- [0007](0007-big-repack-must-be-fsynced-and-verified.md) — the repack-safety lesson learned while shipping this.
