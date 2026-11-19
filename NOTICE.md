# NOTICE — attribution & provenance

This repository is a **fork of [Qibbi/BinaryAssetBuilder](https://github.com/Qibbi/BinaryAssetBuilder)**,
licensed MIT, © 2020 Jana Mohn. The upstream `LICENSE` is retained verbatim and continues to apply to all
upstream code. Our additions below are released under the same MIT license.

## What upstream provides
`BinaryAssetBuilder` ("BAB") — a .NET reimplementation of EA's SAGE/Kane's Wrath asset **compiler**
(authoring XML → compiled binary asset streams), plus the `SageBinaryData` struct definitions and the `Relo`
serialization engine.

## What this fork adds (our original work)
- **A Linux-native port** of the compiler: it builds and runs natively under `dotnet` on Linux (no Wine, no
  Windows VM). Changes are confined to replacing Windows-isms (P/Invoke, pointer width, path casing, XInclude,
  expression evaluation, RefPack) while preserving byte-for-byte output fidelity.
- **A native decompiler** (`source/BinaryAssetBuilder.Decompiler` + the `bab-decompile` CLI): compiled binary
  SAGE/KW assets → authoring XML. It is the structural *inverse* of the compiler — it reuses the same
  `SageBinaryData` structs and `Relo` layout engine, so its output is designed to recompile **byte-identically**.
  This is verified by `tools/roundtrip.sh` (decompile → recompile → assert identical bytes).

## No EA game content is shipped by us
This toolchain contains **no** Command & Conquer / Kane's Wrath game assets. It is reverse-engineering
*interop* software for a file format. Reproducing a mod requires that you supply your own legally-owned game
data and SDK. (Any SDK XML / schema files present in the tree are inherited from upstream history, not added
by this fork; the eventual public release excludes them in favour of a bring-your-own-data setup.)

## Honesty about fidelity
The round-trip harness is the source of truth: a type "round-trips byte-exact" only if its decompiled XML
recompiles to identical instance/relocation/import bytes. Some values are stored by the engine as one-way
hashes (e.g. `StringHash`, module `id` tags) or as opaque binary blobs; where a value cannot be recovered
losslessly it is documented, not silently approximated.
