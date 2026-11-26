# 0031 — The convenient Blender texture-edit → in-game loop (on the proven record-overlay route)

**Status:** Tooling built + decidable sub-anchors green (2026-11-27). In-game acceptance (the §4 oracle) is the
**user's step** — steps below. **Frontier / §4 — stated-tier, NEVER byte-exact** (editing/encoding pixels has no byte
oracle; EA's DXT compressor isn't bit-reproducible — `docs/design/verification-blind-spots.md` §4).

> Builds the *convenient* edit→package→run loop on the delivery route **already proven in-game** by
> [0030](0030-record-overlay-texture-override-works-on-1.3.md) (record overlay WORKS) — **not** the loose-file route
> [0029](0029-loose-file-texture-override-does-not-shadow-record-backed-unit-textures-on-1.3.md) showed FAILS for
> record-backed unit textures. No new format/overlay logic: it reuses the [0024](0024-texture-ondemandtexture-byte-exact-shipped-payload-passthrough.md)
> `Texture <Payload>` pass-through and the [0017](0017-overlay-mod-overrides-base-gameplay-the-complete-recipe.md)
> complete-overlay assembler. Zero EA pixels in git; the user's edits are their own local data.

## TL;DR

`openwrath texture override <proj> --record NURedeemer --image skin.png` reads the shipped record's format, encodes a
**format-matched** DDS, and authors a `<Texture><Payload>` record override; `openwrath mod build-local <proj> --install`
packages the **LOCAL-ONLY** `static_mod` overlay (0030 route); `openwrath mod activate <name>` swaps the master-SkuDef
`add-config` (the papercut 0030 did by hand) and `deactivate` reverses it. In Blender: **File ▸ Export ▸ OpenWrath
Texture Edit (→ in-game)** saves the edited image and shells out to the same CLI. Stated-tier; the in-game render is the
only acceptance.

## What was built (all owned code; Blender stays a thin front-end — invariant 3)

- **CLI (`modkit/openwrath`)**
  - `texture override <proj> --record R --image IMG [...]` / `--solid RRGGBB` — the authoring half. For each record:
    read the shipped format (`_decode_texture_record` → the 0024 decode + `dds.probe`), produce a matched DDS,
    **assert it matches** the shipped FourCC + W×H + mip count (`_dds_match_reason`), base64 it into a
    `<Texture id><Payload>` (`_texture_override_xml`, the 0024 shape), and add it to `mod.toml` sources
    (`_add_source_line`, preserving a `[strings]` table). Scaffolds the project + a `.gitignore` if absent.
  - `texture encode --like R --out X.dds (--image IMG | --solid RRGGBB)` — the pure encode step (no packaging).
  - `_encode_image_to_dds` drives an **external** encoder (nvcompress → nvtt_export → texconv, detected on PATH;
    resizes via Pillow when present) — we never hand-roll a DXT compressor. `_synth_solid_dds` is the
    **no-encoder control** (the exact 0029/0030 constant-block DDS; DXT1 magenta `color0=0xF81F`).
  - `mod activate <name>` / `deactivate [<name> | --all]` — back up the master SkuDef (`.openwrath-orig`), add/remove
    exactly our `add-config` line (`_win_mods_skudef_line`), warn on static-overlay mutual exclusivity (0017) and
    online safety (0030), refuse while the game runs.
- **Blender add-on (`blender/openwrath_import/`)** — `OPENWRATH_OT_export_texture` + `export_textures()`: the importer
  tags each base-color Image-Texture node with the `Texture` asset name on its `.label` (`image_material`), so that
  label IS the record id. The operator saves the edited image to PNG and invokes `cli.run_texture_override`
  (`cli.build_texture_override_argv` — the ONE CLI invocation, mirroring `build_decode_argv`/`build_compile_argv`).
  The add-on forks **no** DDS/record/overlay logic.

## Decidable sub-anchors (verified WITHOUT the game)

- **DDS probe + format match.** `texture encode --like NURedeemer --solid FF00FF` read the real shipped record as
  **512×512 DXT1, 10 mips** (matching 0029) and produced a `dds.probe`-valid, **format-matched** 174,904-byte DDS; a
  wrong FourCC/dims/mips/compression-class is rejected on every axis (test).
