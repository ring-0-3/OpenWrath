# 0023 — Shipped `Texture` / `OnDemandTexture` runtime-record layout (byte-inspection recon)

**Status:** Recon / characterization · 2026-11-25 · **not** a byte-exact verification — this de-risks the *next*
pillar (the `Texture` shipped-payload pass-through, [0021](0021-community-mod-texture-geometry-mechanism-recon.md)
build-order milestone 2). No implementation was done here (the boundary of the 0022 phase).

> **⚠ Corrected by [0024](0024-texture-ondemandtexture-byte-exact-shipped-payload-passthrough.md).** The "`Flags@0x00`"
> field named below (the first 4-byte dword, always `0`) is **not a separate field** — it is the universal zeroed
> `BaseAssetType` placeholder every asset carries. The byte-decided model is `{ BaseAssetType Base; DataBlob Payload }`
> (the relocated payload pointer sits at offset 4, leaving no room for a Flags word), confirmed byte-exact in 0024.
> The DDS-blob layout, mip-size/payloadLen equality, and format distribution below all stand; only the "Flags" label
> was a mischaracterization of the Base slot.

> **Byte-inspected, no mod content.** The records below were read directly out of the **shipped** KW `static_common`
> linked stream (EA's own data, bring-your-own, read-only). This answers the explicit open question 0021 left
> dangling: *is the compiled `Texture` record's payload a literal DDS blob or a re-wrapped surface?* — kept distinct
> from what is merely inferred.

## Method

Parsed the `static_common` manifest (same v5 layout `compare-stream.py`/`Manifest.cs` use) to locate every
`Texture` (TypeId `0x21E727DA` = `FastHash("Texture")`, **1575** instances) and `OnDemandTexture`
(TypeId `0x9312B9AC` = `FastHash("OnDemandTexture")`, **123** instances), then extracted each one's instance / relo /
imp bytes from the sibling `.bin` / `.relo` / `.imp` and inspected them. All statements below are **byte-inspected
over the full instance set** unless flagged *inferred*.

## `Texture` (0x21E727DA) — the record **is** a literal D3D9 DDS blob

Every one of the 1575 `Texture` instances has the identical on-disk shape — a **12-byte header then a complete,
standard D3D9 `.dds` file**:

```
offset  size  field
0x00    4     uint   = 0            (all 1575; reserved / flags — always zero in this stream)
0x04    4     ptr    = 12           (all 1575; relocated pointer to the payload, i.e. points at 0x0C)
0x08    4     uint   = ids - 12     (all 1575; payload byte length)
0x0C    N     byte[] = 'DDS ' ...   (all 1575; a literal 128-byte-header D3D9 DDS, full mip chain)
relo          8 bytes = 04 00 00 00  ff ff ff ff   (all 1575; one entry relocating the pointer at 0x04)
imp           0 bytes (all 1575; no imports)
```

**Byte-inspected invariants (full set, 1575/1575):** `field@0x00 == 0`; `field@0x04 == 12`;
`field@0x08 == ids - 12`; the bytes at `+12` are the ASCII magic `DDS ` (`44 44 53 20`) followed by `dwSize = 124`;
the relo buffer is byte-identical (`04000000 ffffffff`).

**The payload is a *literal, complete* DDS file, not a re-wrapped surface** — verified three ways: (a) the 128-byte
D3D9 header is intact (magic, `dwSize=124`, `dwHeight`/`dwWidth`, `dwPitchOrLinearSize`, `dwMipMapCount`,
`DDS_PIXELFORMAT` with a FourCC); (b) the mip-chain byte sizes sum **exactly** to `payloadLen` (e.g.
`Texture:ABBHive_SPM`, 256×256 DXT1, 9 mips: 128-byte header + Σ mip levels = 43832 = `ids − 12`); (c) FourCCs are
exactly the D3D9 set seen in the community pipeline recon (0021). This resolves 0021's open question.

**Format distribution across the 1575 (byte-inspected):**

| FourCC | count | note |
|--------|-------|------|
| DXT1 | 961 | opaque / 1-bit alpha |
| DXT5 | 269 | interpolated alpha |
| DXT3 | 5   | explicit alpha (UI) |
| 0 (uncompressed) | 340 | `DDS_PIXELFORMAT` RGB/ALPHA flags → A8R8G8B8-class, `dwMipMapCount=0` |

Mip counts range 0–11 (0 for the uncompressed UI pages; 9–10 dominate the world textures).

## `OnDemandTexture` (0x9312B9AC) — an 8-byte all-zero placeholder, no pixels

All 123 `OnDemandTexture` instances are **exactly 8 bytes, all zero** (`00 00 00 00 00 00 00 00`), with **`rds=0`
(no relo)** and **`imps=0`**. The lazy runtime twin carries **no pixel payload** in the stream — the 8 bytes are a
zeroed `{pointer=null, length=0}`-shaped struct (null pointer ⇒ no relocation ⇒ `rds=0`). *Inferred:* the engine
streams the actual pixels on demand, resolving them by the record's id/name (the 123 `OnDemandTexture` records
correspond 1:1 to the 123 `OnDemandTextureImage` atlas records of 0022). The record itself holds only identity.

