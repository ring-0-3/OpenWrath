# Roadmap

Where OpenWrath is and where it's going. Status is honest: a thing is only "done" if it's **verified**
(for round-trips, that means byte-exact via `tools/roundtrip.sh`). Help is welcome on anything below —
especially the 🔧 and 📋 items.

Legend: ✅ done & verified · 🔧 in progress · 📋 planned

## Compiler (XML → binary)
- ✅ Native-Linux port of BinaryAssetBuilder (runs under `dotnet`, no Wine), byte-faithful to EA's output.
- ✅ Correct x64→32-bit on-disk pointer layout; case-insensitive paths; native XInclude / expressions / RefPack.
- ✅ Cross-stream reference typing via reference manifests (`-rm`).
- 📋 Flesh out any remaining under-exercised asset/module structs surfaced by the corpus sweep below.

## Decompiler (binary → XML)
- ✅ Generic read-walk over the shared struct layout — one engine reads every type, no per-type decompile code.
- ✅ Full value vocabulary (scalars, units, enums, bit-flags, strings, colors/coords/ranges, data blobs).
- ✅ Reference / import resolution to authored **names** (the lossless win over schema-walking decompilers).
- ✅ Polymorphic module dispatch → **GameObjects byte-exact**, incl. construction yards.
- ✅ Module-id / StringHash recovery via the compiler's `StringHashes.xml`.
- 🔧 **Foreign-mod robustness & multi-schema** — decompile *any* third-party compiled stream without crashing:
  TypeHash-based schema-version detection, and graceful degradation (emit a labeled raw/unknown block and keep
  going instead of aborting the file). This retires the last reliance on Windows decompiling tools.
- 📋 Master `StringHashes.xml` from a corpus compile, to recover inherited/base-object string values.

## Verification & reliability
- ✅ `tools/roundtrip.sh` — decompile → recompile → assert byte-identical, per asset, manifest-driven.
- ✅ Verified byte-exact: ArmorTemplate 207/207, LocomotorTemplate 79/79, AttributeModifier 78/78,
  WeaponTemplate 456/456, GameObjects incl. `GDIConstructionYard`.
- 🔧 **Whole-corpus coverage** — round-trip the entire SDK asset tree, bucket by type, publish a per-type
  pass/fail matrix with each lossy edge documented (no silent gaps).
- 📋 **CI** — run the round-trip harness on every change so regressions in any type are caught immediately.

## Content pipeline
- ✅ Mod pipeline utilities in `pytools/` (BIG4 archive, RefPack, stream/manifest inspect + splice).
- 📋 **Art / asset compilers** for new-content mods — the big build: textures (DDS), meshes/animation (W3D),
  and audio. This is what unlocks making *new* assets, not just editing existing ones.

## Packaging & docs
- 📋 **Nix flake** + reproducible, cross-distro builds (bring-your-own game data; ship no EA content).
- 📋 **Docs & tutorials** — not a dumbed-down tool, but a teaching layer: "your first mod in 15 minutes," plus
  explained write-ups of the engine internals we've reverse-engineered, so the format is *understood*, not hoarded.

## Non-goals
- Shipping EA game content or SDK assets. OpenWrath is interop tooling; you bring your own legally-owned data.
- A GUI-first workflow at the expense of exposed power. Great docs over a hidden "simple mode."
