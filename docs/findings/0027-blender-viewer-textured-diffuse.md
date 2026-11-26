# 0027 — Blender viewer: real base-color textures on imported units (milestone 2 + 1.5)

**Status:** Verified · in-GUI confirmed on the real NOD Redeemer by independent review · 2026-11-26
(milestone 1.5 — effect-shader `Texture_0` base slot — added the same day)

> Extends the read-only Blender viewer ([0026](0026-blender-viewer-importer.md)) so imported units show their
> **real diffuse skin** instead of the grey placeholder. Still a **thin front-end to the CLI** — it reimplements
> **no** format logic (CLAUDE.md invariant 3 at ecosystem scale): the texture bytes come through `bab-decompile`
> (the finding-[0024](0024-texture-ondemandtexture-byte-exact-shipped-payload-passthrough.md) `<Payload>`
> pass-through), and the **DDS is decoded by Blender's own native image loader** — no second pixel decoder. This
> is **viewer / stated tier**, not the byte-exact data toolchain; the compiler, comparator, schema `.xsd`, and
> the byte-exact gates were untouched.

## Context — where it bites

The 0026 viewer imported geometry + skeleton but every mesh wore one neutral grey placeholder. A unit is hard to
recognise untextured, and the whole point of an authoring front-end is to see the asset as the game draws it. The
texture bytes were already solved: a shipped `Texture` record carries a **literal complete D3D9 DDS** as a
base64 `<Payload>` (0024). The only missing pieces were **(a)** parsing the texture *names* a mesh references and
**(b)** turning that payload into a Blender image material — both read-direction, no new byte logic.

## Finding — the mechanism (do not re-derive)

1. **A mesh names its textures in its `<FXShader>` block.** The decompiled shape is
   `<FXShader ShaderName="ObjectsNOD.fx"><Constants><Texture Name="DiffuseTexture"><Value>NURedeemer</Value></Texture>…`.
   Each `<Texture>` constant's `Name` is the **slot** (`DiffuseTexture`, `Texture_0`, `NormalMap`, `SpecMap`,
   `ScrollingMaskTexture`, …) and its `<Value>` is the referenced **`Texture`/`OnDemandTexture` asset name**
   (not a file). This is the viewer's only new format-shape knowledge, and it lives in the one allowed place:
   `w3x_xml.parse_mesh` → `MeshGeometry.shader` (a `ShaderTextures`).
   **The base-color slot is chosen by an ordered precedence, not a per-shader special-case** (milestone 1.5):
   `w3x_xml.BASE_COLOR_SLOTS = ("DiffuseTexture", "Texture_0")` — object shaders put albedo in `DiffuseTexture`;
   the **effect/muzzle shaders** (`MuzzleFlash.fx`, and the `DefaultW3D.fx` lens-flare/glow meshes) put their base
   map in **`Texture_0`**. `ShaderTextures.base_color()` returns the first slot the mesh actually has.
   **Only base-color slots feed Base Color** — `NormalMap`/`SpecMap`/`ScrollingMaskTexture`/`Texture_1`(gradient)
   are deliberately excluded.
2. **The referenced `Texture` asset's `<Payload>` is a literal DDS (0024).** Resolve the name to its
   `Texture.<name>.xml`, base64-decode `<Payload>` → raw `.dds` bytes. No DXT work on our side.
3. **Blender decodes the DDS.** `bpy.data.images.load(path)` loads DXT/DDS natively, so the add-on writes the
   `.dds` and hands Blender the path. **A second DDS/DXT decoder is exactly the ecosystem-scale drift the design
   doc forbids** (`docs/design/blender-integration.md`), so we do not fork one.
4. **`OnDemandTexture` has no pixels to show.** Its record carries no payload (streamed on demand / lives as a
   loose file, 0024). That slot — and any name that doesn't resolve — **falls back to the grey placeholder and is
   reported**, never crashed, never fabricated.

## What was built / changed (all owned files; no BYO/EA file, no compiler/comparator/schema touched)

- **`blender/openwrath_import/w3x_xml.py`** — `ShaderTextures` + `TextureAsset` dataclasses; `parse_mesh` now
  parses the `<FXShader>` texture slots into `MeshGeometry.shader`; new `parse_texture()` reads a
  `Texture`/`OnDemandTexture` asset (payload or none). The *only* place XML-shape knowledge grew.
- **`blender/openwrath_import/dds.py` (NEW)** — `decode_payload` (base64 → bytes) + `probe` (a **header-only**
  DDS validity check: magic, `dwSize`, pixelformat size, sane dims, known FourCC / uncompressed). Pure-stdlib,
  **not** a pixel decoder — it exists solely as the byte-decidable sub-anchor (below).
- **`blender/openwrath_import/scene_builder.py`** — `image_material(name, path)` builds a node material with the
  DDS on Base Color, keyed/`check_existing` so meshes sharing a texture share one material + image; `build_mesh`
  takes an optional `material` (placeholder when `None`). The UV layer built in 0026 is reused — no re-read.
- **`blender/openwrath_import/__init__.py`** — `_resolve_texture` + `_base_color_material_for` (resolve via
  `ShaderTextures.base_color()` → decode → `dds.probe` → write `.dds` → `image_material`, with an honest status
  bucket: `textured`/`no_shader`/`no_basemap`/`ondemand`/`unresolved`/`invalid`), wired into both the single-`W3DMesh`
  and the `W3DContainer` import paths; the per-mesh report names the slot used (`via <DiffuseTexture>` /
  `via <Texture_0>`), and the container tally gives textured-vs-placeholder with the bucket breakdown.
  **Bucket honesty (milestone 1.5):** a mesh with an `<FXShader>` but no base-color slot now buckets `no_basemap`
  (textureless by design, e.g. a numeric-only shader); `no_shader` means *genuinely no `<FXShader>`*. (The earlier
  code mislabelled the former as `no_shader`.)