## Recommended approach for the next phase (milestone 2)

- **`Texture` → shipped-payload pass-through (the 0018/W3DMesh pattern), byte-exact for shipped textures.**
  Model the runtime struct as `{ BaseAssetType Base; uint Flags(=0); Ptr<byte> Payload; uint PayloadLength; }` with
  the DDS bytes appended. Decompiler: emit `Flags` + the DDS blob **verbatim** (base64, via the existing
  `AssetInput.ReadBlobBase64` — do not copy it) as a runtime `<Texture>` element. Compiler: write the 12-byte header
  + blob back, re-emitting the single `04000000 ffffffff` relo. This gives **byte-exact for shipped textures without
  reimplementing EA's DXT compressor** — the pixel path stays pass-through, so it is the strongest-oracle slice.
  - **Precondition / schema reach (inferred):** the authoring `AssetTypeTexture.xsd` fields are `pipelineOnly`
    (compile-time directives — 0021), so there is no runtime payload element in the BYO schema to bind to. Expect to
    need an **in-code** runtime binding analogous to `SchemaSet.AugmentRuntimeMeshVertexData`
    ([0018](0018-w3dmesh-byte-exact-via-runtime-vertexdata-passthrough.md)) / `BindRuntimeAnimationChannels`
    ([0014](0014-runtime-w3danimation-dispatch-depends-on-schema-stamped-typeid.md)) — **never** a `.xsd` edit
    (invariant 1). Confirm by attempting the plain path first; add the binding only if the runtime `<Texture>`
    element fails to bind.
- **`OnDemandTexture` → trivial 8-byte record.** It is an 8-byte all-zero POD; modeling two zeroed fields (or a
  null pointer + length) round-trips byte-exact with **no payload handling at all** — likely even simpler than the
  `Texture` pass-through. (The current `OnDemandTexture` struct is an empty placeholder; it needs the two fields
  added before it serializes 8 bytes.)
- **New/authored textures stay stated-tier, never byte-exact** — EA's DXT compressor + mip generator is not
  bit-reproducible (0021 §). Pass-through covers *shipped* textures only.

## Honesty line

- **Byte-inspected (full instance set):** the `Texture` 12-byte header + literal-DDS layout, the field invariants,
  the mip-size/payloadLen equality, the FourCC/mip distributions, the identical relo buffer, and the
  `OnDemandTexture` 8-byte-all-zero shape.
- **Inferred (not tested here):** that the `Texture` `Flags` field (always 0 in this stream) is a format/type flag
  rather than padding; that `OnDemandTexture` pixels stream on demand by id/name; that milestone 2 will need an
  in-code runtime schema binding (the `pipelineOnly` XSD implies it). The actual pass-through was **not built** —
  this is the gate, not the capability.
