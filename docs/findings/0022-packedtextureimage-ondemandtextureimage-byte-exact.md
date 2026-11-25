# 0022 — PackedTextureImage / OnDemandTextureImage round-trip byte-exact via the plain data pipeline

**Status:** Verified · 2026-11-25

> About **our own tools** (the XmlCompiler type registry, the decompiler's reflection-built struct-walker). The
> first **texture-pillar** types to reach the byte-exact ground-truth bar — the UI-atlas data records. Like
> [0019](0019-w3dcontainer-hierarchy-collisionbox-byte-exact-plain-pipeline.md) and
> [0020](0020-fxparticlesystemtemplate-byte-exact-plain-pipeline-plus-required-empty-module.md) they carry **no
> lossy/typeless block and no `pipelineOnly` pixel path** — plain POD records — so they needed **no runtime
> pass-through, no in-code schema binding, and not even a decompiler refinement**: just two lines of type
> registration. This is the oracle-strongest slice of the texture plan
> ([0021](0021-community-mod-texture-geometry-mechanism-recon.md) build order, milestone 1); the recon that
> de-risks the next slice (the `Texture` record's own DDS payload) is [0023](0023-texture-ondemandtexture-record-layout-recon.md).

## Context — two plain data records that were only ever un-registered

`PackedTextureImage` (TypeId `0x56626220`) and `OnDemandTextureImage` (TypeId `0xFE0E84BB`) are the UI-atlas
records: a sprite's placement inside a shared texture page. Both were in COVERAGE's "Not modeled" list, but the
structs and marshalers **already existed** in the tree:

- Structs: `SageBinaryData/PackedTexture.cs`, `SageBinaryData/OnDemandTextureImage.cs`
  (`Base` + an `AssetReference<Texture>` / `AssetReference<OnDemandTexture>` + three `ICoord2D`
  `Dimensions`/`Coords`/`TextureDimensions` + `SageBool Rotated`).
- Marshalers: `Marshaler.PackedTextureImage.cs`, `Marshaler.OnDemandTextureImage.cs` (XmlCompiler).
- `ICoord2D` value-struct marshaler already exists (child element with `x`/`y` attributes).

The only missing piece was the **registration** (the two types were present, commented out, in the XmlCompiler
`GetExtendedTypeInformation` scaffold). So this is an ordinary data type that round-trips through the generic
pipeline exactly like the existing 38 — registration + the pre-existing marshalers + the reflection-built
decompiler `TypeRegistry`. The 0021 Phase-1 prediction held: no lossy pixel pipeline (the pixel re-encode lives in
the *`Texture`* record, not these atlas records), so the generic pipeline reproduces them byte-exact. The `Texture`
/ `OnDemandTexture` referenced by the `Texture` attribute resolve by name via `-rm` (exactly like 0020's
`ParticleTexture` reference), so the atlas record round-trips with no `Texture`-record support at all.

## Harvested identity (from shipped data, never guessed — and version-matched)

TypeId = `FastHash(typeName)` — verified by reproducing the shared one-way formula (`Core/Hashing/FastHash`)
in-script, which also reproduces the known `W3DMesh 0xC2B1A262` / `ArmorTemplate 0x3A6C5E8E` /
`FXParticleSystemTemplate 0x28E7FD7F` ids. TypeHash was read straight from the shipped `static_common` manifest's
per-asset entries:

| Type | TypeId | TypeHash (shipped, harvested) | instances in static_common |
|------|--------|-------------------------------|----------------------------|
| PackedTextureImage   | `0x56626220` | `0x8AA0FF90` | 870 (single distinct TypeHash) |
| OnDemandTextureImage | `0xFE0E84BB` | `0xFBBF792D` | 123 (single distinct TypeHash) |

⚠ **Version trap avoided (the 0016 version-blindness class; 0020's TW-vs-KW trap).** The commented
`GetExtendedTypeInformation` scaffold lists these two with TypeHash `0x2FAEB748` (PackedTextureImage) /
`0xF3F4AEEC` (OnDemandTextureImage) — but that whole switch is the **TiberiumWars** type table (its `ArmorTemplate`
entry is `0x9CDD1086`, the *TW* ArmorTemplate hash per the `#if TIBERIUMWARS` arm of the foreach; KW's is
`0x6D59C409`). Trusting the scaffold would have stamped the **wrong-game** TypeHash. The registered values are the
harvested **KW** ones (`0x8AA0FF90` / `0xFBBF792D`), which differ from the TW scaffold values — a direct, concrete
instance of the trap.

**On TypeHash and the comparator (the comparator's own blind spot).** `compare-stream.py` matches by
`(TypeId, InstanceId)` and **wildcards TypeHash / InstanceHash**, so the harvested TypeHash is **not** verified by
the byte-exact gate — it is *harvested-not-oracle-verified*. The engine *does* check TypeHash at load
([0010](0010-insert-must-match-target-stream-type-schema-hash.md) /
[0016](0016-static-mod-stream-is-complete-replacement-not-overlay.md)), so a wrong value would be byte-exact-green
yet crash in-game; the harvest above is the only guarantee. `ProcessingHash = num ^ TypeHash` is applied by
`CreateTypeInfo`, not shipped data — no magic relationship implied.

## What was added / changed (1 owned file; no BYO/EA file edited)

- **`XmlCompiler/Plugin.cs`** — two foreach entries: `(typeof(PackedTextureImage), 0x8AA0FF90u, false)` and
  `(typeof(OnDemandTextureImage), 0xFBBF792Du, false)`, with a comment recording the harvest + the version-trap it
  avoids. Routing is the default `#all` → XmlCompiler (`BinaryAssetBuilder.cfg`), so no cfg change.

No new struct, no new marshaler, no runtime pass-through, no in-code schema binding, **no decompiler change** (the
reflection-built `TypeRegistry` already maps every public `SageBinaryData` struct, so both types decompile through
the generic `StructReader` walk automatically), **no edit to any schema / game data / stream** (invariant 1).

## Verification (oracle-backed, 2026-11-25)

`bab-decompile decompile-stream --type <hex>` + recompile + `compare-stream.py --type <hex>` against the shipped
`static_common` stream (`~/cnc-kw-godmod/ea-roundtrip/eastream/static_common.manifest`). **The whole instance set**
of each type was round-tripped (not a sample):

| Type | TypeId | Whole-corpus decompile | Recompile vs shipped |
|------|--------|------------------------|----------------------|
| PackedTextureImage   | `0x56626220` | **870 ok, raw=0** (single TypeHash `0x8AA0FF90`) | **870/870 BYTEEXACT** (sizeok_valdiff=0, sizediff=0, missing=0) |
| OnDemandTextureImage | `0xFE0E84BB` | **123 ok, raw=0** (single TypeHash `0xFBBF792D`) | **123/123 BYTEEXACT** (sizeok_valdiff=0, sizediff=0, missing=0) |

**Zero value-diffs.** No StringHash / weak-reference residual surfaced — the `Texture` / `OnDemandTexture`
references (e.g. `PackedImages_312`, `IndividualImages_001`) all resolve via `-rm` and round-trip byte-exact.

**No regression:** closed-loop `Armor.xml` **207/207** and `Weapon.xml` **456/456** byte-exact; ground-truth
`W3DAnimation` (`ABBHIVE_D2AN`), `W3DMesh` (`ABBHIVEBLD_SKN.ABBHIVEA`), `FXParticleSystemTemplate`
(`RedeemerLaserGlow3`) still byte-exact; `schema-selftest` both binding guards PASS; clean `dotnet build`
(0 errors).

## Scope / honesty

- Only `static_common` is sampled — but **every** `PackedTextureImage` (870) and `OnDemandTextureImage` (123)
  *in that stream* was round-tripped, so this is a whole-stream result, not a seed sample. It is not a whole-*game*
  guarantee (other streams unsampled).
- **TypeHash is harvested-not-oracle-verified** (comparator wildcard; see above).
- The big-endian / Xenon path is untouched.
- Both types carry a single distinct TypeHash in this stream (no schema variants), so no variant branch is
  unexercised here.

## Credit

Shipped EA UI-atlas records; no community content was used or shipped. The recon that studied the *mechanism* of
how textures enter the engine (0021) credits the community mods named there; this finding reproduces EA's own
shipped atlas-record bytes.
