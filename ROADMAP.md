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
- ✅ **Foreign-mod robustness** — decompiles *any* third-party compiled stream end-to-end without crashing
  (verified on Second Isomer's full **43,994-asset** stream, zero crashes): bounds-checked reads, graceful
  degradation (labeled `<RawAsset>`/`<UnknownModule>` blocks), TypeHash schema-version detection (single schema
  confirmed across the test mod). This retires the last reliance on Windows decompiling tools.
- 🔧 **Raise data-type coverage** — complete the partial gameplay structs surfaced by the corpus/stream runs:
  the **GameObject** tail (a few fail at a fixed offset), plus ExperienceLevelTemplate, LogicCommand,
  AIStrategicStateDefinition, and currently-unmodeled (`unknown-type`) gameplay types. Method: first-diff offset
  → module → XSD → add field → re-verify. (Art/W3D/texture/particle types are **out of scope here** → art pipeline.)
- 🔧 Master `StringHashes.xml` from a corpus compile, to recover inherited/base-object string values losslessly.

## Verification & reliability
- ✅ `tools/roundtrip.sh` — decompile → recompile → assert byte-identical, per asset, manifest-driven.
- ✅ Verified byte-exact (round-trip): ArmorTemplate 207/207, WeaponTemplate 456/456, LocomotorTemplate 79/79,
  AttributeModifier 78/78, UpgradeTemplate 186/186, SpecialPowerTemplate 258/258, ObjectCreationList 267/267,
  GameObjects incl. `GDIConstructionYard`.
- 🔧 **Ground-truth validation — compiler output vs EA's *shipped* bytes (the "does it actually run" check).**
  Round-trip proves the toolchain is internally *lossless*; this proves the output is *what the game actually
  loads* — i.e. it compiles to valid, non-crashing assets. Method: diff our compiled output against the real
  bytes in the game's shipped streams (not just decompile→recompile). Done for the foundational types + the core
  engine, and confirmed end-to-end by mods that run in-game — but **extend the diff across all covered types** so
  every "byte-exact round-trip" is backed by "byte-matches-what-ships." This is the measure that most directly
  means *it runs in the game*, which is the thing that ultimately matters.
- 🔧 **Whole-corpus coverage** — `tools/corpus-roundtrip.sh` + `docs/reference/COVERAGE.md` publish a *measured*
  per-type matrix (currently **99.3% byte-exact across the 5 core gameplay types**; see the file for honest scope).
  **Next:** compile source with include-context so the broader type space (FX, Upgrade, CommandSet, LogicCommand,
  SpecialPower, …) is actually measured — turning "5 types" into a gameplay-wide number.
- ✅ **CI** — builds the compiler + decompiler on every push/PR (`.github/workflows/`); the data-dependent
  round-trip gate runs locally / self-hosted (EA data can't live in CI).

## Content pipeline
- ✅ Mod pipeline utilities in `pytools/` (BIG4 archive, RefPack, stream/manifest inspect + splice).
- 📋 **Art / asset compilers** for new-content mods — the big build: textures (DDS), meshes/animation (W3D),
  and audio. This is what unlocks making *new* assets, not just editing existing ones.

## Packaging & docs
- 📋 **Nix flake** + reproducible, cross-distro builds (bring-your-own game data; ship no EA content).
- 🔧 **Docs & tutorials** — the "Understanding OpenWrath" concept guide has started (`docs/`: the big picture +
  asset streams); more chapters, "your first mod in 15 minutes," and explained write-ups of the **asset format**
  we've reverse-engineered. Not a dumbed-down tool, but a teaching layer so the format is *understood*, not hoarded.

## Non-goals
- Shipping EA game content or SDK assets. OpenWrath is interop tooling; you bring your own legally-owned data.
- A GUI-first workflow at the expense of exposed power. Great docs over a hidden "simple mode."
