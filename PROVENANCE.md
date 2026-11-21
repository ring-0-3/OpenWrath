# Provenance

Where OpenWrath comes from, what in it is original, and why it carries no game content.
This expands on the attribution summary in [`NOTICE.md`](NOTICE.md).

## Lineage

OpenWrath derives from **BinaryAssetBuilder** ("BAB") by Qibbi (Jana Mohn), released under the **MIT License**
(© 2020 Jana Mohn). BAB is a .NET implementation of the SAGE / Kane's Wrath asset *compiler*
(authoring XML → compiled binary asset streams), together with the `SageBinaryData` type definitions and the
`Relo` serialization engine. OpenWrath retains the upstream MIT `LICENSE` verbatim; it continues to apply to
all upstream code, and OpenWrath's own additions are released under the same license.

## What is original to OpenWrath

- **A Linux-native port of the compiler** — it builds and runs under `dotnet` on Linux with no Wine or Windows
  VM. The changes are confined to platform specifics (P/Invoke, pointer width, path casing, XInclude, expression
  handling, RefPack) while preserving byte-for-byte output.
- **A native decompiler** (`source/BinaryAssetBuilder.Decompiler` + the `bab-decompile` CLI) — compiled binary
  assets back to authoring XML, written from scratch as the structural inverse of the compiler.
- **The developer modkit** (`modkit/`), the **findings catalogue** (`docs/findings/`), and the project
  documentation.

## No game content — tree or history

This repository contains **no** Command & Conquer / Kane's Wrath game assets, data, streams, compiled binaries,
game schemas, or SDK files — neither in the working tree nor anywhere in the git history. OpenWrath is
**interoperability** software for a data file format: using it to build or read a mod requires that you supply
your **own legally-owned** game data and SDK (bring-your-own-data; see [`SETUP.md`](SETUP.md)).

Where the toolchain needs to understand the format, it does so the way any file-format library does — the
`SageBinaryData` type definitions describe the on-disk **layout** so the tool can read and write it. The only
Electronic Arts text in the source tree is the format's own XML namespace (`uri:ea.com:eala:asset`), which is
necessary to read and write the format and is used nominatively.

> The optional audio compiler links a native codec library (`audio.dll`, EALayer3) that OpenWrath does **not**
> ship: it is git-ignored and bring-your-own, obtained from your own licensed installation. The audio compiler
> is inert without it.

## Repository & attribution

OpenWrath is maintained as its own repository with its own history. Upstream authorship and the MIT license are
credited in [`LICENSE`](LICENSE) and [`NOTICE.md`](NOTICE.md), satisfying the license's attribution terms.

## Verification

Correctness is shown mechanically rather than asserted: `tools/roundtrip.sh` decompiles a compiled asset,
recompiles it, and checks the bytes are identical — and, when you supply your own game data, compares against
the bytes the game itself produces. The per-type coverage is reported in
[`docs/reference/COVERAGE.md`](docs/reference/COVERAGE.md).
