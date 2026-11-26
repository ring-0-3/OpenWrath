# Roadmap

Where OpenWrath is and where it's going. Status is honest: a thing is only "done" if it's **verified**. For
fidelity, that means measured by `tools/roundtrip.sh` — and the strong claim is the **ground-truth** mode
(`--from-binary`), which compares our output to the bytes the game actually ships, not just to our own compiler's
output. Help is welcome on anything below — especially the 🔧 and 📋 items.

Legend: ✅ done & verified · 🔧 in progress · 📋 planned

## Go-forward sequence (priority order)

The per-area sections below hold the detail; this is the **path**. OpenWrath is crossing from an *interop toolchain*
(read/write existing KW assets byte-exact — nearly complete: the data types, the whole W3D model graph, particles,
and the texture records) to a *creation platform* (author new content — the §4 frontier). The ordering is by oracle
strength: finish what's decidable, then validate the keystone, then the frontier.

1. ✅ **`Texture` / `OnDemandTexture` shipped-payload pass-through** (DONE 2026-11-25; finding
   [0024](docs/findings/0024-texture-ondemandtexture-byte-exact-shipped-payload-passthrough.md), spec'd by
   [0023](docs/findings/0023-texture-ondemandtexture-record-layout-recon.md)). Byte-exact for *shipped* textures via
   the 0018 pass-through pattern (the record wraps a literal DDS blob) — whole-stream **1575/1575** + **123/123**,
   closing the texture *records*. Authoring *new* textures stays stated-tier.
2. 📋 **Finish the byte-exact surface** (oracle-strong, cheap). Sweep the remaining "Not modeled" types for
   registration-only wins (as the atlas records / particles turned out to be); **`AudioFile`** (likely a
   records-tractable + encoded-payload-pass-through split, like textures — shipped audio byte-exact, new audio
   stated-tier); widen coverage beyond `static_common`; close the **GameObject residual** (StringHashes coverage);
   generate + commit the `inputs.sha256` baseline (invariant 4). Keep the foundation honest.
3. ✅ **The re-pack equality gate on `W3DMeshProcessor`** — the **keystone, DONE** (2026-11-26, finding
   [0025](docs/findings/0025-w3dmesh-repack-equality-gate.md)). `semantic-decode ∘ W3DMeshProcessor == shipped`
   verified **300/300 byte-exact** (stratified seeded sample, all 20 declaration layouts) via
   `tools/mesh-repack-gate.sh`; the previously-unverified packer is now validated against shipped bytes, and the gate
   exposed+fixed three latent defects. Blender exporter = **GO** for the round-trip tier (unexercised packer paths —
   half-float / Xenon / >2 weights — remain honestly unverified).
4. ✅ **Semantic mesh decode** (packed vertex buffer → positions / normals / UVs / bone influences) — **DONE** (0025):
   `StructReader.ReadSemanticVertexData`, opt-in `bab-decompile --semantic-mesh`; pass-through stays default. Unlocks
   the Blender **viewer**. Next: the Blender add-on proper (item 6), shelling out to this CLI.
5. ✅ **Blender read-only viewer/importer — DONE** (2026-11-26, finding
   [0026](docs/findings/0026-blender-viewer-importer.md)). A thin CLI front-end (`blender/openwrath_import/` +
   `openwrath blender install/model/view`) imports a shipped W3D model into Blender — no forked format logic, all
   bytes via `bab-decompile`. Rigid placement **exact** (`worlds[bone] @ v`); skinned position via the vertex's
   **channel-0** bone (weights are deform-only), restoring 4-fold symmetry with a per-vertex seam-continuity gate.
   **Stated-tier** (scene assembly has no byte oracle), with a reported soft-blend seam residual; the earlier
   centroid-level "verified" was corrected to per-vertex. Verified in-GUI on the NOD Redeemer (quadruped, 99 bones).
   Next on this thread: **textured viewer** (item 6a) → the **exporter + its byte-exact roundtrip gate** (item 6b) +
   semantic `W3DAnimation` decode (keyframes, for live deform / the soft-blend residual).