- **`modkit/openwrath`** — `_decode_model` now, after decoding each mesh, gathers its FXShader texture names and
  decodes those `Texture` assets through the **same** `decode` closure into the **same** outdir (invariant 3 — no
  second decode loop). Textures decode via a new **non-fatal** `decode_optional` so an OnDemand/unresolved texture
  degrades to the placeholder instead of aborting the whole model decode.
- **Tests** — `blender/tests/test_textures.py` (wired into `run_tests.sh`) + synthetic fixtures
  (`ow_test_texture.xml` = a valid DXT5 DDS payload, `ow_test_ondemand.xml`, plus an `<FXShader>` on
  `ow_test_cube.xml`).

## Evidence — what is decidable vs stated (honest tiers)

**Byte-decidable, asserted (the two required sub-anchors):**
- **FXShader names parse deterministically.** `test_textures.py` asserts the slots come out of the synthetic cube
  *and* — when the gitignored local fixture is present — out of the **real** `REDEEMER_TOP`:
  `DiffuseTexture=NURedeemer`, `NormalMap=NURedeemer_NRM`, `SpecMap=NURedeemer_SPM`,
  `ScrollingMaskTexture=ScrollTest` (all **ok** this run — the local fixture was present).
- **The payload base64-decodes to a valid D3D9 DDS.** `dds.probe` passes the synthetic DXT5, rejects a corrupted
  header / bad magic / non-base64 (not widened away), and the real-payload path **buckets + reports** any failure
  (it fails the test if a real shipped `Texture` payload — byte-exact per 0024 — doesn't validate). Real local
  `Texture.*.xml` weren't present this run (decode them with `openwrath blender model`) so that leg honestly
  **SKIPPED**, not silently passed.

**Headless Blender exercise (proves the material path end-to-end without a GUI):**
- The self-consistency gate's container import reported **`1/1 mesh(es) got a real base-color texture`** — the full
  resolve → decode → validate → `image_material` path ran inside Blender 5.2.
- A targeted smoke test confirmed **Blender's native loader decoded the DXT5 payload to a 4×4 RGBA image, linked
  to Base Color, and the material is shared on re-call** — so the "let Blender load the DDS" decision holds and no
  decoder fork is needed.
- **Real NOD Redeemer, full container (milestone 1.5):** a headless import of `W3DContainer.NUREDEEMER_SKN` is
  **34/34 meshes textured, 0 placeholder**; **7 distinct DDS** loaded (`NURedeemer`/`2`/`3`, `FXMuzzle`,
  `FXLenzFlare02`, `FXBlast01`, `FXElectricity`), **none failed to decode** (no 0×0 image); 7 shared image
  materials. The per-mesh slot audit shows object parts resolve via `<DiffuseTexture>` and every effect sub-mesh
  (`FX_LAZERGLOW`, `FX_RAGEGLOW`, `MUZZLEFLASH_0x`, `FX_FLASHINGLIGHT*`, `FX_GLOWLIGHTS`, module lights) via
  `<Texture_0>` — each choice inspectable, none special-cased.

**Stated-tier (no byte oracle — never claimed byte-exact):** the material assembly and the in-GUI *look*. This was
**confirmed in-GUI on the real NOD Redeemer by independent review** (same discipline as 0026 — proven by inspection
+ the decidable sub-anchors above).

## Coverage gaps (reported, not hidden)

- **`OnDemandTexture` slots** have no payload → placeholder + report (streamed/loose pixels; out of scope here).
- **Unresolved texture names** (e.g. a test-only `ScrollTest` not in the sampled stream) → placeholder + report.
- **Genuinely textureless shaders** (an `<FXShader>` with no `DiffuseTexture`/`Texture_0`, e.g. a numeric-only
  shader) → placeholder, bucketed `no_basemap` — **correct, not a miss**. ⚠ *Note on the review's premise:* the
  Redeemer's `DefaultW3D.fx` flashing-light/glow meshes were expected to be textureless, but the bytes show they
  **do** carry a `Texture_0` base map (`FXLenzFlare02`, a valid 128×128 DXT1) plus a `Texture_1` gradient — so the
  precedence rule correctly textures them; forcing them to placeholder would have been the actual error. On the
  real Redeemer, **all 34 meshes have a base-color slot** (`no_basemap` is exercised synthetically instead).
- **Only the base-color slot is wired** to a material. `NormalMap`/`SpecMap`/`ScrollingMaskTexture`/`Texture_1`
  (secondary gradient/mask) are parsed and (where decoded) available locally but not mapped into the shader graph —
  a nice-to-have, kept off the required base-color path.
- **Only `static_common`-sourced models sampled**; DDS loading relies on the host Blender's image support
  (verified on 5.2 LTS); big-endian/Xenon untouched.
- **Encoding new DDS** (authoring new textures into the game) is the §4 frontier — **not** this milestone.

## How to apply

Decode a model's textures and view it: `openwrath blender model NUREDEEMER_SKN` (now also decodes the referenced
`Texture` assets), then `openwrath blender view NUREDEEMER_SKN`. Switch the viewport to Material Preview /
Rendered to see the skin. The import report states how many meshes were textured vs placeholder and why.

## See also

- [0024](0024-texture-ondemandtexture-byte-exact-shipped-payload-passthrough.md) — the `Texture` `<Payload>` =
  literal DDS fact this rides on; [0026](0026-blender-viewer-importer.md) — the viewer this extends.
- `docs/design/blender-integration.md` (no-second-parser rule), `docs/design/verification-blind-spots.md` §4
  (stated vs byte-exact).
