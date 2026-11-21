# Coverage matrix

What the toolchain can compile and decompile today, and — type by type — **how faithful the output is to
the bytes Kane's Wrath actually ships**. The numbers here are measured, not asserted; every one is
reproducible with the harness described at the bottom.

**Verification method / date.** Measured 2026-11-20 with the ground-truth gate
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

Headline: **of 37 registered types, 33 reproduce EA's shipped bytes byte-exact on the sampled instances**, and
**GameObject is now mostly byte-exact too** (~79% of a random sample) after closing its dominant draw-module
value-diff; Environment is structurally exact with a residual value-diff; 1 has a compile gap; 1 has no instances
in the sampled streams to measure here.

### Byte-exact vs EA shipped bytes — sample-verified (33)

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
| Environment | static_common | Environment | SIZEOK_VALDIFF | 0x40 | One unresolved cross-stream reference. |

### GameObject — now mostly byte-exact vs shipped bytes

GameObject was previously same-size-with-a-value-diff across the board. The dominant diff was a single shared
draw-module field (`W3DScriptedModelDrawModuleData.SetAnimsToLastFrameOnConstructionComplete`, schema default
`true`) that the compiler was writing as `0` into former alignment padding; modeling it (one struct field + one
marshal line) closed it for *every* object that embeds a scripted/tank draw module. Post-fix, a 14-instance random
sample across static_common is **11/14 (~79%) BYTEEXACT** — including all three MARV variants, the construction
yards, GDIAAScout, NODAttackBike, AlienEradicatorHexapod, GDIMedicalBay. The residual ~21% carry a separate,
smaller class of 4-byte hash/reference value-diffs (unresolved StringHash or source drift), tracked next. Closed
loop remains lossless.

### Registered but with an open compile gap (1)

| Type | Stream | Sampled | Bucket | Note |
|------|--------|---------|--------|------|
| MultiplayerColor | static_common | ColorBlue | RECOMPILE-MISSING | Decompiles, but the decompiled XML does not yet recompile (no asset emitted on the recompile pass). Modeling gap to close. |

### Registered but not measurable in the sampled streams (1)

| Type | Note |
|------|------|
| Road | Registered + modeled, but no `Road` instances appear in `static_common` / `global_*`, so it cannot be ground-truthed from these streams. Unmeasured here. |

## Not modeled (out of the 37)

Types the decompiler encounters in shipped streams but the compiler does **not** register — e.g.
`FXParticleSystemTemplate`, `Texture`, `W3DMesh`, `W3DContainer`, `W3DHierarchy`, `W3DCollisionBox`,
`W3DAnimation`, `AudioFile`, `PackedTextureImage`, `OnDemandTexture(Image)`, and the UI/button/AI-strategy
families. The decompiler labels these rather than crashing, but they cannot round-trip. The art / W3D / texture
/ audio-file families belong to the planned **content pipeline**, not the data toolchain; see `../../ROADMAP.md`.

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