6. 📋 **Blender round-trip tier — CRITICAL PATH (reliability keystone at the ecosystem edge).** An exporter is a
   *second packer path the oracle can't see* unless its correctness is made decidable; this item keeps the
   byte-exact oracle reaching all the way to Blender, the same discipline that guards the rest of the toolchain.
   - **6a. Textured viewer** (in flight). Resolve each mesh's `<FXShader>` texture refs → decode the referenced
     `Texture` assets → base64-decode their shipped-DDS `<Payload>` (finding 0024) → UV-mapped Blender materials,
     replacing the grey placeholder. Stated-tier display, with the decidable sub-anchors (names parse; each payload is
     a valid DDS). Unblocks the visual half of texture editing. → finding 0027.
   - **6b. Exporter + the Blender byte-exact roundtrip gate.** The **acceptance test, not a footnote**: Blender
     **import → export → recompile → byte-compare to shipped** must be **byte-exact for unmodified models (geometry
     *and* textures)**, reusing the existing 0025 `mesh-repack-gate` / `compare-stream.py` oracle *with Blender now in
     the loop*. The CLI gate (0025) already proves `decode ∘ packer == shipped` 300/300; this gate proves the added
     delta — `decode ∘ Blender-scene ∘ export ∘ packer == shipped` — i.e. that Blender preserves every authoring
     attribute losslessly (vertex order/identity, normals/tangents/binormals, bone-influence channel order incl. the
     channel-0 reference bone + the weight-0 unreferenced-bone channel, vertex colours, the full `<FXShader>` block,
     hierarchy, container). Realistic design: carry the raw decoded attributes on the datablocks and round-trip an
     *untouched* mesh straight back out (shipped textures already pass through byte-exact, 0024). The gate **bounds
     what the exporter may emit**: the 0025-unverified packer paths (half-float, Xenon/big-endian, >2 blend weights)
     stay off-limits until a corpus exercises them. **Edited** geometry/textures remain the §4 **stated tier**
     ("loads + renders"), never byte-exact — the gate is for *unmodified* round-trips. → a dated finding when GREEN.
7. 📋 **First visible in-game win — loose-file `add-search-path` texture override** (0021 milestone 0). The cheapest
   path to an HD texture *actually rendering in KW* — stated-tier (new content, in-game-acceptance gate),
   modkit/packaging work. The demo moment, and an end-to-end validation of the texture pillar in the real engine.
   (This is also the in-game delivery route for **edited** textures — the stated-tier half of "edit textures".)
