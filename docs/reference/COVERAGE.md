# Coverage matrix

What the toolchain can compile and decompile today, and — type by type — **how faithful the output is to
the bytes Kane's Wrath actually ships**. The numbers here are measured, not asserted; every one is
reproducible with the harness described at the bottom.

> **⚠ Version caveat (finding [0016](../findings/0016-static-mod-stream-is-complete-replacement-not-overlay.md)).**
> "Byte-exact vs shipped" is only meaningful **relative to the patch version the engine actually loads** — a
> stream can match `Core/1.0` byte-for-byte and still mismatch the running **1.3** engine's per-type schema
> hashes (the `DefaultHotKeys` `0x692d0b3a`→`0x12cb83dc` drift that crashed the complete-probe). The numbers below
> are **not yet version-stamped**; the base they were measured against (the SDK `*_2` manifests) should be
> confirmed to be the running patch version (1.3 / the patch `Static_mod`), and each figure stamped with it.
> Until then, read "matches shipped" as "matches the sampled stream," not "matches what the 1.3 engine loads."

**Verification method / date.** Measured 2026-11-24 with the ground-truth gate
`tools/roundtrip.sh --from-binary <stream.manifest> --only <INSTANCE> --stringhashes <master/StringHashes.xml>`,
which decompiles a *shipped* linked stream, recompiles the decompiled XML, and byte-compares each asset to the
**original shipped bytes**, bucketed per type. Streams sampled: `static_common` (gameplay types) and
`global_common` / `global_english` (audio / LOD / environment types). A *master* `StringHashes.xml` (built from
an SDK compile) was supplied so module-id / `StringHash` fields resolve to names rather than hex.

Two senses of "correct" are kept distinct, because conflating them would overclaim:

- **Closed-loop (lossless):** our decompiler's XML recompiles to the *same bytes our compiler produced*. Proves
  the decompiler is a faithful inverse of the compiler. Run with `tools/roundtrip.sh <source.xml>`.
- **Ground-truth (byte-exact vs EA):** our output reproduces the bytes the **game itself ships**. This is the
  stronger claim and the one the matrix below reports.

## What is registered

The compiler registers **37 asset types** (the `foreach` in
`source/BinaryAssetBuilder.XmlCompiler/BinaryAssetBuilder/XmlCompiler/Plugin.cs`, `Initialize()`). Those 37 are
the authoritative supported set. The decompiler can additionally *name* and structurally walk more types than
that for inspection (it labels anything it can't fully model as `<RawAsset>`/`<UnknownModule>` rather than
crashing), but only the 37 below have full compile support, so only they can round-trip.

## Status by type (sample-verified against shipped bytes)

Headline: **of 37 registered types, 34 reproduce EA's shipped bytes byte-exact on the sampled instances**
(MultiplayerColor joined this set 2026-11-24 — see below), and **GameObject is now mostly byte-exact too**
(**40/50 = 80%** of a *widened* random sample) after closing its dominant draw-module value-diff; Environment is
structurally exact with a single residual value-diff that is a known-lossy reference (characterized below); 1 has
no instances in the sampled streams to measure here (Road). There is no longer a `RECOMPILE-MISSING` type.

### Byte-exact vs EA shipped bytes — sample-verified (34)

Each was confirmed with `--from-binary … --only <instance>` returning `BYTEEXACT`.

