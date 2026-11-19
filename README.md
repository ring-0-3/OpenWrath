# OpenWrath

A **native-Linux, open modding toolchain for Command & Conquer: Kane's Wrath** (the SAGE engine) — a
byte-faithful asset **compiler** and a lossless **decompiler**, plus the stream/archive utilities needed to
build a mod end to end. No Wine, no Windows VM.

The point is to turn SAGE/KW modding from gatekept, Windows-only, tribal knowledge into something open,
native, reproducible, and **learnable** — tools that come with their own proof that they work, and docs that
explain the engine instead of hiding it.

## What's here

| Piece | What it does |
|-------|--------------|
| **`BinaryAssetBuilder`** (compiler) | authoring XML → compiled SAGE asset streams, byte-faithful to EA's output. A Linux port of [Qibbi/BinaryAssetBuilder](https://github.com/Qibbi/BinaryAssetBuilder). |
| **`bab-decompile`** (decompiler) | compiled asset streams → authoring XML. The structural *inverse* of the compiler, so its output recompiles **byte-identically**. |
| **`pytools/`** | BIG4 archive pack/extract, RefPack (de)compression, and stream/manifest inspect + splice utilities — the rest of the mod pipeline. |
| **`tools/`** | `roundtrip.sh` (the correctness gate), `dev-env.sh` (one-command dev setup), `kw-compile.sh`. |

## Reliability is measured, not claimed

Correctness here is a *decidable property*, not a promise: `tools/roundtrip.sh` decompiles an asset, recompiles
the result, and asserts the instance/relocation/import bytes are **identical**. If they differ, it's a failure.
Verified byte-exact so far:

- **ArmorTemplate** 207/207 · **LocomotorTemplate** 79/79 · **AttributeModifier** 78/78 · **WeaponTemplate** 456/456
- **GameObjects** — including a full construction yard (`GDIConstructionYard`), the asset class other tools choke on.

In progress: whole-corpus coverage reporting, and robust decompilation of arbitrary third-party mods.
See **[ROADMAP.md](ROADMAP.md)** for what's done and what's planned (incl. the art/asset compilers, Nix
packaging, and docs/tutorials).

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
port and the decompiler are ours. It contains **no EA game assets or SDK schemas**; those are reverse-engineered
interop targets you bring yourself.

This toolchain was built with **AI assistance**, stated plainly — and backed by the byte-exact test suite above
so correctness is verified mechanically rather than taken on trust. Audits, scrutiny, and contributions are
welcome. Full details in **[NOTICE.md](NOTICE.md)**.
