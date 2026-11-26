# 0030 — Record-overlay texture override WORKS on retail 1.3 (unit skin edited in-game)

**Status:** In-game result (frontier / §4 — in-game acceptance is the oracle, never byte-exact) · 2026-11-26 ·
**positive result, confirmed in-game** on retail 1.3 / Patch103

> The reliable texture-editing route, proven. Finding [0029](0029-loose-file-texture-override-does-not-shadow-record-backed-unit-textures-on-1.3.md)
> showed the loose-file route does NOT override a record-backed unit texture on 1.3; this is the fallback it named —
> an edited DDS carried as a `Texture` **record** in a `static_mod` overlay (the [0017](0017-overlay-mod-overrides-base-gameplay-the-complete-recipe.md)
> route) — and it **works**. This is EA's own method (`Patch103\102texturefix.big` ships exactly this shape). No
> mod/EA content was used; the test payload is a synthetic solid color.

## TL;DR

A `static_mod` overlay carrying two edited `Texture` records (`NURedeemer`, `NURedeemer_D`, each a synthetic solid
**magenta** DXT1 512² payload) **changed the Nod Redeemer's skin in-game** — the upper body rendered magenta. This
proves OpenWrath can edit a shipped unit texture end-to-end on retail 1.3 **as a stated-tier capability** (the pixels
are new → not byte-exact, by definition). The route reuses only existing, verified machinery: the 0024 `Texture`
`<Payload>` pass-through + `modkit/openwrath mod build-local` (the 0017 complete-overlay assembler).

## How it was built (all reused tooling — no new format logic)

1. **Authoring source** — a plain `<AssetDeclaration>` with two `<Texture id="NURedeemer"><Payload>…base64 DDS…</Payload></Texture>`
   records. The compiler accepts `<Payload>` because `SchemaSet.BindRuntimeTexturePayload()` runs before `Compile()`
   (0024); `Marshaler.Texture` writes the decoded DDS straight into the record's `DataBlob`. No `File`/pipeline
   re-encode — the synthetic DDS bytes pass through verbatim.
2. **Payload** — a synthetic solid-magenta **D3D9 DXT1, 512×512, 10-mip** DDS, byte-format-matched to the shipped
   `NURedeemer` records (dims/format/mip-count read from shipped `static_common` via `parse_manifest` + the 0024
   12-byte-header layout), validated by `blender/openwrath_import/dds.py probe`. **Zero EA pixels.**
3. **Overlay** — `openwrath mod build-local` assembled the complete `static_mod` (21,747 entries) from the running
   patch overlay + base chain and **spliced** the two edited records (REPLACE path; `31 replaced` incl. the
   instant-build test aids below), emitting the `data\static.version=_mod\n` activation + lowercase names (0016).
   Built artifact verified before launch: both records carry `DDS ` magic, 512², DXT1, first-block color0=`0xF81F`
   (magenta), TypeHash `0xB30F14DB` (the harvested KW value, 0024).
4. **Activation** — swapped into the `static_mod` slot in the master SkuDef (overlay families are mutually exclusive,
   0017), SkuDef backed up and restored.

## Result (the oracle: in-game)

**The Redeemer's upper body (torso, head, arms, shoulders) rendered bright magenta.** The override took effect — the
record-overlay texture route is confirmed on retail 1.3. No crash; the match ran normally.

**Per-record precision (bonus observation).** The **legs stayed stock**, because the epic Redeemer is textured by
*several* skin records and only the two overridden (`NURedeemer`/`NURedeemer_D` = upper body) changed. The leg skins
live in the sibling records `NURedeemer2`/`NURedeemer2_D` (512²) and `NURedeemer3`/`NURedeemer3_D` (128²). This
cleanly demonstrates the override is **per-`Texture`-record**, mapping exactly to the model's texture-slot bindings —
a full recolor just means overriding the additional records.

## Online-safety — DIFFERENT from the (disproven) loose-file route

A record overlay **replaces records and changes the stream's identity/checksum**, so unlike loose files (which
replace nothing) it is **not inherently C&C-Online / replay-safe**. Treat it as a **mod target**, not a base-stream
edit: fine for single-player / local / consenting-lobby use, but it is a different online-safety class than the
loose-file route 0029 hoped for. (The loose route would have been safe but does not work for record-backed textures.)

## Honesty / scope

- **Stated-tier, never byte-exact.** New pixels + (here, synthetic) payload — in-game acceptance is the only oracle.
  The *pass-through mechanism* is byte-exact for shipped payloads (0024); *authoring new pixels* is not.
- **Confirmed:** a `static_mod` overlay with edited `Texture` records visibly changes a unit skin on retail 1.3,
  no crash. One unit (Redeemer), two records, one install.
- A real edit-a-texture workflow would encode source art to D3D9 DXT1/5 mip-chained DDS with **NVIDIA Texture Tools**
  (`nvcompress`/`nvtt_export`) — legacy DDS, no DX10-ext header — gated through `dds.py probe`. That encoder path is
  the remaining piece for the convenient Blender edit→package loop (Prompt 3b), which now has a **proven delivery
  route** to build on.

## Reused symbols (review: no new format logic, no second overlay path)

`SchemaSet.BindRuntimeTexturePayload` / `Marshaler.Texture` (0024 pass-through); `openwrath mod build-local` +
`assemble_complete_stream.py` + the 0017 overlay machinery; `parse_manifest` + the 0024 record layout to read the
shipped format; `blender/openwrath_import/dds.py probe` for payload validity. The instant-build test aids reused the
existing `inheritFrom` + `BuildTime/BuildCost` fastbuild pattern (not part of the texture result).

## Credit

Shipped EA texture records defined the format reproduced here; the synthetic magenta payload contains no EA pixels.
The community-mod recon that mapped the two texture routes (0021) credits the mods named there.
