# 0024 — `Texture` / `OnDemandTexture` round-trip byte-exact via a shipped-DDS-payload pass-through

**Status:** Verified · 2026-11-25

> About **our own tools** (the XmlCompiler type registry + a new pass-through marshaler, the decompiler's
> struct-walker, and an in-code schema binding). The texture-pillar milestone 2
> ([0021](0021-community-mod-texture-geometry-mechanism-recon.md) build order), executing the spec in the
> byte-inspection recon [0023](0023-texture-ondemandtexture-record-layout-recon.md). This is **0018-shaped** (a
> runtime pass-through of a lossy compiled block), not 0022-shaped (plain registration): the texture records carry a
> literal compiled DDS payload, so they need a marshaler, a decompiler reader, and a schema binding — not just a
> `foreach` line.

## Context — the record IS a literal D3D9 DDS blob (0023), so pass it through

A shipped KW `Texture` (TypeId `0x21E727DA`) carries its pixels as a **literal, complete D3D9 `.dds` file** — the
compile-time output of EA's DXT compressor + mip generator. That compressor is lossy and **not bit-reproducible**
(0021 §), so re-encoding a decoded texture cannot reproduce the shipped bytes — exactly the situation `W3DMesh`'s
packed vertex data (finding [0018](0018-w3dmesh-byte-exact-via-runtime-vertexdata-passthrough.md)) and
`W3DAnimation`'s compressed channels ([0014](0014-runtime-w3danimation-dispatch-depends-on-schema-stamped-typeid.md))
were in. So the DDS payload is carried straight through, never re-encoded; byte-exact for **shipped** textures without
reimplementing the compressor. Authoring *new* textures stays stated-tier and is out of scope here.

`OnDemandTexture` (TypeId `0x9312B9AC`) is the lazy twin: the stream record carries **no pixels** (the engine streams
them on demand by id/name), just identity.

## The model — decided by the shipped bytes, not the recon's field names

The recon (0023) *recommended* `{ BaseAssetType Base; uint Flags; <ptr> Payload; uint PayloadLength }`, but the
shipped bytes — re-inspected here against `PackedTextureImage` (a sibling record whose struct is known) — show there
is **no separate `Flags` field**. Every shipped asset instance begins with the universal **4-byte zeroed
`BaseAssetType`** slot (the `AssetIdInfo*` placeholder, written as 0 by the no-op `Marshal(Node, BaseAssetType*)`); in
a `Texture` the relocated payload pointer sits at **offset 4** (relo `04 00 00 00`), leaving no room for a `Flags`
word before it. The recon's "Flags@0x00" IS that `Base` placeholder. (`PackedTextureImage:AmmoPip` confirms the
convention directly: `inst[0:4] = 0` = Base, its `Texture` AssetReference at offset 4.)

So the byte-decided model is:

```csharp
// SageBinaryData/Texture.cs
public struct Texture         { public BaseAssetType Base; public DataBlob Payload; }   // Base@0, Data@4(reloc), Size@8, DDS@0x0C
public struct OnDemandTexture { public BaseAssetType Base; public unsafe byte* Payload; } // Base@0, null ptr@4 -> 8 zero bytes, no relo
```

`DataBlob` is the **shared** `Relo` type `{ void* Data; uint Size }` — the **ptr-then-length** shape (NOT the
`List<byte>` `{Count, Items}` convention), which is exactly the shipped field order and collapses (via `TypeLayout`'s
x64→x86 map) to a 4+4=8-byte header, so the `Texture` record is Base(4)+Data(4)+Size(4) = a 12-byte header then the
DDS bytes. Reusing `DataBlob` (invariant 3) means the relocation (`Tracker.Push(&Payload.Data, …)`), the x64→x86
pointer compaction, and the single `04000000 ffffffff` relo all fall out of the existing framework — no re-derivation.
`OnDemandTexture`'s `byte* Payload` is never allocated, so it stays null → no relocation → the shipped 8-byte-all-zero
record.

## What was added / changed (all owned files; no BYO/EA file edited)

- **Model** — `SageBinaryData/Texture.cs`: the two structs above (were empty `// TODO` stubs).
- **Compiler marshaler** — `BinaryAssetBuilder.XmlCompiler/Marshaler.Texture.cs` (NEW): `Marshal(Node, Texture*)`
  decodes the `<Payload>` base64 and writes the DDS bytes into the `DataBlob` (length derived from the actual blob,
  never a baked sampled value; `Push` reproduces the one relo); `Marshal(Node, OnDemandTexture*)` writes only the Base
  slot. The one base64 decoder in the XmlCompiler marshaler (its W3DMeshRuntime twin lives in a separate plugin
  assembly).
- **Registration** — `XmlCompiler/Plugin.cs`: two `foreach` entries, `(typeof(Texture), 0xB30F14DBu, false)` and
  `(typeof(OnDemandTexture), 0x9DEE5EDCu, false)`. `TypeId = FastHash(name)` = `0x21E727DA` / `0x9312B9AC`
  (reproduced by the registration; confirmed empirically by the byte-exact recompile). `ProcessingHash = num ^
  TypeHash` is applied by `CreateTypeInfo`.
