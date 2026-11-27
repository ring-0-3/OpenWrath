# Tutorial — edit a unit's texture in Blender and see it in-game

**Goal:** take a shipped Kane's Wrath unit, open its model *with textures* in Blender, repaint the skin, and get it
rendering on your own retail 1.3 game — then switch it back off.

**What tier is this?** Editing pixels is the **§4 frontier** — *stated-tier*, never byte-exact. There is no byte
oracle for new pixels (EA's DXT compressor isn't bit-reproducible), so the acceptance test is simply **"the game
loads it and renders it."** Everything up to that point (reading the shipped format, matching it, packaging the
overlay) *is* checked. See `docs/design/verification-blind-spots.md` §4 and findings
[0030](../findings/0030-record-overlay-texture-override-works-on-1.3.md) /
[0031](../findings/0031-convenient-texture-edit-to-in-game-loop.md).

> **Two honesty flags, up front.** The mod you build is **LOCAL-ONLY** (it carries EA-derived stream metadata — fine
> on your own machine, not shareable), and a texture overlay **changes the stream's identity, so it is NOT
> C&C-Online / replay-safe** — treat it as a single-player / local / consenting-lobby mod, never a ranked edit.

---

## 0. One-time setup

You need three things on your machine. OpenWrath bundles none of them — it *detects* them, so the toolchain stays
general:

1. **The OpenWrath toolchain built** and `openwrath detect` run once (so `~/.config/openwrath/config.toml` knows
   your install, SDK, schema, etc.). Check with `openwrath show`.
2. **Blender 4.1+** with the add-on installed: `openwrath blender install`, then enable *OpenWrath* in Blender's
   *Edit ▸ Preferences ▸ Add-ons*.
