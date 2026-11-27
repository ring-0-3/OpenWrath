# OpenWrath

A **native-Linux, open modding toolchain for Command & Conquer 3: Kane's Wrath** (the SAGE engine) — a
byte-faithful asset **compiler** and a lossless **decompiler**, plus the stream/archive utilities needed to
build a mod end to end. No Wine, no Windows VM.

The point is to make working with Kane's Wrath's data open, native, reproducible, and **learnable** —
tools that come with their own proof that they work, and docs that explain the format.

## What's here

| Piece | What it does |
|-------|--------------|
| **`BinaryAssetBuilder`** (compiler) | authoring XML → compiled SAGE asset streams, byte-faithful to EA's output. A Linux port of [Qibbi/BinaryAssetBuilder](https://github.com/Qibbi/BinaryAssetBuilder). |
| **`bab-decompile`** (decompiler) | compiled asset streams → authoring XML. The structural *inverse* of the compiler, so its output recompiles **byte-identically**. |
| **`pytools/`** | BIG4 archive pack/extract, RefPack (de)compression, and stream/manifest inspect + splice utilities — the rest of the mod pipeline. |
| **`modkit/`** | `openwrath` — a config-driven developer CLI that drives the whole pipeline: set up (`detect`/`init`), explore (`trace`/`uses`), author (`mod new`/`add`, `mod check`), build & install (`mod bake`, `mod build-local`, `mod package`), toggle (`mod activate`/`deactivate`), and **edit unit textures** (`texture override`/`encode` → record overlay → in-game). Ships no game data. |
| **`blender/`** | A Blender add-on — a *thin front-end to the CLI* (no forked format logic). Import a shipped W3D model, see its real textures, edit it, and **export it back byte-exact** (unmodified) or stated-tier (edited). `openwrath blender install` / `model` / `view`. |
| **`tools/`** | `roundtrip.sh` / `corpus-roundtrip.sh` (the correctness gate), `mesh-repack-gate.sh` + `blender-roundtrip-gate.sh` (the Blender byte-exact gates), `verify-inputs.py` (bring-your-own input-integrity preflight — refuses the gate on drifted inputs), `dev-env.sh` (one-command dev setup), `kw-compile.sh`. |

## Reliability is measured, not claimed

Correctness here is a *decidable property*, not a promise. `tools/roundtrip.sh` has two modes, and the project
is careful not to conflate them:

- **Closed-loop (lossless):** decompile an asset, recompile it, and assert the bytes are **identical** to what
  our compiler produced. Proves the decompiler is a faithful inverse of the compiler. Verified e.g.
  **ArmorTemplate** 207/207 · **WeaponTemplate** 456/456 · **LocomotorTemplate** · **AttributeModifier** · and
  **GameObjects** including a full construction yard (`GDIConstructionYard`), the asset class other tools choke on.
- **Ground-truth (byte-exact vs EA):** decompile a *shipped* stream, recompile, and byte-compare to the bytes the
  **game itself ships** (`tools/roundtrip.sh --from-binary`). This is the stronger claim. As of 2026-11-25, of
  the **42 registered asset types, 39 reproduce shipped bytes byte-exact** on sampled instances; **GameObject is
  40/50 (80%)**, with the residual fully characterized as `StringHashes`-table coverage — not a model defect
  (feeding the missing module-id tags makes those byte-exact too); Environment is structurally exact with one
  known-lossy reference; one type (Road) has no instances in the sampled streams to measure. The honest, per-type
  matrix — with the exact instances sampled — is in **[docs/reference/COVERAGE.md](docs/reference/COVERAGE.md)**.

Beyond the gameplay data types, the **art / content pipeline** now reproduces the whole **W3D model graph**
byte-exact vs shipped bytes — **`W3DAnimation`** (seed-7 **125/125**, every channel codec), **`W3DMesh`**
(**300/300**), and the connective tissue **`W3DContainer` / `W3DHierarchy` / `W3DCollisionBox`** (**150/150** each)
— plus **particles** (**`FXParticleSystemTemplate`**, **150/150** + all 35 null-module edge cases) and the
**texture-pillar** records: the UI atlases (**`PackedTextureImage`** / **`OnDemandTextureImage`**, whole-stream
**870/870** and **123/123**) and the texture records themselves (**`Texture`** / **`OnDemandTexture`**, whole-stream
**1575/1575** and **123/123** — the shipped DDS payload passed through verbatim). Where an asset ships in a lossy
*compiled* form (animation's time-coded / adaptive-delta channels, the mesh's packed vertex buffer, a texture's
DXT-compressed DDS), OpenWrath **passes those bytes through** in their shipped form rather than re-encoding
— byte-exact where a re-encoder never could be. (Sample-verified against shipped `static_common`, honestly bucketed
— see COVERAGE.)

