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
- 🔧 **Raise data-type coverage** — complete the partial gameplay structs, now measured against the game's
  *shipped* bytes rather than guessed. The **GameObject** tail has had two structural bugs fixed this way — an
  `ActiveBody` field-order error and the out-of-schema enum case (see below) — leaving a smaller residual tail
  (a few epic units + `MedicalBay`/`CommandPost` variants, `AlienMillipedeBody`, `AlienCorrupter`,
  `GDIDigInBuilding`). Plus ExperienceLevelTemplate, LogicCommand, AIStrategicStateDefinition, and currently
  unmodeled (`unknown-type`) gameplay types. Method: first-diff offset → module → XSD → add/fix field → re-verify
  against shipped bytes. (Art/W3D/texture/particle types are **out of scope here** → art pipeline.)
- 🔧 Master `StringHashes.xml` from a corpus compile, to recover inherited/base-object string values losslessly.

## Verification & reliability
- ✅ `tools/roundtrip.sh` — decompile → recompile → assert byte-identical, per asset, manifest-driven.
- ✅ Verified byte-exact (round-trip): ArmorTemplate 207/207, WeaponTemplate 456/456, LocomotorTemplate 79/79,
  AttributeModifier 78/78, UpgradeTemplate 186/186, SpecialPowerTemplate 258/258, ObjectCreationList 267/267,
  GameObjects incl. `GDIConstructionYard`.
- ✅ **Ground-truth verification — our output vs the game's *shipped* bytes** (`tools/roundtrip.sh --from-binary`).
  Round-trip proves the toolchain is internally *lossless*; this proves the output is *what the game actually
  loads*. The gate decompiles a shipped (or mod) linked stream, recompiles it, and byte-compares every asset to
  the original bytes, bucketed per type (byte-exact / same-size value-diff / size-mismatch, with first-diff
  offsets). It has already surfaced and confirmed real toolchain bugs that round-trip alone could not (a
  field-order error; out-of-schema enum values). Verified on `static_common`. 🔧 **Next:** extend across more
  shipped streams, and *harvest* from it the set of values the shipped data uses that the authoring schema omits.
- 🔧 **Tolerant-but-honest validation.** In places the authoring schema is a strict *subset* of what the game's
  own shipped data uses (e.g. enum fields holding integer values the schema never names). Rather than refuse to
  reproduce data the game itself ships and runs, the compiler accepts an out-of-schema integer value — but says
  so, at the right volume: **informational** when the value is attested in shipped data, a loud **warning** when
  it is novel and unverified. Tolerance + a single warning have landed; the info-vs-warning split awaits the
  harvested attested-value set — **harvested from shipped data, never hardcoded**, so every "attested" claim is
  backed by evidence.
- 🔧 **Whole-corpus coverage** — `tools/corpus-roundtrip.sh` + `docs/reference/COVERAGE.md` publish a *measured*
  per-type matrix (currently **99.3% byte-exact across the 5 core gameplay types**; see the file for honest scope).
  **Next:** compile source with include-context so the broader type space (FX, Upgrade, CommandSet, LogicCommand,
  SpecialPower, …) is actually measured — turning "5 types" into a gameplay-wide number.
- ✅ **CI** — builds the compiler + decompiler on every push/PR (`.github/workflows/`); the data-dependent
  round-trip gate runs locally / self-hosted (EA data can't live in CI).

## Platform & extensibility
OpenWrath is meant to be *built on* — both as a foundation other modding frameworks sit atop, and as a host for
third-party **modules** that add capability. That makes its boundary a kind of public API, which shapes the work
below. Each item rests on the same idea as the verification gate: correctness anyone can *check*, not merely trust.
- 📋 **Structured diagnostics** — stable, machine-readable codes (not just prose), so tools built on OpenWrath can
  react programmatically and tell *their* bug from ours.
- 📋 **Machine-readable reliability map** — publish the per-type ground-truth bucket matrix as data, so a framework
  can ask *what is proven reliable* before depending on it.
- 📋 **Opt-in strict mode** — escalate the "novel / unverified value" warning to a hard error, giving downstream
  frameworks and CI a provable guarantee: everything emitted is schema-named or shipped-attested.
- 📋 **Documented module / extension API** — clean, stable seams for third-party handlers, formats, and renderers,
  with the round-trip + ground-truth gate as the module's *acceptance test*, so a module's correctness is
  decidable by anyone rather than taken on trust.

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