3. **A DDS encoder on your `PATH`** — this is the only new requirement for *editing* (viewing needs none). OpenWrath
   looks for `nvcompress` → `nvtt_export` → `texconv`, in that order, and recommends **NVIDIA Texture Tools**
   (`nvcompress`) because it emits the legacy D3D9 DDS the engine requires.
   - NixOS: add `nvidia-texture-tools` to your packages. Debian/Ubuntu: `apt install nvidia-texture-tools`.
     macOS: `brew install nvidia-texture-tools`.
   - Verify: `command -v nvcompress` prints a path. (No encoder? You can still do a *synthetic* solid-color test —
     see the `--solid` note at the end — but you can't paint real pixels.)

---

## 1. Decode the model for Blender

Pick the unit's model container and decode it (this reads *your* installed game; it ships nothing):

```sh
openwrath blender model NUREDEEMER_SKN
```

This writes the mesh + hierarchy + **its textures** into OpenWrath's local scratch dir and prints the `.xml` to
import. (`NUREDEEMER_SKN` is the Nod Redeemer; use `openwrath find <name> --type W3DContainer` to find others.)

## 2. Import into Blender

In Blender: **File ▸ Import ▸ OpenWrath Model (.xml)** and choose the printed
`W3DContainer.NUREDEEMER_SKN.xml`. The model comes in **textured** — each mesh part gets a material named `OW_<texture>`
whose Image Texture node is **labelled with the texture's record name**. That label is the key the exporter uses
later, so don't rename it.

> **A unit's skin is usually several textures, not one.** EA splits a model's skin across records by body section.
> The Redeemer, for example, uses `NURedeemer` (upper body), `NURedeemer2` (legs), and `NURedeemer3` (small details).
> So the atlas you first see is only *part* of the unit — section 4 covers editing the whole thing.

## 3. Paint

The quickest way:

1. In the 3D viewport, change the mode dropdown from **Edit/Object Mode** to **Texture Paint**.
2. Press **N** for the sidebar → under **Tool**, pick a bold brush **Color** and a comfortable **Radius**.
3. Paint directly on the model, or paint the flat atlas in the left **Image Editor** (switch its mode to **Paint**).
   You can pick which texture you're editing from the image dropdown at the top of the Image Editor — the images are
   named after the records (`NURedeemer`, `NURedeemer2`, …).

**Paint boldly.** DXT compression softens fine detail, so a big obvious block of color reads far better in-game than
subtle shading — especially for your first test.

You don't need to manually *save* the image; the exporter reads the painted pixels straight off the datablock.

> **If Texture Paint says "Missing texture" / won't paint:** Blender needs its paint slot pointed at the image. Open
> a **Shader Editor**, click the Image Texture node for that material (so it's the active node), and paint again — or
> in Texture Paint mode's sidebar set **Mode: Image** and choose the image. One click, then it paints.

## 4. Export — one part, or the whole unit

**File ▸ Export ▸ OpenWrath Texture Edit (→ in-game).** In the dialog:

| Field | Set it to |
|-------|-----------|
| **Mod project dir** | the folder to author into, e.g. `~/mods/RedeemerSkin` (created if new). Put it in the **same** project every time you want the edits to live in one overlay. |
| **Source stream** | leave `static_common` |
| **Active object only** | **ON** → export just the selected part's texture. **OFF** → export *every* OpenWrath texture in the scene (the whole unit, all sections). |
| **Solid control (RRGGBB)** | leave blank for a real paint |

- To change **just the top**, select `REDEEMER_TOP`, leave *Active object only* **on**.
- To change the **whole unit**, paint every section (orbit the model and paint the legs, feet, etc.), then turn
  *Active object only* **off** so all three skin records are overridden in one shot.

Under the hood this is a thin shell-out: Blender saves your edited image(s) and calls `openwrath texture override`,
which reads each shipped record's exact format, encodes a **format-matched** DDS with your encoder, verifies it
matches (FourCC + dimensions + mip count), and writes a `<Texture><Payload>` override into the project. The DDS/record
/overlay logic all lives in the CLI — the add-on only exports the image.

## 5. Build + activate + play

```sh
openwrath mod build-local ~/mods/RedeemerSkin --install --no-check
openwrath mod activate RedeemerSkin
```

- `build-local --install` assembles the complete LOCAL-ONLY `static_mod` overlay and copies it into your `Mods/`.
  (`--no-check` skips the pre-flight linter; see the troubleshooting note on it below.)
- `activate` backs up your master SkuDef and switches this overlay on (with the online-safety + mutual-exclusivity
  warnings).

Launch Kane's Wrath on a **standard** skirmish map (not an R23/tournament map — those crash on their own, finding
0017), build the unit, and look at it. When you're done:

```sh
openwrath mod deactivate RedeemerSkin
```

If you want to tweak and go again: repaint → export → `build-local --install` → relaunch. Since the overlay is
already active, you don't re-activate — just rebuild and launch.

---

## Troubleshooting & gotchas

- **Only one overlay at a time.** All `static_mod` overlays claim the same slot, so **activating one turns the others
  off** (finding 0017). If you also run a gameplay mod (money, instant-build), fold the texture edits into *that same
  project* instead of making a second overlay — otherwise they fight and one silently wins.
- **"encoded DDS does NOT match the shipped record (dimensions …)".** Your painted image isn't the record's native
  size. Editing the *imported* texture keeps the right size automatically; if you painted at a different resolution,
  install Pillow (`python3Packages.pillow` / `pip install pillow`) so the CLI can resize, or paint at the native size.
- **"no DDS encoder found".** Install `nvcompress` (section 0) and open a fresh terminal so it's on `PATH`.
- **A section didn't change in-game.** The exporter overrides the **diffuse** of each section. A few models layer a
  `_D`/normal/spec companion map that can mute a recolor; if a part stays stock, that section needs its companion map
  overridden too — ask and it can be extended.
- **`--no-check` — why?** `mod check` is currently over-strict: it flags harmless `unnamed module` diagnostics and
  some in-base references as fatal even though the asset compiles and runs. Until that's relaxed (see `ROADMAP.md`),
  `--no-check` is the pragmatic choice for overlays that are known-good. It skips validation, not correctness —
  `build-local` still integrity-checks the packed big.
- **Nothing committed to git.** A scaffolded project gitignores `dist-local/`, `*.dds`, and the base64 override XML —
  your edited pixels are *your* local data, never checked in.

## What's byte-checked vs. trusted

| Step | Checked how |
|------|-------------|
| Reading the shipped record's format | decoded from your own game (findings 0023/0024) |
| Your encoded DDS matches that format | `dds.probe` + FourCC/dims/mips assertion (refuses a mismatch) |
| The payload survives into the compiled record | base64 round-trip + verbatim in the compiled `.asset` |
| The overlay is complete + loadable | `build-local` completeness + big-integrity check (findings 0016/0017) |
| **The new pixels look right** | **in-game only — stated-tier, your eyes are the oracle** |

See `docs/findings/0031-convenient-texture-edit-to-in-game-loop.md` for the full mechanism and the reused machinery.