| Type | Stream sampled | Sampled instance(s) |
|------|----------------|---------------------|
| WeaponTemplate | static_common | AlienAnnihilatorEMPCannon |
| ArmorTemplate | static_common | AlienAssimilatorArmor |
| LocomotorTemplate | static_common | AlienBuzzerLocomotor |
| AttributeModifier | static_common | AttributeModifier_AdaptiveArmor |
| UpgradeTemplate | static_common | Upgrade_AdaptiveArmor |
| SpecialPowerTemplate | static_common | EMPBlast |
| ObjectCreationList | static_common | AlienAnnihilatorTripodDieOCL |
| FXList | static_common | FX_VoiceSuppressed |
| DamageFX | static_common | GenericStructureDamageFX |
| ExperienceLevelTemplate | static_common | AlienAnnihilatorTripodExperienceLevel_1, NODMilitantSquadExperienceLevel_1 |
| LogicCommand | static_common | Command_ActivateAdaptiveArmor |
| LogicCommandSet | static_common | AlienAssimilatorCommandSet |
| StanceTemplate | static_common | Generic |
| RadiusCursorLibrary | static_common | RadiusCursorLibrary |
| Weather | static_common | Weather |
| Mouse | static_common | StandardMouse |
| OnlineChatColors | static_common | OnlineChatColors |
| ConnectionLineManager | static_common | ConnectionLineManager |
| PhaseEffect | static_common | PhaseEffect |
| MultiplayerColor | static_common | ColorBlue, ColorRed, ColorOrange, ColorGold, ColorGreen, ColorPink, ColorPurple, ColorSkyBlue (8/8, whole type) |
| AmbientStream | global_common | AmbStream_BlueZone03_Pristine_5point1 |
| MusicTrack | global_common | 5_1_STARTSCREEN_MUSIC_360 |
| DialogEvent | global_common | BaseDialogEvent |
| LargeGroupAudioMap | global_common | Confessor_MoveLoop |
| StaticGameLOD | global_common | StaticLODHigh |
| DynamicGameLOD | global_common | DynamicLODHigh |
| GameLODPreset | global_common | High |
| CrowdResponse | global_common | NOD_Infantry |
| VideoEventList | global_common | 1_1 |
| AudioEvent | global_common | CIV_Mutant_CrowdAttack |
| Multisound | global_common | Music_Credits |
| MiscAudio | global_common | TheMiscAudio |
| AudioSettings | global_common | TheAudioSettings |
| AudioLOD | global_common | High |

> "Sample-verified" means specific instances were confirmed byte-exact against shipped bytes — not that every
> instance of the type is proven. It is strong positive evidence for the type's model, not a whole-corpus
> guarantee. Widening each type to its full instance set is ongoing.

### Structurally exact, residual value-diff (1)

Same serialized **size** as the shipped asset (the struct shape and field order are right), but some field
*values* differ — the model is structurally complete and the gap is localized.

| Type | Stream | Sampled | Bucket | First-diff offset | Note |
|------|--------|---------|--------|-------------------|------|
| Environment | static_common | Environment | SIZEOK_VALDIFF | 0x40 | One known-lossy weak reference — characterized below; model is complete. |

**Environment — characterized (2026-11-24).** The model is structurally *and* semantically complete; the single
residual byte is the `CloudEffect.LightningFX` field, a `TypedAssetId<FXList>` (schema `FXListWeakRef`) that in the
shipped data holds `FastHash("fx_lightningthunderstrike") = 0x9d865d76`. Its target FXList (`FX_LightningThunderStrike`)
is a *weak* reference that is **not defined anywhere in the SDK corpus** and **not present in the supplied master
`StringHashes.xml`**, so the decompiler cannot invert the one-way hash and emits the raw `0x9d865d76` placeholder,
which the compiler then re-hashes to a different value (first diff at 0x40). This is the *same known-lossy class* as
`StringHash` — not a model defect. **Proven:** adding the one name to the StringHashes reverse table makes
`Environment:Environment` recompile **BYTEEXACT**. Closing it for good is a StringHashes-coverage (data) task, not a
code change.

### GameObject — mostly byte-exact vs shipped bytes; residual fully characterized

GameObject was previously same-size-with-a-value-diff across the board. The dominant diff — a single shared
draw-module field (`W3DScriptedModelDrawModuleData.SetAnimsToLastFrameOnConstructionComplete`, schema default
`true`) written as `0` into former alignment padding — was closed earlier (one struct field + one marshal line),
fixing *every* object that embeds a scripted/tank draw module.

**Widened measurement (2026-11-24).** A reproducible random sample of **50** instances (seed 42) across
static_common is **40/50 = 80% BYTEEXACT**, **10 SIZEOK_VALDIFF, 0 SIZEDIFF, 0 missing**. All 10 value-diffs are
the **same, now fully-characterized class**: each is a set of isolated 4-byte dwords (relo/imp buffers byte-identical)
that are **module-id tags** — `ModuleData.id` `TypedAssetId`s such as `ModuleTag_CaptureSpecialPower` on
`<SpecialPower id="…">`, stored as `FastHash(tag.ToLower())`. The tag strings (mostly from shared includes like
`Includes/CaptureBehavior.xml`) are **absent from the supplied master `StringHashes.xml`**, so the decompiler emits a
`0x…` placeholder that the compiler re-hashes. Verified mechanically: for every differing dword, `new ==
FastHash("0x%08x" % ea)`. The diffs cluster on squads/infantry (RifleSoldier, Sniper, Fanatic, MilitantRocket,
Shadow, ImprovedCyborg) plus a couple of militant-rocket units. **Proven:** compiling a unit's source with `-scd`
captures its tags; feeding those into the StringHashes table makes `GameObject:GDIRifleSoldierSquad` recompile
**BYTEEXACT**. So the residual 20% is **StringHashes-coverage, not a model defect**. (A corpus-wide comprehensive
StringHashes would raise the measured rate but is blocked by a separate `-scd` compiler crash —
`KeyNotFoundException` during whole-tree StringHash finalization; noted, not chased.) Closed loop remains lossless.

