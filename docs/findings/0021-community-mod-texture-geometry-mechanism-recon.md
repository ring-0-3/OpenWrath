# 0021 — How non-EA textures / geometry / particles enter the KW engine (community-mod mechanism recon)

**Status:** Recon / characterization · 2026-11-25 · **not** a byte-exact verification (frontier tier — see
[verification-blind-spots](../design/verification-blind-spots.md) §4 and
[community-mods-as-frontier-reference](../design/community-mods-as-frontier-reference.md))

> **Mechanism only — no mod content.** Three community mods were acquired into a quarantine dir **outside** the repo
> and byte-*inspected* for their **loading/format mechanism**. Nothing of theirs is copied, committed, or reproduced
> here (no asset bytes, pixels, or verbatim files). A community mod is **not** ground truth; it is an
> existence-proof that "the engine accepts X via path Y." The oracle for eventual texture work remains EA's own
> originals (byte-exact where one exists) + **in-game acceptance**, never a mod's bytes.

## What was examined (and credit to the authors)

| Mod | Tier | Source | Author(s) | Status |
|---|---|---|---|---|
| **KWBandage** | data / overlay | [github.com/theHostileNegotiator/KWBandage](https://github.com/theHostileNegotiator/KWBandage) | theHostileNegotiator + KW community | **byte-inspected** |
| **KW Mod SDK 2020 "SampleMod"** (new units) | authoring / re-pack (geometry+texture+FX) | [github.com/JenkinsTR/KanesWrath-MODSDK-2020](https://github.com/JenkinsTR/KanesWrath-MODSDK-2020) | Jenkins/JMDigital/EALA/DarthJane/JonWil, built on WrathEd (Bibber et al.) | **byte-inspected** |
| **Kane's Wrath 4K Edition (R25)** | true frontier (HD textures) | [ModDB](https://www.moddb.com/games/cc-kanes-wrath/addons/4k-add-on-installer) / kaneswrath.com | KW 4K/UHD remaster team | **hypothesis-not-verified** (installer `.exe`; ModDB 403 to automation — never downloaded) |

Also credited: WrathEd ([CNCNZ](https://cncnz.com/wrathed-v1-10-released/)). All tiers from
[community-mods-as-frontier-reference](../design/community-mods-as-frontier-reference.md) are represented.

## The four questions, answered per mod

### Mod 1 — KWBandage (data/overlay tier) — verified by inspection
1. **What/where:** a gameplay/UI fix pack shipped as **overlay linked streams** (`*_mod.manifest` + `.version`
   redirects), *not* repacked base BIGs — the overlay chain of finding
   [0017](0017-overlay-mod-overrides-base-gameplay-the-complete-recipe.md).
2. **Payload:** compiled SAGE linked streams (`.manifest`+`.bin/.relo/.imp`), built by WrathEd against the `*_common_2`
   (1.2) base with unchanged assets **deferred to the base** (the `\x02` base-ref), plus a low-LOD twin. Ships some
   uncompiled art (`.w3x`/`.dds`/`.fx`) too.
3. **Records vs files:** replaces **asset records** (gameplay/UI) in the overlay streams.
4. **Load path:** a `.version` file containing `_mod\n` (hex `5f 6d 6f 64 0a`) — the engine appends the postfix and
   loads the mod stream in place of the base. **Already SOLVED** in OpenWrath (`modkit/lib/build_overlay.py`).
   New detail: KWBandage also uses a `-version:"_common_mod"` variant (overlay at the `static_common` *family*
   level, `static.version=_common_mod\n`) — this is attempt #5 in 0017, here confirmed in the wild. **Corroborates
   0017; nothing new to build.**

### Mod 2 — KW Mod SDK "SampleMod" / new units (authoring + re-pack tier) — verified by inspection
The richest find: a buildable new-unit example showing exactly how non-EA geometry + textures + FX enter the engine.
1. **What/where:** a **standard (Core-replacement) mod** — `BuildMod.bat` compiles unit XML+art into
   `*_Streams.big` + `*_Misc.big`, mounted by a `.skudef` of plain `add-big` lines, activated by `add-config` in
   the master SkuDef. A new unit is a directory of asset **records**.
2. **Payload:**
   - **Geometry:** authored `.w3x` (XML W3D-authoring source) → WrathEd compiles to the runtime W3D layout. Carries
     `<W3DMesh>` with `<FXShader>` + named texture slots (Diffuse/Normal/Spec/ScrollingMask). Maps directly onto
     OpenWrath's byte-exact `W3DMesh/W3DContainer/W3DHierarchy/W3DAnimation/W3DCollisionBox`.
   - **Textures:** standard **D3D9 DDS** (128-byte header, no DX10 ext). Header survey (fields only, no pixels):
     FourCCs **DXT1 / DXT3 (UI) / DXT5 / uncompressed A8R8G8B8**; world textures carry full mip chains, UI atlases
     mips 0/1.
   - **Particles:** ordinary `FXParticleSystemTemplate` records — **byte-exact in OpenWrath today** (finding
     [0020](0020-fxparticlesystemtemplate-byte-exact-plain-pipeline-plus-required-empty-module.md)).
3. **Records vs files: both.** A unit ships **records** (`Texture`, `OnDemandTexture`, `PackedTextureImage`,
   `W3DMesh`, `FXParticleSystemTemplate`, `GameObject`…) that reference raw **DDS files** alongside. The `Texture`
   record is the binding glue; per the SDK XSD (`AssetTypeTexture.xsd`) its fields (`File`, `OutputFormat` default
   DXT1, `GenerateMipMaps`, `AllowAutomaticResize`, `Type`) are **`xas:pipelineOnly="true"`** — i.e. **compile-time
   directives**: the compiler reads the source DDS, **re-encodes to OutputFormat + generates mips**, and the runtime
   record stores only `Base`(id/hash) + the processed pixel payload. `OnDemandTexture` is the lazy runtime twin;
   `PackedTextureImage`/`OnDemandTextureImage` are UI-atlas records (id + a `Texture` ref + ICoord2D
   Dimensions/Coords/TextureDimensions).
4. **Load path:** `add-big` (mod `.skudef`) → `add-config` (master SkuDef); the engine resolves a model's logical
   texture-slot name → StringHash → the `Texture`/`OnDemandTexture` record in the mounted stream; UI resolves
   `PackedTextureImage` id likewise.

### Mod 3 — KW 4K Edition (true-frontier texture tier) — **hypothesis-not-verified**
Not downloaded (ModDB 403 to automation; installer-only). From public descriptions only: a one-click installer of
HD textures that the retail engine loads; advertised **C&C-Online-compatible**, which strongly implies a
**texture/art-only override** that does **not** touch gameplay type-hashes — most likely a larger texture-only
overlay riding the same slot as the 1.3 patch's art stream (0017 notes that stream is ~98% zero-data, ~384 art
assets carry bytes), or `add-big`/`add-config`. **Byte-exact-invertible? No, by definition** — new higher-res
content with no EA original to match: pure stated-tier. **Recommendation: do not chase the `.exe`** — Mod 2 already
gives a byte-inspectable, legally-cleaner existence-proof of the identical mechanism; the 4K pack only scales
resolution.

## Implicated COVERAGE types

All currently "Not modeled": **`PackedTextureImage`, `OnDemandTextureImage`** (plain UI-atlas data records);
**`Texture`, `OnDemandTexture`** (metadata record + a lossy pixel pipeline). The W3D model-graph types are byte-exact
today for **pass-through**, but authoring re-pack stays UNVERIFIED (finding 0018's gate). `FXParticleSystemTemplate`
is byte-exact (0020).

## Is the texture path byte-exact-invertible?

**No for the pixel payload.** The `pipelineOnly` design confirms the compiler runs a DXT compressor + mip generator
that is not bit-reproducible — exactly the §4 frontier. **But the texture *records* and the *shipped* payload are
tractable:** a shipped texture's compiled bytes can be passed through verbatim (the 0018/W3DMesh pattern), giving
byte-exact for shipped textures without reimplementing EA's compressor.

## Recommended first implementation milestones (ordered by oracle strength)

1. **`PackedTextureImage` / `OnDemandTextureImage` FIRST** — plain data records (Base + a texture ref + three
   ICoord2D). No lossy pixel pipeline → should round-trip **byte-exact** against shipped bytes like the 0019
   connective-tissue types. Cheaply promotes two "Not modeled" types and de-risks the texture-record plumbing.
2. **`Texture` / `OnDemandTexture` record, payload pass-through** — model the runtime record (Base/id/hash + the
   pixel payload) and emit the shipped compiled payload **verbatim** (the W3DMesh pattern). Byte-exact for *shipped*
   textures, no compressor reimplementation. **Precondition:** open a shipped `static/global` texture record first
   to confirm the runtime byte layout (is the payload a literal DDS blob or a re-wrapped surface? — inferred, not
   yet opened).
3. **Authoring frontier (new textures)** — ingest a source DDS, emit an engine-accepted texture payload. Gated on an
   **in-game acceptance test**, explicitly **stated-tier, never byte-exact**.

**Exact format the stated-tier texture path must emit:** a standard **D3D9 DDS** — 128-byte header (`'DDS '` magic;
height/width at 0x0C/0x10; FourCC at 0x54 ∈ {`DXT1`,`DXT3`,`DXT5`, or 0 + RGB flags for A8R8G8B8}; `dwMipMapCount`
at 0x1C), full mip chain for world textures — as the payload of a `Texture`/`OnDemandTexture` record bound by
StringHash of the logical slot name, delivered via `add-big`+`add-config` or the 0017 `.version` overlay.

## Toolchain robustness on third-party bytes (bonus signal — PASS)

OpenWrath's own tools, run against SDK-built third-party BIGs/streams, **crashed on nothing and mis-parsed
nothing**: `pytools/biglist.py` parsed a 147-entry `BIG4` cleanly; `bigextract.py` extracted; the RefPack guard
(`byte[1]==0xFB`) correctly classified an uncompressed `.bin` as not-RefPack; `bab-decompile typescan` tallied a
third-party audio stream by type with instance names. (The `.cdata` duplicate case-variant files are the engine's
per-asset cache form — expected.)

## Honesty line

- **Byte-inspected:** KWBandage build script + `.version` bytes + tree; SampleMod `Mod.xml` / unit records /
  `.w3x` texture-slot refs; 1723 DDS headers (fields only, **no pixels**); the SDK XSDs; OpenWrath tools vs
  third-party BIGs/streams.
- **Inferred / hypothesis-not-verified:** the **entire 4K-pack mechanism** (never downloaded); and whether the
  compiled `Texture` payload is *literally* a DDS blob vs a re-wrapped surface (the XSD + `pipelineOnly` design
  imply re-encode, but a shipped `Texture` runtime record was **not opened here** — confirm before milestone 2).

## Bottom line

The texture and geometry paths are **"stated-tier achievable"** for OpenWrath, and the mechanism is fully
characterized **without any mod content**. A new unit enters as asset **records**
(`Texture`/`OnDemandTexture`/`PackedTextureImage` + the W3D model graph + `FXParticleSystemTemplate`) referencing raw
**D3D9 DDS** files, packed in a BIG mounted via `add-big`/`add-config`, or overridden via the 0017 `.version`
overlay. Build order: byte-exact texture **records** first (start with `PackedTextureImage`), shipped-payload
pass-through next, and *new* HD content last as an explicit in-game-acceptance stated tier — never claimed byte-exact
(EA's DXT compressor is not bit-reproducible).