8. 📋 **Then the big pillars** (each its own effort — choose by goal, not forced order): **new-content authoring**
   (meshes via the re-pack gate, textures stated-tier, audio); **maps** (greenfield `.map` reader + writer, 96-map
   corpus); **sound** (EALayer3, frontier). (Blender integration's viewer+exporter are now the critical-path item 6.)
   Detail in the Content-pipeline and Platform sections below.

**Tier discipline past the byte-exact surface:** authoring / new content is the §4 frontier — use a *decidable gate*
where one exists (the re-pack equality test), a **stated** weaker tier (in-game acceptance) where it doesn't, and
never report a stated tier as byte-exact ([verification-blind-spots](docs/design/verification-blind-spots.md) §4).

## Compiler (XML → binary)
- ✅ Native-Linux port of BinaryAssetBuilder (runs under `dotnet`, no Wine), byte-faithful to EA's output.
- ✅ Correct x64→32-bit on-disk pointer layout; case-insensitive paths; native XInclude / expressions / RefPack.
- ✅ Cross-stream reference typing via reference manifests (`-rm`).
- ✅ **42 asset types registered** (`Plugin.cs` `Initialize()`): the five core gameplay types plus the gameplay
  breadth batch (Upgrade, SpecialPower, OCL, FXList, DamageFX, ExperienceLevel, LogicCommand(Set), Stance,
  RadiusCursor, Weather, Mouse, OnlineChatColors, ConnectionLineManager, PhaseEffect, Road, MultiplayerColor),
  the audio/LOD/environment batch (AmbientStream, MusicTrack, DialogEvent, LargeGroupAudioMap,
  Static/Dynamic GameLOD, GameLODPreset, CrowdResponse, VideoEventList, Environment, AudioEvent, Multisound,
  MiscAudio, AudioSettings, AudioLOD), the first content-pipeline data type (FXParticleSystemTemplate,
  finding 0020), the texture-pillar UI-atlas records (PackedTextureImage, OnDemandTextureImage, finding 0022),
  and the texture records themselves (Texture, OnDemandTexture — shipped-DDS-payload pass-through, finding 0024).
- ✅ Compile-fail bug-class fixes surfaced by the ground-truth gate (field-order error; out-of-schema enum
  values) — see Verification.
- ✅ **MultiplayerColor** recompile fixed — modeled its inline `MetaGameSide` field (8/8 byte-exact). The one
  remaining data-type gap is the **GameObject residual**, tracked under Verification below (StringHashes coverage,
  not a compiler change).

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
  fixed this way (an `ActiveBody` field-order error; an out-of-schema enum case; the shared draw-module
  `SetAnimsToLastFrameOnConstructionComplete` default), bringing GameObjects to **40/50 byte-exact** vs shipped
  with the residual characterized (see below). Art / W3D are handled by their own pillar (W3DAnimation is already
  byte-exact); particles (`FXParticleSystemTemplate`) are byte-exact (finding 0020); textures → content pipeline.
- ✅ **RefPack detection + single authority** (finding [0012]). RefPack is identified by its **second** byte
  (`0xFB`); the first byte is a flags byte that *varies* (`0x10`/`0x11`/`0x90`/`0x91` — `0x90` ships on
  `static_common.bin`). A first guard matched only `0x10FB`, so other variants misreported as "Xbox360
  big-endian" (overfit to one sampled variant + duplicated-knowledge drift). Fixed: detect on `byte[1] == 0xFB`
  via a single shared authority (`Containers.RefPack.IsRefPack` in C#, `is_refpack()` in the canonical
  `modkit/lib/refpack.py`), corrected the "0x10FB magic" wording, deleted the byte-identical duplicate
  `pytools/refpack.py`, guarded by a variant unit test.
- 🔧 **Transparent RefPack *decompression* in the .NET reader.** The modkit already decompresses (Python
  `refpack.py`); the C# decompiler currently *detects* a compressed manifest and names the fix ("decompress
  first"). Port the decompressor into the reader (or the harness) so a compressed manifest/stream just works
  end to end.

## Verification & reliability
- ✅ `tools/roundtrip.sh` — the correctness gate, two modes:
  - **closed-loop** (`<source.xml>`): compile → decompile → recompile → assert byte-identical. Proves the
    decompiler is a faithful inverse of the compiler. Verified byte-exact e.g. ArmorTemplate 207/207,
    WeaponTemplate 456/456, LocomotorTemplate, AttributeModifier, and GameObjects incl. `GDIConstructionYard`.
  - **ground-truth** (`--from-binary <stream.manifest>`): decompile a *shipped* linked stream, recompile, and
    byte-compare every asset to the **original shipped bytes**, bucketed per type (byte-exact / same-size
    value-diff / size-mismatch / recompile-missing, with first-diff offsets). This proves the output is *what
    the game actually loads*, and it has surfaced real bugs closed-loop alone could not.
- ✅ **Ground-truth results (2026-11-24; FX + textures added 2026-11-25):** of the 42 registered types, **39 reproduce
  EA's shipped bytes byte-exact on sampled instances** (MultiplayerColor joined after modeling its inline `MetaGameSide`
  field; FXParticleSystemTemplate joined via the plain pipeline + a required-null-module decompiler fix, finding 0020;
  PackedTextureImage / OnDemandTextureImage joined via plain registration — whole-stream 870/870 and 123/123, finding 0022;
  Texture / OnDemandTexture joined via a shipped-DDS-payload pass-through — whole-stream 1575/1575 and 123/123, finding 0024);
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
  **⚠ Version-blindness (finding [0016](docs/findings/0016-static-mod-stream-is-complete-replacement-not-overlay.md),
  corrected):** the loadable static world is a **base + overlay chain**, not one file — Core/1.0 `static_common`
  (the 195 MB full byte pool) plus the active, version-matched overlay (1.3 = the patch `Static_mod`, a complete
  entry list with 1.3 TypeHashes but sparse data). The baseline must capture the **chain** and record the **patch
  version**. `inputs.sha256` currently records *no* patch version, so a pristine-but-stale (1.0-only) baseline would
  pass every input check and still crash the game on a `0010` TypeHash mismatch (e.g. `DefaultHotKeys`
  `0x692d0b3a`→`0x12cb83dc`, which drifted at 1.1). The baseline step must pin, and record, the patch version.
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
  - ✅ **Loadable base-game override mod SOLVED (finding
    [0017](docs/findings/0017-overlay-mod-overrides-base-gameplay-the-complete-recipe.md)).** A tiny overlay that
    overrides base gameplay on retail 1.3 was achieved **in-game** (a WeaponTemplate's fire-rate / ClipSize /
    AttackRange all took effect, no crash). The recipe: a **sparse differential** (complete entry list, data only
    for the changed assets, `\x02` defer to `static_common_2`) + a **low-LOD twin** (`static_l_mod` → `static_mod`)
    + the **WorldBuilder companion** (`worldbuilder_mod`) + the **three `.version` redirect files** (`static`,
    `static_l`, `worldbuilder` = `_mod\n`) + the **base's max-chunk header kept** (not recomputed — the final
    crash) + unique per-stream checksum. Builder codified + verified byte-exact: `modkit/lib/build_overlay.py`
    (+ `retag_checksum.py`). 0016's "must be complete data" / checksum-collision theories are withdrawn; 0005 is
    refined (an overlay IS consulted, via the `.version` redirect).
  - 🔧 `mod package` → **the shareable deliverable.** Builds the **zero-EA overlay diff** (only the user's declared
    overrides; hard gate refuses any undeclared/EA asset; sliced `inheritFrom` bases carry their `<Defines>` macro
    context; fsync+integrity-verified — finding
    [0015](docs/findings/0015-standalone-overlay-override-needs-sliced-inheritfrom-base.md)). Go-forward: emit the
    **strict zero-EA diff + a bundled recipient-side assembler** (the project's chosen default — ships *nothing*
    EA-derived; the recipient's own `static_common_2`/`worldbuilder_2` supply the entry-list metadata locally;
    design: **[diff-plus-assemble-at-install](docs/design/diff-plus-assemble-at-install.md)**). A full ~6MB
    **drop-in** is possible but **LOCAL-ONLY** (it carries EA-derived entry-list metadata), so OpenWrath never
    presents it as shareable. Also valid: `mod bake` into an existing complete stream (SI).
  - 📋 **multi-mod merger** — select N mods → bake their diffs into ONE overlay so all features run (one static
    stream owns a family, so overlay mods are otherwise mutually exclusive — 0017). Clash detection/resolution is
    future work. **Motivating case (2026-11-25):** installing two separate `static_mod` overlays (a commando test +
    a conyard-money mod) silently conflicts — only one owns the family — and had to be hand-merged into one project
    (both `<GameObject>` overrides + the weapon) before `build-local`. The merger should do this automatically:
    `openwrath mod merge <modA> <modB> … → one overlay`, with per-asset clash detection.
  - ✅ `mod check` — pre-flight validation: dangling references + unknown fields / schema errors with `file:line`,
    plus per-type schema drift vs the target. Runs **automatically before a bake** (`--no-check` to skip).
  - 📋 **stream explorer — list available streams, show which are LIVE, and search within one.** Today `find` searches
    one (default) installed stream by name and there is no way to see what streams exist or which the engine actually
    loads. Add: **(a) `openwrath streams`** — enumerate the stream families present across the game's `.big` archives
    (`static_common` / `global_common` / `global_english` / … ) and mark **which are live** via the `.version` redirect
    (`data\<family>.version` → base vs the `_mod` overlay — the live-stream mechanism from findings
    [0016](docs/findings/0016-static-mod-stream-is-complete-replacement-not-overlay.md)/[0017](docs/findings/0017-overlay-mod-overrides-base-gameplay-the-complete-recipe.md),
    so a user sees at a glance whether an overlay is active and which stream wins); **(b) `find --stream <name>`**
    (and `inspect --stream`, already flagged in the diagnosability papercut below) — target a specific stream so you
    can search within it rather than the default. **Reuse, don't re-derive:** `lib/bigextract.entries` (big contents),
    the existing `.version` resolver (`_VERSION_POSTFIX` / the `<family>.version` reader in the build path), the
    stream-name discovery already in `verify`, `lib/biglist.py`, and the `find` matcher — this is expose-and-wire, not
    new format work.
  - 📋 base-game-target guard — default to mod targets; require an explicit flag + warning to splice base-game
    streams (avoids C&C:Online / replay desync).
  - 📋 installable command — a `pipx`-installable `openwrath` that locates or fetches the compiler binary, so
    setup is "install + init" rather than "clone + build".
  - 📋 **GameObject-override robustness — three real bugs hit modding the GDI construction yard (2026-11-25).**
    (a) **Unnamed stock modules block an `inheritFrom` override.** When a stock GameObject carries a module with
    no `id` (the GDI conyard's `StructureUnpackUpdate`), `mod check` + the compiler reject an `inheritFrom`
    override of it (`has an unnamed module …`). Auto-name unnamed base modules (or let the override proceed).
    (b) **The `mod package` block-extractor (`_find_toplevel_block`) is indent-sensitive.** A full/decompiled
    override whose indentation isn't uniform gets its element body truncated in the assembled `static.xml`
    (`GameObject start tag … does not match end tag of AssetDeclaration`). Make block extraction tag-depth-based,
    not indent-based — so a decompiled asset is directly usable as an override source.
    (c) **`inheritFrom` overrides pull unexpanded base `#define` macros.** The sliced base can contain macro
    values (`CampnessValue="CAMPNESS_CONYARD"`) that fail the package compile (ExpressionEvaluator is off in that
    path); the define-slicer (finding [0015]) doesn't always harvest them. Harvest/expand the base's defines.
    *Workaround used:* a self-contained **decompiled** full override (clean values, no base include) — works once
    its indentation is uniform (bug b).
  - 📋 **Diagnosability / signposting papercuts — three hit during the 0011 commando re-investigation (2026-11-25).**
    Each cost real time because the tool failed *opaquely* rather than pointing at the fix.
    (a) **`inspect` desyncs on the installed stream with no fallback or hint.** `openwrath inspect GU_CMMNDO_SKL`
    returned `<RawAsset … reason="desync: struct W3DHierarchy@0 len 12 past instance end (0)">` — looks like a
    decompiler bug — yet the *same* asset decompiles byte-exact via `bab-decompile.dll decompile-stream` against the
    clean `ea-roundtrip/eastream/static_common.manifest` + the right `--rm`/`--schema`. `inspect` should (i) print
    *which* stream it read, (ii) on desync, suggest (or auto-fall-back to) the clean roundtrip stream, and (iii)
    accept a `--stream`/`--rm` override so `inspect` can reach the base asset without hand-running the raw tool.
    (b) **`mod bake` / `build-local` swallow the compiler's real error message.** A failed override compile printed
    only `error: compile produced no stream for GDICommando.xml:` followed by a stack trace whose first line was
    truncated mid-path (`aryAssetBuilder/Core/SageXml/DocumentProcessor.cs:line 360`) — the exception *Message* (the
    actual cause) was cut off, and `-v` didn't surface it. Surface the compiler's exception Message + the offending
    XML `file:line`, not a truncated stack tail.
    (c) **No signpost that replacing an inherited module needs `xai:joinAction="Replace"`.** `mod add` scaffolds an
    `inheritFrom` override commented "change an attribute or add a child element here", but adding a module whose
    `id` already exists on the base (e.g. a `<ScriptedModelDraw id="ModuleTag_Draw">` to re-point a `WeaponLaunchBone`)
    fails with the opaque error in (b). The join-action idiom (`="Replace"` to swap a module, `="Remove"` to drop
    one) is undocumented in the scaffold. Mention it in the `mod add` comment and/or detect duplicate-module-id at
    compile and suggest it. *Workaround used:* add `xai:joinAction="Replace"` to the overriding module — compiles clean.
  - ✅ **Projectile-launch SOLVED + forward-reference tooling (finding
    [0011](docs/findings/0011-hitscan-units-do-not-detonate-launched-projectiles.md), 2026-11-26).** A hitscan unit
    *can* launch a projectile — the gate was **stream load-ORDER**, not "engine coupling": a `ProjectileNugget` binds
    its projectile (GameObject) and warhead (WeaponTemplate) by **forward lookup at load**, so each must appear
    **before** the weapon in the compiled manifest or it silently binds to null (projectile-order→spawn,
    warhead-order→detonation; proven in-game on the GDI Commando *and* NOD Avatar). EA emits a topological
    (dependencies-first) order (only 14/73,928 refs are forward, and all 10 EA ones are benign `→ Texture`). New tools:
    `modkit/lib/reorder_stream.py` (lockstep reorder of manifest + `.bin/.relo/.imp`, relo/imp asset-local so safe;
    then `retag_checksum.py`) and `modkit/lib/check_forward_refs.py` (lints a built stream — FATAL
    `WeaponTemplate → GameObject/WeaponTemplate` forward edges, BENIGN `→ Texture`; exit 1 to gate a build).
  - ✅ **Forward-ref safety wired into the build (2026-11-26).** `mod build-local` now runs an **auto-ordering pass**
    after applying overrides: it detects every FATAL forward edge (shared `check_forward_refs.scan`), reorders so each
    nugget's projectile/warhead precede the weapon (`reorder_stream.py --auto-fix`, lockstep bin/relo/imp), re-checksums,
    and **gates** the build on a clean result — so projectile mods "just work" with zero manual surgery (verified
    end-to-end: a pure-`ProjectileNugget` commando + Avatar build to 0 fatal edges and launch in-game). The forward-ref
    gate lives in the *build* path (order is a compiled-stream property, not a source one, so `mod check` — which is
    source-level — isn't the right home; the stream-level gate in build-local is). Still 📋: (a) apply the same pass to
    `mod bake`; (b) grow the FATAL/BENIGN classifier as more order-sensitive reference kinds are verified in-game
    (today only weapon→projectile/warhead is proven fatal, →Texture proven benign; everything else is SUSPECT, not asserted).
  - ✅ **Two build-local robustness fixes surfaced by the above (2026-11-26).** (a) **Bounded temp:** `_apply_overrides`
    now deletes each intermediate `op{N}` stream dir once the next supersedes it — previously it kept a full ~400 MB
    copy per override (tens of GB for a large mod → **disk-full → silent partial write**), now ~2 copies regardless of
    override count. (b) **Partial-write detection:** each splice/insert step now verifies **all four** stream files
    exist (not just the manifest), so a truncated write (e.g. `ENOSPC`) fails at its source with the producer's real
    error instead of an opaque `FileNotFoundError` in the next step.
  - ✅ **String-table editing — custom unit names / tooltips (2026-11-26).** A `[strings]` table in `mod.toml`
    (`"NAME:GDIPitbull" = "Rift Pet"`, `"DESC:…"`, `"TYPE:…"`) is built by `mod build-local` into a LOCAL-ONLY
    `<name>-strings.big` and `add-big`'d in the mod skudef — custom in-game names and build-button tooltips with **no
    CSF compiler and no edit of the BYO `cnc3.csf`**. `modkit/lib/csf.py` is a reusable reader for the compiled
    `.csf` string table + writer for the plaintext `.str` source the engine also accepts (format reverse-figured +
    verified vs the shipped 7395-label table; the engine loads **one** table, so the complete table is shipped →
    LOCAL-ONLY, embeds EA strings, same posture as the overlay big). Zero-EA-public path (ship only the label diff +
    recipient-side assembler) is future work, mirroring `diff-plus-assemble-at-install`.
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
- ✅ **Art — `W3DMesh` byte-exact vs shipped** (Pillar 2, second milestone). Decompile ↔ recompile via the W3X
  compiler, with the packed `W3DMeshVertexData` (interleaved vertex buffer + D3D declaration + bone-remap table)
  **passed through** in its shipped runtime form — a `<VertexData>` element the compiler writes straight back, no
  re-packing (the `W3DMeshProcessor` packer is lossy; §4 tiered fidelity, done right — the mesh analogue of the
  W3DAnimation pass-through). Verified from the pristine schema: seed-7 sample **300/300** byte-exact across plain,
  skinned (bone-remap), and `AABTree` collision meshes; data types regression-clean (Armor 207/207, Weapon
  456/456). Runtime vertex data bound in code (`SchemaSet.AugmentRuntimeMeshVertexData`), never by editing a BYO
  schema (finding [0018](docs/findings/0018-w3dmesh-byte-exact-via-runtime-vertexdata-passthrough.md)); two latent
  AABTree bugs fixed in passing (anon-inline scalar list, `**`-marshaler stack-address push).
- 📋 **Schema-overlay registry** — the permanent home for in-code schema augmentations. There are now **two**
  prototype bindings (W3DAnimation's runtime channels + W3DMesh's runtime `<VertexData>`), both data-shaped and
  both currently accreting in `SchemaSet` — i.e. the "when a second one is needed" trigger has arrived. Migrate
  them into a general registry of owned, declarative overlays (per-type, versioned). (The owned-schema-file /
  `xs:redefine` variant is the documented alternative to evaluate then.)
- ✅ **Art — `W3DContainer` (HLod) / `W3DHierarchy` / `W3DCollisionBox` byte-exact vs shipped** (Pillar 2, third
  milestone). The connective tissue that binds meshes to a skeleton + LODs; plain sequential structs (no lossy
  packed form), so handled by the **ordinary pipeline** — type registration + hand-written marshalers — with **no**
  runtime pass-through and **no** in-code schema binding (deliberately not overfitting the mesh/animation answer).
  The one refinement: `SubObject.RenderObject` is a schema `xas:refType` *choice* (`<Mesh>`/`<CollisionBox>`), so
  the decompiler now picks the wrapper from the **referenced asset's actual type** via a schema-driven index (no
  hardcoded element/type name). Verified against `static_common` seed-7 samples (150 each) all byte-exact; whole
  corpus decompiles clean (finding
  [0019](docs/findings/0019-w3dcontainer-hierarchy-collisionbox-byte-exact-plain-pipeline.md)). Closes the W3D
  model graph.
- ✅ **Particles — `FXParticleSystemTemplate` byte-exact vs shipped** (content pipeline, first *data* type). An
  ordinary data type that was only ever un-registered: the model + full polymorphic-module marshaler suite
  (Physics / Draw / Volume / Velocity / Update / Event) already existed, so it round-trips through the **plain
  pipeline** — one registration line, **no** runtime pass-through, **no** in-code schema binding. KW TypeHash
  `0xA0C56702` harvested from shipped `static_common` (the commented scaffold's `0xA148D511` is the TiberiumWars
  table — 0016 version-trap avoided); comparator-wildcarded, so harvested-not-oracle-verified. One schema-driven
  decompiler fix: a required (`minOccurs=1`) single polymorphic-module element whose binary pointer is null (the
  reworked-laser / Redeemer / beam / railgun family) decompiles to an **empty wrapper** (`<Velocity/>`) — which
  compiles straight back to the null pointer, byte-exact. seed-7 **150/150** + all **35** null-module systems
  byte-exact; whole corpus 1674 decompile clean; regression-clean (Armor 207/207, Weapon 456/456, W3D still exact,
  schema-selftest pass, GameObject inert). Finding
  [0020](docs/findings/0020-fxparticlesystemtemplate-byte-exact-plain-pipeline-plus-required-empty-module.md).
- 🔧 **Art — textures (DDS).** Build order from 0021 (oracle-strongest first).
  - ✅ **UI-atlas records** (`PackedTextureImage` / `OnDemandTextureImage`) — byte-exact via plain registration,
    whole-stream 870/870 + 123/123, finding 0022.
  - 🔎 **`Texture` / `OnDemandTexture` record layout** characterized (finding 0023, Recon): the `Texture` record is
    a 12-byte header + a **literal D3D9 DDS blob** (DXT1/3/5 + uncompressed, full mip chain), relocated by one relo
    entry; `OnDemandTexture` is an 8-byte all-zero lazy placeholder. Next milestone: **shipped-payload pass-through**
    (the W3DMesh/0018 pattern) → byte-exact for *shipped* textures without reimplementing the compressor.
  - 📋 **New/authored textures (the pixel path).** Can't bit-reproduce EA's DXT compressor, so a **stated weaker
    tier**, never reported as byte-exact ([verification-blind-spots](docs/design/verification-blind-spots.md) §4).
  - 📋 **Loose-file `add-search-path` override** (the route the 4K pack rides) — a packaging feature gated on
    in-game acceptance, not a compiler change; separate later phase.
- 📋 **Maps** (greenfield `.map` reader + writer; 96 shipped maps as corpus) and **sound** (native EALayer3
  decode; faithful-not-identical re-encode) — later pillars, each its own dedicated run.
- 📋 **Art / asset compilers** for new-content mods — the big build. Unlocks making *new* assets, not just editing
  existing ones; a separate effort from the data toolchain above.
- 🔧 **Blender integration** (viewer → importer → exporter) — **CRITICAL PATH (go-forward item 6).** A Blender
  add-on that is a **thin front-end to the OpenWrath CLI** — scene ⇄ W3X authoring XML — so format knowledge never
  forks into a plugin (§3 at ecosystem scale). Needs the **authoring/semantic tier**, not just round-trip
  pass-through: a semantic vertex decode (the base64 packed buffer is not editable geometry) plus
  `W3DHierarchy`→armature / `W3DContainer`→grouping. The CLI **re-pack equality test** —
  `semantic-decode ∘ W3DMeshProcessor == shipped bytes` — is **done + green** (0025); the viewer shipped (0026).
  **The exporter's acceptance gate is the Blender byte-exact roundtrip** — `decode ∘ Blender-scene ∘ export ∘ packer
  == shipped` for **unmodified models (geometry + textures)**, reusing the 0025 oracle with Blender in the loop. It
  proves Blender preserves every authoring attribute losslessly (the project's reliability keystone at the ecosystem
  edge); it is an acceptance test, **not** a mere regression guard. Authored/edited geometry is a **stated tier**
  ("loads + renders"), never byte-exact (§4); the gate bounds the exporter to the 0025-verified packer paths. Design:
  **[docs/design/blender-integration.md](docs/design/blender-integration.md)**.
  - 📋 **(perf, deferred — not now) Speed up `openwrath blender view` / `model` decode.** `_decode_model` spawns a
    **separate `bab-decompile` (dotnet) process per asset** — container + hierarchy + every mesh + every collision
    box + every texture — so a full model is dozens of cold .NET starts (the NOD Redeemer: ~34 meshes + collision
    boxes + textures), which is the dominant wall-clock cost. Correctness is unaffected; it's just slow. Optimize by
    **batching into far fewer invocations** — e.g. one `decompile-stream` pass per needed type (the verb already
    supports `--type` + `--semantic-mesh`, decoding all instances of a type at once) instead of one `--only <name>`
    per asset, or a single warm/long-lived decode process. Profile first to confirm dotnet-startup is the cost before
    optimizing. Keep the single `build_decode_argv` source of truth (invariant 3).
  - 📋 **(viewer, stated-tier, optional) House/team-color preview.** In-game a player's **house color** recolors the
    masked regions of a unit (the NOD-red accents → blue/green/… per player) at **render time**, via the `Objects*.fx`
    shader + a team-color **mask** (no dedicated mask slot in the shader → the mask rides a channel of an existing
    texture, most likely the diffuse alpha — standard SAGE practice). The colour itself is a **per-player runtime
    constant the engine feeds the shader — NOT stored in the model** (evidence: shaders carry a `HouseColorPulse`
    constant but no stored colour value). The viewer today correctly shows the **default base diffuse** (red for NOD);
    a future option could preview a chosen house colour by implementing the shader's house-colour path in Blender —
    cosmetic, **stated-tier** (full `FXShaderMaterial` semantics don't map cleanly, per the design doc). **Irrelevant
    to the byte-exact exporter:** team colour isn't in the model bytes; only static shader constants like
    `HouseColorPulse` are, and those already round-trip inside the `<FXShader>` block.
  - 📋 **(viewer, stated-tier, optional) Additive/translucent FX-mesh blend.** The effect meshes (muzzle/laser glow,
    flashing lights) are drawn **additive/translucent** in-game but the viewer shows them **solid** — it maps only the
    base-color texture onto an opaque Principled BSDF and sets no blend mode. Cosmetic, same stated-tier class as the
    house-colour / NormalMap gaps. **Unlike house colour, the blend data IS in the decoded bytes** — `DefaultW3D.fx`
    meshes carry `<Int BlendMode>` / `<Int SecondaryTextureBlendMode>` / `<Float Opacity>` / `ColorEmissive` /
    `DepthWriteEnable` constants — so a future viewer option could map `BlendMode`→Blender `blend_method`
    (additive→emission+blend), `Opacity`→alpha, `ColorEmissive`→emission for a faithful preview **without inventing
    data** (still a heuristic approximation of the compiled `.fx`, so stated-tier, not byte-decidable). **Irrelevant to
    the byte-exact exporter:** those blend constants round-trip verbatim inside the `<FXShader>` block, so an exported
    mesh keeps its correct in-engine blend regardless of how Blender previews it.
- 📋 **Community mods as frontier existence-proofs** (research strategy). The KW community has shipped content
  OpenWrath can't yet produce — 4K/HD **texture** add-ons, total-conversion mods with **new geometry**, and
  **particle/FX** patches (e.g. reworked laser effects). Each proves the retail engine *accepts* a kind of non-EA
  content; studying the **mechanism** (not their bytes) turns "frontier, no oracle" into "stated tier + in-game
  acceptance gate." The corpus spans three tiers: particles (`FXParticleSystemTemplate` — likely a **data type →
  byte-exact**, already scaffolded/commented in the XmlCompiler), new geometry (the mesh **re-pack** path), and
  textures (true §4 frontier). **Discipline:** community mods are NOT ground truth (EA bytes / in-game remain the
  oracle); BYO/zero-EA holds — characterize the format, reimplement clean, ship **nothing** of theirs; credit the
  source. Each examined mod → a dated finding that promotes a type in COVERAGE. Design:
  **[docs/design/community-mods-as-frontier-reference.md](docs/design/community-mods-as-frontier-reference.md)**.

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
