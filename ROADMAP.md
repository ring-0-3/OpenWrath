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
- 🔧 **RefPack manifest/stream handling.** Shipped stream parts are often RefPack-compressed. RefPack is
  identified by its **second** byte (`0xFB`); the first byte is a flags byte that *varies* (`0x10`/`0x11`/`0x90`/
  `0x91` — `0x90` ships on `static_common.bin`). The reader's first guard matched only `0x10FB`, so the `0x90`/
  `0x11` variants still misreported as "Xbox360 big-endian" (finding [0012] — overfit to one sampled variant +
  duplicated-knowledge drift). Fix: detect on `byte[1] == 0xFB` via a **single shared `IsRefPack()`** (one
  authority used by C# *and* `refpack.py`), correct the "0x10FB magic" wording, consolidate the duplicate
  `pytools/refpack.py` + `modkit/lib/refpack.py`, then **decompress transparently** (port RefPack into the .NET
  reader, or decompress in the harness) so a compressed manifest/stream just works.

## Verification & reliability
- ✅ `tools/roundtrip.sh` — the correctness gate, two modes:
  - **closed-loop** (`<source.xml>`): compile → decompile → recompile → assert byte-identical. Proves the
    decompiler is a faithful inverse of the compiler. Verified byte-exact e.g. ArmorTemplate 207/207,
    WeaponTemplate 456/456, LocomotorTemplate, AttributeModifier, and GameObjects incl. `GDIConstructionYard`.
  - **ground-truth** (`--from-binary <stream.manifest>`): decompile a *shipped* linked stream, recompile, and
    byte-compare every asset to the **original shipped bytes**, bucketed per type (byte-exact / same-size
    value-diff / size-mismatch / recompile-missing, with first-diff offsets). This proves the output is *what
    the game actually loads*, and it has surfaced real bugs closed-loop alone could not.
- ✅ **Ground-truth results (2026-11-24):** of the 37 registered types, **34 reproduce EA's shipped bytes
  byte-exact on sampled instances** (MultiplayerColor joined after modeling its inline `MetaGameSide` field);
  GameObject is **40/50** on a *widened* sample, with the residual characterized as module-tag / weak-ref name
  recovery bounded by StringHashes coverage (byte-exact once the name is in the table); Environment is
  structurally exact with one known-lossy weak-ref; Road has no sampled instances. Full matrix, sampled
  instances, and method in **[docs/reference/COVERAGE.md](docs/reference/COVERAGE.md)**.
- ✅ **Master `StringHashes.xml`** harvested from an SDK compile, so module-id / inherited string values resolve
  during decompilation.
- 🔧 **Close the GameObject residual (~20% of the widened sample)** — now characterized: the remaining diffs are
  isolated 4-byte module-id tags (and Environment's one weak-ref) that `FastHash` to names absent from the
  supplied StringHashes — byte-exact once harvested. The fix is a **more complete StringHashes table** (harvested,
  blocked today by a `-scd` whole-tree finalization crash — tracked), **not** a compiler change: hardcoding the
  shipped value would be overfitting ([verification-blind-spots](docs/design/verification-blind-spots.md) §2).
- 🔧 **Tolerant-but-honest validation.** Where the authoring schema is a strict *subset* of what shipped data
  uses (e.g. enum fields holding integer values the schema never names), the compiler reproduces the shipped
  value rather than refusing it — **informational** when attested in shipped data, a loud **warning** when novel.
  Tolerance + a single warning have landed; the info-vs-warning split awaits a harvested attested-value set
  (**harvested from shipped data, never hardcoded**).
- ✅ **CI** — builds the compiler + decompiler on every push/PR (`.github/workflows/`); the data-dependent
  round-trip gate runs locally / self-hosted (game data can't live in CI).
- 📋 **Verify inputs, not just outputs — the input-integrity preflight.** The round-trip gate proves our
  *output* matches shipped bytes, but nothing checks that the *inputs* (schema, base streams, manifests, SDK
  XML) are the pristine ground truth — the oracle silently assumes they are. That assumption is the hole
  **finding [0013]** fell through: an agent edited a bring-your-own schema in place, and a "verified" result then
  quietly depended on the edit. A one-time re-download fixes today; it doesn't stop the next silent edit. Fix,
  symmetric with the output gate:
  1. **Establish a clean set** — verified game install + fresh SDK.
  2. **Commit a checksum manifest** — `inputs.sha256`: SHA-256 of every BYO input (each schema,
     `base-stream/*.{bin,relo,imp,manifest}`, `base-manifests/*`, the dataroot XML). It holds *hashes, not EA
     content*, so it lives in git as our own file.
  3. **`verify-inputs` preflight** — `roundtrip.sh` / the toolchain hash the BYO files first, compare to the
     baseline, and **refuse (or loudly warn) on any drift**. Input integrity becomes "correctness you can run,"
     and a "verified" result can never again silently rest on a mutated input, because the preflight catches it.

  **Built (data-independent):** `tools/verify-inputs.py` (generate `--baseline` from a *verified-clean* set —
  refuses to seed from a dirty tree; verify mode with dedicated exit codes) + `tools/verify-inputs-preflight.sh`
  wired into **both** round-trip gates (`roundtrip.sh`, `corpus-roundtrip.sh`): drift → hard-abort before the
  round-trip, no baseline yet → warn + continue. Enforcement switches on automatically the moment `inputs.sha256`
  is generated from the clean set and committed (step 2). *Remaining:* generate + commit `inputs.sha256`.
- 📋 **BYO / EA-sourced inputs are read-only.** Schemas and game data are never modified in place; OpenWrath's
  additions live in owned, tracked files or in code. Encoded in `CLAUDE.md` and the subagent-spec template so it
  can't recur. (finding [0013])
- 📋 **Subagent-spec template = goal + reuse-map + boundaries** (the systemic fix). Every delegated task carries
  three parts, not one: (a) an oracle-backed **bounded goal**, (b) a **reuse map** — the existing
  helpers/authorities it must *not* re-derive (`refpack.py`, `StructReader`'s float-render, the channel
  type-ids, …), and (c) **boundaries** — what's off-limits (BYO/EA files, the comparator/oracle). The RefPack
  overfit (0012) and the schema edit (0013) both trace to specs that had (a) but not (b)/(c); this is the one
  change that attacks the recurring root cause rather than the symptom.

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
- ✅ **Art — `W3DAnimation` byte-exact vs shipped** (Pillar 2, first milestone). Decompile ↔ recompile via the
  W3X compiler, with lossy time-coded / adaptive-delta channels **passed through** in their shipped compressed
  form (no re-compression — §4 tiered fidelity, done right). Verified from the **pristine** schema: seed-7
  sample **125/125** byte-exact + all four channel-codec cases (mixed / time-coded / adaptive-delta / empty);
  data types regression-clean (Armor 207/207, Weapon 456/456). The runtime channels are bound to EA's own
  `AnimationChannelTimecoded`/`Delta` types **in code** (`SchemaSet.BindRuntimeAnimationChannels`), never by
  editing a BYO schema file (finding 0014); §3 drift-seeds deduped (shared float-render, one channel-typeid
  source, one reader-dispatch helper).
- 📋 **Schema-overlay registry** — the permanent home for in-code schema augmentations. The W3DAnimation runtime
  binding above is the **prototype**; it is data-shaped (`(element, type)` table) precisely so it migrates into a
  general registry of owned, declarative overlays (per-type, versioned) when a second one is needed, instead of
  accreting ad-hoc augmentations in `SchemaSet`. (The owned-schema-file / `xs:redefine` variant is the documented
  alternative to evaluate then.)
- 📋 **Art — `W3DMesh`, then textures (DDS).** Mesh via the vertex pipeline; textures can't bit-reproduce EA's
  compressor, so a **stated weaker tier**, never reported as byte-exact ([verification-blind-spots](docs/design/verification-blind-spots.md) §4).
- 📋 **Maps** (greenfield `.map` reader + writer; 96 shipped maps as corpus) and **sound** (native EALayer3
  decode; faithful-not-identical re-encode) — later pillars, each its own dedicated run.
- 📋 **Art / asset compilers** for new-content mods — the big build. Unlocks making *new* assets, not just editing
  existing ones; a separate effort from the data toolchain above.

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
