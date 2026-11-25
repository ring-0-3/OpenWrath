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
| **Kane's Wrath R25n 4K Edition (Standard)** | true frontier (HD textures) | [ModDB](https://www.moddb.com/games/cc-kanes-wrath/addons/4k-add-on-installer) / kaneswrath.com (installer supplied by the user) | KW 4K/UHD remaster team | **byte-inspected** (NSIS unpacked in quarantine; targets **R25**, not retail 1.3) |

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

### Mod 3 — "Kane's Wrath R25n 4K Edition (Standard)" (true-frontier texture tier) — **contents byte-inspected; engine behavior attested-not-tested**
The user supplied the installer; it was byte-inspected in quarantine (a Nullsoft/NSIS installer: non-solid LZMA,
props `5D 00 00 80 00` = lc3/lp0/pb2, 8 MB dict — decompressed with Python stdlib `lzma`, no mod bytes copied out).
It targets **R25** (a community patch release, *not* retail 1.3) — a version-blindness note that matters. **Two
levels of claim, kept distinct:** the mod's *contents* (install directives, DDS format/resolution) are genuinely
byte-read here; the *engine's runtime response* to them (resolving a loose file over a packed one) is **attested**
— documented `add-search-path` semantics + the fact that this pack demonstrably works for its users — **not tested**
(the engine was not run here). Same distinction as the comparator/in-game blind spot.

1. **What/where (verified from the install directives):** it does **not** repack a base BIG and does **not** touch
   gameplay records. It mounts via the mod launcher's **SkuDef/config**, with exactly three directives:
   `add-search-path 4KTextureMod/` · `add-big patch2.big` · `add-config ..\1.0\config.txt`.
2. **Payload format (verified by decompressing the NSIS blocks and reading DDS headers directly):** standard **D3D9
   DDS** (128-byte header, FourCC at 0x54, **no** DX10 extended header), **DXT1 and DXT5**, with **full mip chains**
   and resolutions up to **2048×2048** (e.g. `2048×2048 mips=12 fourcc=DXT5`, `256×1024 mips=11 fourcc=DXT1`) —
   genuinely high-res vs EA's typical 512/1024. (~2373 LZMA sub-blocks in the archive, the bulk of them textures.)
3. **Records vs files: raw FILES** (verified: the payload is loose DDS files, no `Texture`/`OnDemandTexture` records
   in the archive). The 4K textures are **loose DDS files** dropped into the `4KTextureMod/` search-path directory
   (plus the small `patch2.big`). *Attested-not-tested:* that the engine's file resolver then overrides the
   BIG-packed originals **by path/name** — standard `add-search-path` behavior, and the premise that makes the pack
   work, but not observed here. Replacing no records is exactly why it stays **C&C-Online-compatible** (no
   gameplay/type-hash change).
4. **Load path:** the three directives `add-search-path 4KTextureMod/` + `add-big patch2.big` + `add-config
   ..\1.0\config.txt` are *verified* (read from the installer; `..\1.0\` is the launcher's R25 version folder, i.e.
   it chains the base R25 config). That this chain is what the engine honors to activate the override is
   *attested-not-tested*. The mechanism is **distinct from, and simpler than, the 0017 `.version` overlay** — no
   record modeling is needed to override a texture, just a correctly-pathed loose DDS.

**Byte-exact-invertible? No, by definition** — new higher-res content with no EA original to match: pure
stated-tier. But the mechanism's *contents* are now byte-read (not inferred), and — engine-honoring attested — it is
the **easiest texture entry point of all**: loose-file override via `add-search-path`, which OpenWrath would still
gate on an **in-game acceptance test** before claiming it works.

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

0. **Loose-file texture override via `add-search-path` (cheapest win — the route the 4K pack rides)** — overriding an
   *existing* texture needs **no record support at all**: drop a correctly-pathed D3D9 DDS (DXT1/5, mip-chained)
   into a SkuDef `add-search-path` directory and the engine's file resolver prefers it over the BIG-packed original
   by name. This is a packaging/tooling feature (emit a SkuDef + a search-path tree), gated on **in-game
   acceptance**, not a compiler change — and it is how the whole 4K ecosystem ships. Best first texture capability.
1. **`PackedTextureImage` / `OnDemandTextureImage`** — plain data records (Base + a texture ref + three
   ICoord2D). No lossy pixel pipeline → should round-trip **byte-exact** against shipped bytes like the 0019
   connective-tissue types. Cheaply promotes two "Not modeled" types and de-risks the texture-record plumbing.
2. **`Texture` / `OnDemandTexture` record, payload pass-through** — model the runtime record (Base/id/hash + the
   pixel payload) and emit the shipped compiled payload **verbatim** (the W3DMesh pattern). Byte-exact for *shipped*
   textures, no compressor reimplementation. **Precondition:** open a shipped `static/global` texture record first
   to confirm the runtime byte layout (is the payload a literal DDS blob or a re-wrapped surface? — inferred, not
   yet opened).
3. **Authoring frontier (new *records* with new textures)** — ingest a source DDS, emit an engine-accepted texture
   payload *as a record*. Gated on an **in-game acceptance test**, explicitly **stated-tier, never byte-exact**.

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
  third-party BIGs/streams; **and the 4K pack itself** — NSIS install directives (`add-search-path`/`add-big`/
  `add-config`) + DDS headers decompressed straight from its NSIS blocks (format/resolution/mips only, no pixels).
- **Inferred / not-yet-opened:** whether the compiled *`Texture` record* payload is *literally* a DDS blob vs a
  re-wrapped surface (the XSD + `pipelineOnly` design imply re-encode, but a shipped `Texture` runtime record was
  **not opened here** — confirm before milestone 2). Note the 4K pack sidesteps this entirely: it ships loose DDS
  **files**, not `Texture` records.

## Bottom line

The texture and geometry paths are **"stated-tier achievable"** for OpenWrath, and the mechanism is fully
characterized **without any mod content**. Two distinct texture routes are now characterized (mechanisms byte-read;
engine-honoring attested-not-tested): (1) **new content as asset
records** — a new unit enters as `Texture`/`OnDemandTexture`/`PackedTextureImage` records + the W3D model graph +
`FXParticleSystemTemplate`, referencing raw **D3D9 DDS**, packed in a BIG via `add-big`/`add-config` (Mod 2); and
(2) **override existing textures as loose files** — drop correctly-pathed D3D9 DDS (DXT1/5, mip-chained, up to
2048²) into a SkuDef `add-search-path` dir and the engine prefers them by name (Mod 3, the 4K pack — the whole 4K
ecosystem rides this). Build order: **loose-file `add-search-path` override first** (cheapest, no record modeling,
in-game-acceptance gate) → byte-exact texture **records** (`PackedTextureImage`) → shipped-payload pass-through →
*new* record-borne HD content last — never claimed byte-exact (EA's DXT compressor is not bit-reproducible).