- **Payload round-trip (integrity).** The authored `<Payload>` base64-decodes to the same bytes (test); and the
  authored DDS appears **verbatim** inside the compiled `.asset` (compile via the real 0024 pass-through; `mod check`
  clean, DDS present at the DataBlob offset) — what you author is what compiles.
- **Overlay completeness.** `build-local` is the 0017 complete-entry-list assembler **proven in-game by 0030** (same
  code path; not re-run here — honestly noted).
- **Activate/deactivate.** Adds exactly our line, backs up the pristine SkuDef, is idempotent, removes exactly our
  line, and `--all` restores the pristine backup (tests). Suites: modkit **35/35**, blender texture/parser/export all
  green.

## In-game gate (the oracle — the user's step)

```
# 1. (Blender) import the unit, confirm it imported "textured", paint the base-color image, then
#    File ▸ Export ▸ OpenWrath Texture Edit (→ in-game); set the project dir. (Or run the CLI directly:)
openwrath texture override ~/mods/RedeemerSkin --record NURedeemer --image ~/skin.png
#    (control, no encoder:  --solid FF00FF  instead of --image)
# 2. build the LOCAL-ONLY overlay + install to Mods/
openwrath mod build-local ~/mods/RedeemerSkin --install
# 3. activate (swaps the master SkuDef; warns online-safety)
openwrath mod activate RedeemerSkin
# 4. launch Kane's Wrath on a STANDARD map (never R23/tournament — 0017); verify the skin; screenshot.
# 5. turn it off:
openwrath mod deactivate RedeemerSkin
```
A full recolor = override the unit's other skin records too (e.g. the Redeemer's `NURedeemer_D` upper-body + the
`NURedeemer2/_D`, `NURedeemer3/_D` leg records — the per-record precision 0030 observed).

## Honesty / scope — tier, posture, gaps

- **STATED-TIER, never byte-exact.** New/edited pixels have no byte oracle; nvtt/texconv ≠ EA's compressor. The CLI
  says so on every success line. The pass-through *mechanism* is byte-exact for **shipped** payloads (0024) — editing
  is not.
- **LOCAL-ONLY.** `build-local` embeds EA-derived entry-list metadata (0017) → not shareable; marked local-only (same
  posture as `diff-plus-assemble-at-install`). The shareable zero-EA diff form is future work.
- **Online safety.** A record overlay changes stream identity → **NOT** inherently C&C-Online/replay-safe (0030);
  `activate` warns and it is a **mod** target, never a base edit.
- **Zero-EA in git.** The scaffolded project gitignores `dist-local/` + `*.dds`; the base64-in-XML override is the
  user's own local data (no EA/edited pixels committed). Only code + this finding are committed.
- **Gaps (honest):** needs an external DDS encoder for real images (detected; clear failure + `--solid` fallback);
  Pillow resizes a non-matching source (else dims must pre-match); the auto-encoder targets only mip-count = 1 or the
  full chain (an arbitrary count errors); `--solid` covers DXT1/DXT5/A8R8G8B8; multi-record units need one `--record`
  each; `OnDemandTexture`/loose textures are a different (unproven-for-units) route; SkuDef line placement is appended
  (0030 worked — if an overlay doesn't take effect, load order may matter, 0017).

## Reused symbols (review: no second DDS/record/overlay path)

`SchemaSet.BindRuntimeTexturePayload` / `Marshaler.Texture` (0024 pass-through, untouched); `mod build-local` /
`assemble_complete_stream.py` / the 0017 overlay machinery; `_decompress_base_stream` + the add-on decode builder +
`w3x_xml.parse_texture` to read the shipped format; `blender/openwrath_import/dds.py probe` for validity;
`_win_mods_skudef_line` for activation; `scene_builder.image_material` node label for the record↔image map;
`cli.build_decode_argv`/`build_compile_argv` siblings → the new `build_texture_override_argv` (one CLI invocation).

## Credit

Shipped EA texture records defined the format matched here; the control payload contains no EA pixels. The
community-mod recon that mapped the texture routes (0021) credits the mods named there.
