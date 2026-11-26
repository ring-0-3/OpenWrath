# 0029 — Loose-file `add-search-path` override does NOT shadow a record-backed unit texture on retail 1.3

**Status:** In-game result (frontier / §4 — in-game acceptance is the oracle, never byte-exact) · 2026-11-26 ·
**negative result, confirmed in-game** on retail 1.3 / Patch103

> The §4-frontier test from [0021](0021-community-mod-texture-geometry-mechanism-recon.md)'s build-order step 0
> ("loose-file texture override via `add-search-path` — cheapest win"). The recon flagged the engine's honoring of a
> loose file over a packed record as **attested-not-tested**; this is the test. **It does not work** for a
> record-backed unit texture on retail 1.3 — so the cheap route the recon hoped for is **not** the reliable path for
> unit skins. The reliable route is the **record overlay** (0017 + 0024), which is also EA's own method. No mod/EA
> content was used; the test textures are synthetic solid colors.

## TL;DR

Dropping an edited loose `.dds` (named exactly after the shipped `Texture` record id, matching its format) into an
**already-active `add-search-path` directory** did **not** change the unit's appearance in-game. Record-backed unit
textures (the `Texture` records of [0024](0024-texture-ondemandtexture-byte-exact-shipped-payload-passthrough.md))
have **no loose file in any BIG to shadow**, and the retail engine does not fall back to a file probe for them. The
4K-ecosystem loose-file route (Mod 3 in 0021) therefore does **not** generalize to retail-1.3 unit skins as-is.
**Use the record-overlay route for unit textures** (next step below).

## What was tested (decidable sub-anchors all met)

- **Target (derived from data, not guessed):** the Nod Redeemer's diffuse. Parsing the shipped `static_common`
  manifest + `.bin` (reused `parse_manifest`; record layout per 0024 = 12-byte header + literal DDS) shows the
  Redeemer ships **four `Texture` records, zero `OnDemandTexture`**:
  `NURedeemer` / `NURedeemer_D` = **512×512 DXT1, 10 mips**; `NURedeemer_NRM` / `NURedeemer_SPM` = 256×256 DXT1, 9
  mips. (Also confirms 0021's accepted format: **D3D9 DXT1, no DX10 ext, full mip chain**.)
- **Test payload (zero-EA):** synthetic solid-color DXT1 512² 10-mip `.dds` for `NURedeemer` + `NURedeemer_D`, format
  byte-matched to the shipped records, validated by `blender/openwrath_import/dds.py probe` (valid=True,
  512×512/mips=10/DXT1). Not EA pixels.
- **Activation (no EA file edited):** the install's master SkuDef already runs `add-config 4KMod\config.txt`, which
  already declares `add-search-path 4KTextureMod/`. Test files were dropped into that **already-active** search root —
  **no SkuDef edit, no second mod/SkuDef path** written.
- **Path disambiguation in one launch:** color-coded — **MAGENTA** at the flat root (`4KTextureMod/NURedeemer.dds`),
  **CYAN** under `4KTextureMod/art/textures/NURedeemer.dds` (the two most-likely conventions, from the SDK
  `AssetTypeTexture.xsd` `File="art\Textures\…"` and EA's own `art\terrain\…` VFS layout).
- **In-game:** standard skirmish map (not R23/tournament — 0017), Nod, Redeemer in view, zoomed.

## Result (the oracle: in-game)

**Unchanged — neither MAGENTA nor CYAN.** The Redeemer rendered with its **full original skin** (all panel detail,
cockpit glass, mechanical detail intact; the visible purple was the player's **team color** on the emissive/team
channel, not the diffuse). A solid-color override would have flattened the entire hull to one detail-free color — it
did not. **The loose `.dds` was not honored for this record-backed texture.**

## Why this is the expected answer (data corroboration — not just one screenshot)

- **No file to shadow.** Retail unit textures live as `Texture` **records** embedded in `static_common`; the
  StaticStream/GlobalStream BIGs contain **0** loose `.dds`. The loose-file override rule — proven for files that *do*
  have a BIG entry (the `shaders\compiled\muzzleflash.fxo` override present in this very search root; terrain
  `art\terrain\*.tga`) — has nothing to shadow for a record.
- **EA agrees.** EA's own retail texture fix, `Patch103\102texturefix.big`, ships a **`Static_mod` record overlay +
  `.version` redirects** (the 0017 shape) — *not* loose files. EA overrides retail textures by **record overlay**.

## Honesty / scope — what this does and does NOT claim

- **Claims:** on retail 1.3, a loose `.dds` named after the record id, in the two tested path conventions (flat +
  `art/textures/`), exact record-id casing, `.dds` extension, in an active search path, does **not** override a
  record-backed unit texture. Confirmed in-game.
- **Does NOT claim loose-file override is impossible in general.** Not exhausted: other path conventions (a
  unit/faction subdir, a texture-cache path), alternate casing on a case-sensitive host FS, the `.tga` route (the 4K
  config also declares `add-search-path tgaoverride/` — untested here), or **file-backed** textures (terrain), which
  may still be loose-overridable. A **positive control** (override a file-backed terrain `.tga` to confirm the search
  path is honored at all) was not run — the search path's liveness rests on the pre-existing `muzzleflash.fxo` whose
  in-game effect was not independently confirmed. These are cheap follow-ups if the loose route is ever revisited.
- **Frontier tier.** In-game acceptance is the only oracle; nothing here is byte-exact (editing pixels + DXT encode
  is not bit-reproducible — verification-blind-spots §4).

## The reliable route for a record-backed unit texture: record overlay (next build)

Override the `Texture` record itself via the **0017 overlay** carrying a new `NURedeemer` `Texture` record whose
`<Payload>` is the edited DDS (the 0024 pass-through writes the DDS straight into the `DataBlob`). This is EA's own
method (`102texturefix.big`) and reuses tooling we already have: `modkit/lib/build_overlay.py` (the sparse
differential + `.version` + low-LOD/WB twins) + the 0024 `Texture` marshaler. **Online-safety differs from loose
files:** a record overlay changes a stream's identity/checksum, so unlike the (hoped-for, now-disproven) loose route
it is **not** inherently C&C-Online / replay-safe — treat it as a mod target, not a base-stream edit, and flag it.

## Reused symbols (review: no second SkuDef/mod path written)

`parse_manifest` (modkit/openwrath) to locate the record from data; the **already-active** `add-search-path
4KTextureMod/` (rode the live path rather than writing a competing SkuDef); `blender/openwrath_import/dds.py probe`
for test-DDS validity. Harness: `scratchpad/texovr-test/{run-test,cleanup}.sh` (synthetic, reversible, refuses while
the game runs).

## DDS encoder note for the convenient edit→package loop (Prompt 3b)

Recommend **NVIDIA Texture Tools (`nvcompress`/`nvtt_export`)** — native-Linux, emits **legacy D3D9 DDS by default**
(DXT1/5 + full mip chains, **no DX10 extended header**, which 0021/0024/this finding confirm the engine requires);
de-facto KW/SAGE community tool. `nvcompress -bc1`/`-bc3`. Gate every produced file through `dds.py probe` before
packaging. Avoid `texconv` unless forced `-dx9` (can emit DX10-ext headers). Encoding new pixels is **stated-tier**.