- **Decompiler reader** — `Decompiler/StructReader.cs`: a `Texture.Payload` special-case (mirroring the `W3DMesh`
  `VertexData` hook) emits the shipped DDS bytes verbatim as a runtime `<Payload>` base64 element via the existing
  `ReadBlobBase64` (reused, not copied). Needed because the `SchemaIndex` is parsed from the **raw** XSD (which has no
  `<Payload>`), so the generic `DataBlob` walk's `SetAttr` would drop it. `OnDemandTexture`'s null pointer falls
  through the generic pointer path and emits nothing.
- **Schema binding (in code)** — `Core/SageXml/SchemaSet.cs`: `AugmentRuntimeTexturePayload` adds an optional
  `<Payload>` element to the `Texture` content sequence before `Compile()`, so the runtime form validates. Never edits
  a bring-your-own `.xsd` (invariant 1); the prototype binding, migrates to the schema-overlay registry (ROADMAP).
- **Self-test** — `source/schema-selftest/Program.cs`: a `Texture` guard with a negative control (the un-augmented
  schema rejects `<Payload>`), mirroring the animation/mesh guards.

## Harvested identity (from shipped data, never guessed)

TypeHash was read straight from the shipped `static_common` manifest's per-asset entries — a **single distinct value**
across every instance of each type:

| Type | TypeId | TypeHash (shipped, harvested) | instances |
|------|--------|-------------------------------|-----------|
| Texture         | `0x21E727DA` | `0xB30F14DB` | 1575 |
| OnDemandTexture | `0x9312B9AC` | `0x9DEE5EDC` | 123 |

⚠ **Neither type appears in the commented `GetExtendedTypeInformation` TW scaffold** — so there is no shortcut value;
harvest from the shipped KW manifest was the only source (invariant 2; the 0016 version-blindness / 0020 TW-vs-KW
class). **The comparator wildcards TypeHash** (`compare-stream.py` matches on `(TypeId, InstanceId)`), so the
harvested TypeHash is **harvested-not-oracle-verified** — the byte-exact gate below does **not** prove it. The engine
*does* check TypeHash at load ([0010](0010-insert-must-match-target-stream-type-schema-hash.md) /
[0016](0016-static-mod-stream-is-complete-replacement-not-overlay.md)), so the harvest above is the only guarantee.

## Verification (oracle-backed, 2026-11-25)

`bab-decompile decompile-stream --type <hex>` + recompile + `compare-stream.py --type <hex>` against the shipped
`static_common` stream (`~/cnc-kw-godmod/ea-roundtrip/eastream/static_common.manifest`). **The whole instance set** of
each type was round-tripped (not a sample):

| Type | TypeId | Whole-corpus decompile | Recompile vs shipped |
|------|--------|------------------------|----------------------|
| Texture         | `0x21E727DA` | **1575 ok, raw=0** (single TypeHash `0xB30F14DB`) | **1575/1575 BYTEEXACT** (sizeok_valdiff=0, sizediff=0, missing=0) |
| OnDemandTexture | `0x9312B9AC` | **123 ok, raw=0** (single TypeHash `0x9DEE5EDC`)  | **123/123 BYTEEXACT** (sizeok_valdiff=0, sizediff=0, missing=0) |

**Zero value-diffs.** Payloads span DXT1/DXT3/DXT5 and uncompressed A8R8G8B8, mip counts 0–11 (the 0023 format
distribution) — all pass through byte-exact.

**No regression:** closed-loop `Armor.xml` **207/207** and `Weapon.xml` **456/456** byte-exact; ground-truth
`W3DAnimation` (`ABBHIVE_D2AN`), `W3DMesh` (`FXPHASEMASK`), `FXParticleSystemTemplate` (`RedeemerLaserGlow3`),
`PackedTextureImage` (`AmmoPip`), `OnDemandTextureImage` (`17Logo`) still byte-exact; `schema-selftest` **3/3 PASS**
(animation + mesh + the new texture guard, each with its negative control); clean `dotnet build` (0 errors).

## Scope / honesty

- Only `static_common` is sampled — but **every** `Texture` (1575) and `OnDemandTexture` (123) *in that stream* was
  round-tripped, so this is a whole-stream result, not a seed sample. It is not a whole-*game* guarantee.
- **TypeHash is harvested-not-oracle-verified** (comparator wildcard; see above).
- **Pass-through covers SHIPPED textures only.** Authoring *new* textures needs EA's DXT compressor + mip generator,
  which is not bit-reproducible — explicitly **stated-tier**, a future phase, not done here.
- **Defensive-not-verified branches.** The `Texture` marshaler's empty/null-payload branch (`Payload.Size == 0`) has
  **no shipped instance** to compare against — every shipped `Texture` carries a DDS, and `field@0x00 (Base)` is `0`
  across all 1575, so a non-zero first dword (were it ever a real flag rather than Base) is also unexercised.
- The big-endian / Xenon path is untouched.

## Credit

Shipped EA texture records; no community content was used or shipped. The recon that studied how textures enter the
engine (0021) credits the community mods named there; this finding reproduces EA's own shipped `Texture` bytes.