### MultiplayerColor — fixed 2026-11-24 (was RECOMPILE-MISSING → now 8/8 BYTEEXACT)

Previously the decompiled XML would not recompile. First-diff method located the cause: the C# `MultiplayerColor`
struct was **missing a field**. The shipped 44-byte fixed struct is
`Base, MetaGameSide(AnsiString), RGBColor, RGBColorT, RGBNightColor, LivingWorldColor, LivingWorldBannerColor,
TooltipName(AnsiString), AvailableInMetaGame` — `MetaGameSide` (an `xs:attribute`, stored *inline* as an AnsiString
e.g. `"NOD"`/`"GDI"` right after Base) was absent, shifting every later field by 8 bytes so the generic walker read
`TooltipName` from the wrong offset and dropped the required `<TooltipName>` element (recompile then failed XSD
validation). Fix is type-local: one struct field + one marshal line (`MetaGameSide` marshaled before `TooltipName`
to match the shipped string-data order). **All 8 instances of the type** now recompile BYTEEXACT, both with
`MetaGameSide` present (ColorRed=NOD, ColorOrange=GDI) and absent.

### Registered but not measurable in the sampled streams (1)

| Type | Note |
|------|------|
| Road | Registered + modeled, but no `Road` instances appear in `static_common` / `global_*`, so it cannot be ground-truthed from these streams. Unmeasured here. |

## Art pipeline (Pillar 2) — W3DAnimation byte-exact (2026-11-24)

**`W3DAnimation` (TypeId `0x2448AE30`) round-trips byte-exact against shipped bytes, from the pristine
(un-widened) schema.** This is the first art-pipeline type to reach the data-type ground-truth bar. The earlier
result rested on an in-place schema widening (finding
[0013](../findings/0013-byo-schema-edited-in-place.md)); that was reverted and the binding re-established **in
OpenWrath's own code** (finding
[0014](../findings/0014-runtime-w3danimation-dispatch-depends-on-schema-stamped-typeid.md)), so the number below
is earned by the current, BYO-clean pipeline — not by any edit to a bring-your-own file.

- **Result.** `static_common` (`~/cnc-kw-godmod/ea-roundtrip/eastream/static_common.manifest`), **1792**
  `W3DAnimation` instances, all decompiling cleanly (`ok=1792, raw=0`). A reproducible random sample of **125**
  (seed 7) recompiles **125/125 BYTEEXACT** (`sizeok_valdiff=0, sizediff=0`). Codec coverage BYTEEXACT on
  `ABBHIVE_D2AN` (20 mixed time-coded + adaptive-delta channels), `ABBHIVEDR_CLS` (time-coded only),
  `ABBHIVEDR_OPN` (adaptive-delta only), and `ABGATEWAYFXDIE` (empty channel list). Measured with
  `tools/roundtrip.sh --from-binary` / `bab-decompile decompile-stream --type 0x2448ae30` + `compare-stream.py`.

- **Approach — runtime pass-through (lossless), not decompress→recompress.** In KW a `W3DAnimation` ships in
  its compiled runtime form `W3DAnimationRuntime`, whose per-bone channels are already time-coded or
  adaptive-delta **compressed** (lossy). The compressor dominates the corpus, so decompressing to raw frames and
  re-running the compressor cannot reproduce the shipped bytes. Instead the decompiler emits each channel in its
  **shipped compressed form** — `<Timecoded FrameAndBinaryFlag Values>` /
  `<Delta Scale Init NumBits CompressedValues>` — and the W3X compiler writes those straight into the
  `W3DAnimationRuntime` layout with no re-compression. The asset element stays `<W3DAnimation>` so the shipped
  TypeId `0x2448AE30` / TypeHash `0xCC069193` are reproduced exactly.

