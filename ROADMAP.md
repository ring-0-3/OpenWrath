# Roadmap

Where OpenWrath is and where it's going. Status is honest: a thing is only "done" if it's **verified**. For
fidelity, that means measured by `tools/roundtrip.sh` — and the strong claim is the **ground-truth** mode
(`--from-binary`), which compares our output to the bytes the game actually ships, not just to our own compiler's
output. Help is welcome on anything below — especially the 🔧 and 📋 items.

Legend: ✅ done & verified · 🔧 in progress · 📋 planned

## Compiler (XML → binary)
- ✅ Native-Linux port of BinaryAssetBuilder (runs under `dotnet`, no Wine), byte-faithful to EA's output.
- ✅ Correct x64→32-bit on-disk pointer layout; case-insensitive paths; native XInclude / expressions / RefPack.
- ✅ Cross-stream reference typing via reference manifests (`-rm`).
- ✅ **37 asset types registered** (`Plugin.cs` `Initialize()`): the five core gameplay types plus the gameplay
  breadth batch (Upgrade, SpecialPower, OCL, FXList, DamageFX, ExperienceLevel, LogicCommand(Set), Stance,
  RadiusCursor, Weather, Mouse, OnlineChatColors, ConnectionLineManager, PhaseEffect, Road, MultiplayerColor)
  and the audio/LOD/environment batch (AmbientStream, MusicTrack, DialogEvent, LargeGroupAudioMap,
  Static/Dynamic GameLOD, GameLODPreset, CrowdResponse, VideoEventList, Environment, AudioEvent, Multisound,
  MiscAudio, AudioSettings, AudioLOD).
- ✅ Compile-fail bug-class fixes surfaced by the ground-truth gate (field-order error; out-of-schema enum
  values) — see Verification.
- 🔧 Close the remaining per-type gaps the matrix lists (MultiplayerColor recompile; GameObject value-diff).

## Decompiler (binary → XML)
- ✅ Generic read-walk over the shared struct layout — one engine reads every type, no per-type decompile code.
- ✅ Full value vocabulary (scalars, units, enums, bit-flags, strings, colors/coords/ranges, data blobs).
- ✅ Reference / import resolution to authored **names** (the lossless win over schema-walking decompilers).
- ✅ Polymorphic module dispatch for GameObjects (incl. construction yards) — closed-loop byte-exact.
- ✅ Module-id / StringHash recovery via a master `StringHashes.xml` built from an SDK compile, so inherited /
  base-object string values decompile to names rather than hex.
- ✅ **Foreign-mod robustness** — decompiles *any* third-party compiled stream end-to-end without crashing
  (exercised on a full large mod stream of tens of thousands of assets, zero crashes): bounds-checked reads,
  graceful degradation (labeled `<RawAsset>` / `<UnknownModule>` blocks), and TypeHash schema-version detection.
  This removes the last reliance on Windows-only decompiling tools.
- 🔧 **Raise data-type coverage**, measured against the game's *shipped* bytes. Method: first-diff offset →
  module → schema → add/fix field → re-verify against shipped bytes. The GameObject tail has had structural bugs
  fixed this way (an `ActiveBody` field-order error; an out-of-schema enum case), bringing GameObjects to
  **same-size, value-diff** vs shipped (see below). Art / W3D / texture / particle types are **out of scope
  here** → content pipeline.

## Verification & reliability
- ✅ `tools/roundtrip.sh` — the correctness gate, two modes:
  - **closed-loop** (`<source.xml>`): compile → decompile → recompile → assert byte-identical. Proves the
    decompiler is a faithful inverse of the compiler. Verified byte-exact e.g. ArmorTemplate 207/207,
    WeaponTemplate 456/456, LocomotorTemplate, AttributeModifier, and GameObjects incl. `GDIConstructionYard`.
  - **ground-truth** (`--from-binary <stream.manifest>`): decompile a *shipped* linked stream, recompile, and
    byte-compare every asset to the **original shipped bytes**, bucketed per type (byte-exact / same-size
    value-diff / size-mismatch / recompile-missing, with first-diff offsets). This proves the output is *what
    the game actually loads*, and it has surfaced real bugs closed-loop alone could not.
- ✅ **Ground-truth results (2026-11-20):** of the 37 registered types, **33 reproduce EA's shipped bytes
  byte-exact on sampled instances**; GameObject and Environment are structurally exact with a residual
  value-diff; MultiplayerColor has a recompile gap; Road has no instances in the sampled streams. Full matrix,
  sampled instances, and method in **[docs/reference/COVERAGE.md](docs/reference/COVERAGE.md)**.
- ✅ **Master `StringHashes.xml`** harvested from an SDK compile, so module-id / inherited string values resolve
  during decompilation.
- 🔧 **Finish GameObject byte-exactness vs shipped bytes** — the residual value-diff is localized to the
  module / weapon-set region (incl. the MARV turret block). This is the next fidelity milestone.
- 🔧 **Tolerant-but-honest validation.** Where the authoring schema is a strict *subset* of what shipped data
  uses (e.g. enum fields holding integer values the schema never names), the compiler reproduces the shipped
  value rather than refusing it — **informational** when attested in shipped data, a loud **warning** when novel.
  Tolerance + a single warning have landed; the info-vs-warning split awaits a harvested attested-value set
  (**harvested from shipped data, never hardcoded**).