**You can edit models and textures in Blender — reaching the game, with the oracle kept honest.** A Blender
add-on (a thin front-end to the CLI, no forked format logic) imports a shipped W3D model with its real textures,
and **exports it back**. The claim is tiered, never conflated: an *unmodified* model round-trips **byte-exact**
(proven by `tools/blender-roundtrip-gate.sh` — `decode ∘ Blender save/reload ∘ export ∘ packer == shipped` across
the whole W3D graph; the packer itself is validated by the re-pack gate, `tools/mesh-repack-gate.sh`), while an
*edited* model or texture is **stated-tier** ("the game loads + renders it") — new pixels/geometry have no shipped
bytes to be exact against, so they are never reported byte-exact. **Editing a unit's texture reaches retail 1.3
today and is confirmed in-game** (a Blender-painted skin rendering on the Nod Redeemer), delivered as a `Texture`
record overlay — EA's own method — via `openwrath texture override` → `mod build-local` → `mod activate`. See the
**[your-first-mod tutorial](docs/tutorials/edit-a-unit-texture-in-blender.md)**.

**Inputs are verified too, not just outputs.** A committable `inputs.sha256` baseline + a `verify-inputs`
preflight make the round-trip gate **refuse to run on a drifted bring-your-own input**, so a "verified" result
can never silently rest on a mutated schema or stream. The frontier now is **new-content authoring** (new
meshes/units — on the verified packer; new textures/audio — a stated weaker tier, since EA's compressors can't be
bit-reproduced) and **wider per-type coverage**. See **[ROADMAP.md](ROADMAP.md)** for what's done and planned
(incl. the content pipeline, Nix packaging, and docs/tutorials).

## Quick start

This repo ships **only code** — no EA game content. You supply the schemas / SDK XML / game data yourself.
See **[SETUP.md](SETUP.md)** for the full, reproducible setup; the short version:

```bash
source tools/dev-env.sh                       # point the tools at your local SDK/game data
cd source && dotnet build BinaryAssetBuilder.sln -c Debug -p:Platform=x64
tools/roundtrip.sh GlobalData/Armor.xml       # -> total=207 byte_exact=207 fail=0
```

## License, attribution, and provenance

MIT licensed. **OpenWrath is a fork of [Qibbi/BinaryAssetBuilder](https://github.com/Qibbi/BinaryAssetBuilder)
(MIT, © 2020 Jana Mohn)** — the upstream `LICENSE` is retained in full; the compiler is their work, the Linux
port and the decompiler are ours. It contains **no EA game assets or SDK schemas**; those are interoperability
targets you bring yourself.

This toolchain was built with **AI assistance**, stated plainly — and backed by the byte-exact test suite above
so correctness is verified mechanically rather than taken on trust. Audits, scrutiny, and contributions are
welcome. Full details in **[NOTICE.md](NOTICE.md)**.

**Interoperability & third-party mods.** OpenWrath studies file *formats* to build compatible tooling — the
reverse-engineering-for-interoperability that every format tool and emulator relies on. Where it learns from
community work (texture add-ons, new-unit mods, FX patches), it takes the **mechanism**, verified independently,
and reimplements it in its own code — **never** another project's content or bytes, which stay their authors'.
OpenWrath ships **no EA and no third-party mod content**; you bring your own legally-owned game data and any mods
you legally have. Mechanisms learned from community mods are credited. This is a description of the project's
posture, not legal advice — respect the game's EULA and the licenses of any mods you work with.

Command & Conquer and Kane's Wrath are trademarks of Electronic Arts Inc. OpenWrath is an independent,
fan-made interoperability project — not affiliated with, endorsed by, or sponsored by EA. Game and engine
names are used nominatively, only to describe what the tools interoperate with.
