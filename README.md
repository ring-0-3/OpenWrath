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
| **`modkit/`** | `openwrath` — a config-driven developer CLI that drives the above: `detect`/`show` your setup, `mod bake` (compile overrides + splice into a stream + install), `mod revert`. Ships no game data. |
| **`tools/`** | `roundtrip.sh` / `corpus-roundtrip.sh` (the correctness gate), `verify-inputs.py` (bring-your-own input-integrity preflight — refuses the gate on drifted inputs), `dev-env.sh` (one-command dev setup), `kw-compile.sh`. |

## Reliability is measured, not claimed

Correctness here is a *decidable property*, not a promise. `tools/roundtrip.sh` has two modes, and the project
is careful not to conflate them:

- **Closed-loop (lossless):** decompile an asset, recompile it, and assert the bytes are **identical** to what
  our compiler produced. Proves the decompiler is a faithful inverse of the compiler. Verified e.g.
  **ArmorTemplate** 207/207 · **WeaponTemplate** 456/456 · **LocomotorTemplate** · **AttributeModifier** · and
  **GameObjects** including a full construction yard (`GDIConstructionYard`), the asset class other tools choke on.
- **Ground-truth (byte-exact vs EA):** decompile a *shipped* stream, recompile, and byte-compare to the bytes the
  **game itself ships** (`tools/roundtrip.sh --from-binary`). This is the stronger claim. As of 2026-11-24, of
  the **37 registered asset types, 34 reproduce shipped bytes byte-exact** on sampled instances; **GameObject is
  40/50 (80%)**, with the residual fully characterized as `StringHashes`-table coverage — not a model defect
  (feeding the missing module-id tags makes those byte-exact too); Environment is structurally exact with one
  known-lossy reference; one type (Road) has no instances in the sampled streams to measure. The honest, per-type
  matrix — with the exact instances sampled — is in **[docs/reference/COVERAGE.md](docs/reference/COVERAGE.md)**.

Beyond the gameplay data types, the **art pipeline** has its first byte-exact type: **`W3DAnimation`** round-trips
byte-exact vs shipped bytes (reproducible seed-7 sample **125/125**, every channel codec), with its lossy
time-coded / adaptive-delta channels **passed through** in their shipped compressed form rather than re-encoded.

**Inputs are verified too, not just outputs.** A committable `inputs.sha256` baseline + a `verify-inputs`
preflight make the round-trip gate **refuse to run on a drifted bring-your-own input**, so a "verified" result
can never silently rest on a mutated schema or stream. In progress: the developer modkit, wider per-type
coverage, and the next art types (`W3DMesh`, textures). See **[ROADMAP.md](ROADMAP.md)** for what's done and
planned (incl. the art/asset content pipeline, Nix packaging, and docs/tutorials).

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

Command & Conquer and Kane's Wrath are trademarks of Electronic Arts Inc. OpenWrath is an independent,
fan-made interoperability project — not affiliated with, endorsed by, or sponsored by EA. Game and engine
names are used nominatively, only to describe what the tools interoperate with.