- ✅ **CI** — builds the compiler + decompiler on every push/PR (`.github/workflows/`); the data-dependent
  round-trip gate runs locally / self-hosted (game data can't live in CI).

## Developer modkit
- 🔧 **`modkit/openwrath`** — a developer-facing, **config-driven** CLI that turns the hand-run pipeline into a
  few commands. Ships **zero game data**; discovers your own install/SDK and keeps all paths in a per-user config
  outside any repo. Implemented today:
  - ✅ `detect` / `show` / `init` — auto-discover the install / prefix / mods / SDK, confirm bring-your-own
    paths, and write/report the config (Flatpak, native, and WSL / Windows-side).
  - ✅ `gen-stringhashes` / `extract-manifests` — produce the bring-your-own inputs from your own SDK and install.
  - ✅ `mod bake` — compile a mod's XML overrides and splice them into a target stream, repack the big,
    auto-backup, install. (A *mod* is bring-your-own; the modkit is the capability, it bundles no mod or EA data.)
  - ✅ `mod revert` — restore a target's big from the last backup.
  - ✅ `schema` — per-type TypeHash drift detection + a bake-time guard (`--adopt-schema`).
  - ✅ `trace` / `uses` — walk the reference graph (outgoing / incoming) to find what to mod and what depends on it.
  - ✅ `mod new` / `mod add <asset>` — scaffold a project and pull an asset in as an editable override
    (from the SDK source), closing the loop: `trace` → `add` → edit → `bake`.
  - 📋 `mod package` — produce a self-contained, shareable mod (its own big + SkuDef) a player drops into `Mods/`
    and runs with no OpenWrath installed.
  - 📋 `mod check` — pre-flight validation (dangling references, unknown fields, schema drift) with file/line
    messages, run automatically before a bake.
  - 📋 base-game-target guard — default to mod targets; require an explicit flag + warning to splice base-game
    streams (avoids C&C:Online / replay desync).
  - 📋 installable command — a `pipx`-installable `openwrath` that locates or fetches the compiler binary, so
    setup is "install + init" rather than "clone + build".
  See **[modkit/README.md](modkit/README.md)**. This is the start of the "reliability as a platform" phase:
  make the verified toolchain usable, not just correct.

## Platform & extensibility
OpenWrath is meant to be *built on*. Each item rests on the same idea as the verification gate: correctness
anyone can *check*, not merely trust.
- 📋 **Structured diagnostics** — stable, machine-readable codes, so tools built on OpenWrath can tell *their*
  bug from ours.
- 📋 **Machine-readable reliability map** — publish the per-type ground-truth bucket matrix as data, so a
  framework can ask *what is proven reliable* before depending on it.
- 📋 **Opt-in strict mode** — escalate the "novel / unverified value" warning to a hard error, giving downstream
  CI a provable guarantee: everything emitted is schema-named or shipped-attested.
- 📋 **Documented extension API** — clean, stable seams for third-party handlers and formats, with the
  round-trip + ground-truth gate as the acceptance test.
- 📋 **Multi-schema interoperability** — read/author data for mods built against a *different schema version* than
  retail (same types, drifted layout). A TypeHash-keyed layout registry + data-driven variant tables + a
  derive-and-verify workflow, so OpenWrath has a default schema and an additive, community-contributed set of
  supported variants — shipping authored descriptions, zero mod/EA content. Groundwork landed: `openwrath schema`
  (drift visibility), a bake-time drift guard, and `--adopt-schema` for hash-only drift. Full design:
  **[docs/design/multi-schema-interop.md](docs/design/multi-schema-interop.md)**. Motivating findings:
  [0009](docs/findings/0009-decompiler-logiccommand-instance-read-desync.md) /
  [0010](docs/findings/0010-insert-must-match-target-stream-type-schema-hash.md).

## Content pipeline
- ✅ Mod pipeline utilities in `pytools/` (BIG4 archive, RefPack, stream/manifest inspect + splice).
- 📋 **Art / asset compilers** for new-content mods — the big build: textures (DDS), meshes/animation (W3D), and
  audio files. This is what unlocks making *new* assets, not just editing existing ones. It is a separate effort
  from the data toolchain above.

## Packaging & docs
- 📋 **Nix flake** + reproducible, cross-distro builds (bring-your-own game data; ship no game content).
- 🔧 **Docs & tutorials** — the "Understanding OpenWrath" concept guide (`docs/`) now runs big picture → asset
  streams → authoring XML → references/import graph; next are the decompiler chapter and "your first mod." A
  teaching layer so the format is *understood*, not hoarded.
- 🔧 **Onboarding for contributors** (`onboarding/`) — a doing-first path (understand → use → practice). Planned:
  a sequence of small **practice exercises** (build a pluggable addition against the real tests, with a worked
  solution to check against), and a **practice harness** that reproduces the codebase with one chosen part
  removed, so you can reimplement a real piece (a command, a renderer, a container parser) against the existing
  tests in isolation — one of the fastest ways to truly own a subsystem.

## How we calibrate against prior tooling
The closest reference point, WrathEd, recognizes a wider set of top-level types (~66) but is Windows-only, is
**lossy** (schema-walk decompilation that does not reproduce exact bytes), and crashes on some inputs
(GameObject among them). OpenWrath is deliberately **narrower but deeper**: fewer types, but each one measured
**byte-exact or honestly bucketed against shipped data**, lossless where it claims to be, native-Linux, and
crash-free on arbitrary input. We are **not** at type-count parity and do not claim to be — the goal is a
measured, trustworthy core that widens over time, not a bigger unverified surface.

## Non-goals
- Shipping game content or SDK assets. OpenWrath is interop tooling; you bring your own legally-owned data.
- A GUI-first workflow at the expense of exposed power. Great docs over a hidden "simple mode."