- **How the runtime channels bind WITHOUT editing the BYO schema (finding 0014).** EA's schema already defines
  the runtime channel types (`AnimationChannelTimecoded` / `AnimationChannelDelta`) but doesn't reach them from
  the authoring `W3DAnimation`'s `<Channels>` choice. OpenWrath adds that reach **in code**, before the schema
  compiles — `SchemaSet.BindRuntimeAnimationChannels()` adds `<Timecoded>`/`<Delta>` particles (→ EA's own
  types) to the `W3DAnimation` `<Channels>` choice in memory. The runtime channels then bind, so the whole
  normal pipeline works through them (validation, reference-handling, instance hashing, and the existing
  `TypeId` stamping that drives the marshaler's dispatch). No bring-your-own schema *file* is modified
  (invariant 1's "in code" clause). It is the **prototype** binding; it migrates into the schema-overlay
  registry when that exists (ROADMAP).

- **What was added / changed.** Core: `SchemaSet.BindRuntimeAnimationChannels` (the in-code binding). Decompiler:
  `W3DAnimationReader.cs` (+ `ValueRender.cs`; dispatch via `AssetDecompiler.PopulateRoot`;
  `decompile-stream --type` filter). Compiler: `Marshaler.W3DRuntime.cs` (runtime pass-through writer,
  reproducing EA's exact block/array allocation order) + a runtime-form branch in `W3XCompiler/Plugin.cs`. Shared
  single-source channel TypeIds in `SageBinaryData.AnimationChannelTypeIds`. **No schema file was modified.**

- **No data-type regression from the shared schema augmentation.** The binding only adds particles to the
  `W3DAnimation` type; closed-loop `Armor.xml` **207/207** and `Weapon.xml` **456/456** byte-exact confirm the
  data types are unaffected.

- **W3DMesh (stretch) — deferred.** Not attempted in this pass. The mesh pipeline packs authoring vertices into
  a runtime `W3DMeshVertexData` layout via `W3DMeshProcessor`, so it needs its own (heavier) runtime
  pass-through; left for a follow-up to avoid risking the verified `W3DAnimation` result.

## Not modeled (out of the 37)

Types the decompiler encounters in shipped streams but the compiler does **not** register — e.g.
`FXParticleSystemTemplate`, `Texture`, `W3DMesh`, `W3DContainer`, `W3DHierarchy`, `W3DCollisionBox`,
`AudioFile`, `PackedTextureImage`, `OnDemandTexture(Image)`, and the UI/button/AI-strategy
families. The decompiler labels these rather than crashing, but they cannot round-trip. The remaining art / W3D /
texture / audio-file families belong to the planned **content pipeline**, not the data toolchain; see
`../../ROADMAP.md`. (`W3DAnimation` has now left this list — see the art-pipeline section above.)

## Known decompiler (read-direction) limitations

- **`LogicCommand` instance data isn't recovered on read.** `openwrath inspect`/the decompiler desync on every
  `LogicCommand` instance (`len 24 past instance end (0)`) and fall back to a labeled `<RawAsset>` — the
  anti-crash desync guard works, but the fields aren't rendered. This is **read-direction only**: the
  compile/roundtrip `LogicCommand` row above (byte-exact on `Command_ActivateAdaptiveArmor`) is unaffected. See
  `../findings/0009-decompiler-logiccommand-instance-read-desync.md` for the H1/H2 discriminator and fix plan.

## Known compiler limitations

- ~~`xi:include` xpointer is not honored~~ — **FIXED 2026-11-21** (`../findings/0008-xinclude-xpointer-not-honored.md`).
  The custom `ResolveXIncludes` now splices only the xpointer-selected node-set; units whose `<Behaviors>` use
  xpointer includes (e.g. `GDICommando`) compile and round-trip byte-exact. Add an xpointer-using unit to the
  corpus to keep it from regressing.

## Closed-loop corpus sweep (self-consistency)

Separately from the ground-truth gate, `tools/corpus-roundtrip.sh` runs the **closed-loop** check
(compile → decompile → recompile → compare) across many SDK source files and aggregates a per-type matrix via
`tools/coverage-report.py`. That measures the decompiler-is-inverse-of-compiler property, not fidelity to
shipped bytes — useful, but weaker than the `--from-binary` numbers above. Regenerate it after decompiler
changes; treat it as a self-consistency monitor, not a whole-game coverage claim.

---

_This file is a measurement, not a promise. Re-run the harness after changes and update the date, sampled
instances, and buckets to match._
