# 0011 — SOLVED: a hitscan unit CAN launch a projectile; the gate was stream load-ORDER, not engine coupling

**Status:** ✅ **SOLVED & verified in-game (2026-11-26)** — data-fixable; mechanism proven by a 5-build in-game matrix.
Opened 2026-11-21. (§4 frontier — "does it launch" is in-game-only; this is now settled by direct observation.)

> ## THE FINDING (do not re-derive — supersedes every "engine coupling / impossible" conclusion below)
> A `ProjectileNugget` resolves its **`ProjectileTemplate`** (the object to spawn) and its **`WarheadTemplate`** (what
> detonates on impact) by **forward lookup during the engine's single sequential stream-load pass.** Each binding
> succeeds **only if that template appears *before* the referencing weapon in the compiled stream's manifest order**;
> a template ordered *after* the weapon binds to **null, silently** — the weapon fires its FX and any weapon-local
> nuggets (e.g. `DamageNugget`) but the forward-referenced piece does nothing. The two bindings are **independent**:
>
> | ProjectileTemplate order | WarheadTemplate order | in-game result |
> |---|---|---|
> | after weapon | after weapon | nothing launches (every T0–T20 "failure") |
> | after | before | nothing launches |
> | **before** | after | projectile **spawns & flies**, but **no detonation / no damage** (dud) |
> | **before** | **before** | **spawns + flies + detonates + damage** — a real projectile from a hitscan unit |
>
> **Projectile-order controls the spawn; warhead-order controls the detonation.** Proven on **both** the GDI Commando
> (tracer-draw family) *and* the NOD Avatar (laser-nugget family) → the rule is **unit-agnostic**. It was **never**
> about "hitscan hardpoints," bones, draws, KindOf, modules, or any GameObject field — those were all red herrings
> (see the long trail below for how the investigation was fooled). **The fix is pure data/stream-order**, applied with
> `modkit/lib/reorder_stream.py` (moves a `ProjectileNugget`'s projectile + warhead ahead of the weapon in the linked
> stream, permuting `.bin/.relo/.imp` in lockstep — relo/imp are asset-local so this is safe; then `retag_checksum.py`).
>
> **Why the earlier "engine coupling, data-unfixable" conclusion was wrong (honest post-mortem):** the free-oracle
> GameObject differential correctly found *no distinguishing GameObject field* — because the gate isn't in the
> GameObject at all, it's in the **stream position of the referenced weapon/projectile assets**. The "order is
> irrelevant" claim rested on noting a working launcher references its projectile 1,377 entries away — but I compared
> *distance*, not **direction**: the missile soldier's projectile is 1,377 entries *earlier* (backward ref, fine); the
> commando's was *later* (forward ref, null). Direction was everything. The first reorder attempt crashed only because
> it moved manifest entries without moving the parallel `.bin/.relo/.imp` data blocks (cumulative-offset desync); the
> lockstep reorder loads and launches. Full evidence + the A1/A2/C1 probe matrix: `0011-hitscan-launch-test-registry.md`.
>
> **Project-wide implication:** ANY mod that puts a `ProjectileNugget` on a weapon whose projectile/warhead happen to
> sit later in the stream will silently fail to launch. The overlay/compiler toolchain should ensure a nugget's
> referenced templates are emitted before the weapon (candidate `openwrath` auto-ordering pass — see ROADMAP).
>
> **It's statically detectable (reference-graph proof).** The manifest's AssetReference buffer records every
> reference as (TypeId, InstanceId); comparing the target's stream index to the referrer's flags **forward edges**.
> A whole-stream scan found **only 14 forward edges out of 73,928 references (0.02%)** — EA's compiler emits an
> essentially **topological (dependencies-first) order**. Of those 14: **10 are EA's own and every one is
> `Mesh/Object → Texture`** (textures bind through an order-*independent* managed store → benign; EA ships them and the
> game works), and the **4 fatal ones were exactly our mod edits** (`GDICommandoRailCarbine` + `NODAvatarLaser` →
> their warhead + projectile). So there are (≥2) resolution regimes: **order-independent** (textures) and
> **order-dependent/eager-pointer-at-load** (a weapon's projectile/warhead) — only the latter cares about order.
> **Tools:** `modkit/lib/check_forward_refs.py` lints a built stream (FATAL = `WeaponTemplate → GameObject/WeaponTemplate`
> forward; BENIGN = `→ Texture`; exit 1 on any FATAL — gate a build with it); `modkit/lib/reorder_stream.py` fixes it.
> Verified: lint shows 4 FATAL on the base-order stream, **0 FATAL after the reorder**.

<details><summary>⚠️ Historical trail below (2026-11-21 → T20) — how the investigation was fooled. Conclusions here are SUPERSEDED by the finding above; kept for the record.</summary>

**Superseded bottom line (was stated 2026-11-26, now REFUTED):** "a hitscan hardpoint cannot be made to launch a
`ProjectileNugget` through any data edit … genuine engine coupling … use the `WeaponOCLNugget` escape hatch." This was
wrong — the gate was stream load-order, fixable in data (above). The `WeaponOCLNugget` escape hatch still works as an
*alternative* but is no longer necessary.

> ⚠ **This narrative lags the live ledger.** The current truth is
> **`0011-hitscan-launch-test-registry.md`** — read it first. The sections below are kept as the dated trail of how
> the investigation evolved; several of their *conclusions have since been refuted* and are flagged inline. In
> particular, the original 2026-11-21 framing ("projectile delivery is a **modeled hardpoint property, not data**")
> was **refuted** (the bare-launch-bone theory fell to the Predator; the whole art/model side was then eliminated in
> **both** directions by T5 and T12). Treat this file as history, not as the standing conclusion.

> A **data-authoring behaviour** finding: what actually happens when you try to give a hitscan unit
> (sniper, laser) a projectile weapon. The robust, repeatedly-reproduced observation is: **the weapon fires (muzzle
> FX + sound), damage-nuggets apply, but a `ProjectileNugget` instantiates nothing** — no projectile, no impact. The
> *why* is still open. This is behaviour observed in-game; it is **not** an engine teardown, and the mechanism is
> explicitly unproven.

## Context

A very common mod wish: take a hitscan unit and make it fire a real projectile — give the GDI Commando (rail
carbine, a hitscan sniper weapon) GDI Juggernaut shells or rockets; give the NOD Avatar (laser arm) a rocket.
In every case the result is the same and baffling at first: **the weapon fires (muzzle FX + sound play), but no
projectile is ever launched** — no projectile, no impact, no damage.

## Finding (robust) + original hypothesis (REFUTED)

**Robust, repeatedly reproduced:** put a `ProjectileNugget` on a hitscan unit (commando carbine, Avatar laser) and
**no projectile is ever launched** — the weapon fires its FX, instant `DamageNugget`/`SuppressionNugget` apply, but
the projectile object never spawns (T4: damage dealt + FX play, zero projectile → a *projectile-spawn* gate).

> ⚠ **REFUTED original hypothesis (2026-11-21):** *"the hardpoint's type is a property of the **model**, not the
> data; you need a separate projectile hardpoint (an art change)."* This has since been **disproven**:
> - The "launch bone must be bare / a mesh-bearing bone can't launch" refinement fell to the **GDI Predator** (it
>   launches its shell from `FXMUZZLEFLASH`, a 93-vertex mesh bone).
> - The whole **art/model/bone side was then eliminated in both directions**: a missile soldier wearing the
>   commando's entire draw still launches (**T5**), and the commando wearing the missile soldier's draw still won't
>   (**T12**). So "needs an art change" is wrong — swapping art changes nothing either way.
>
> The gate therefore travels with the unit's **data**, not its model — see the ledger's current localization and the
> **2026-11-26 free-oracle GameObject differential** below, which finds *no* surviving distinguishing data property
> and reopens genuine engine coupling as a live possibility.

What *does* still work from a hitscan unit (unchanged, still true): **weapon-level, instant nuggets** — a direct
`DamageNugget` and a `SuppressionNugget` both apply. It is specifically the launched projectile that never happens.

## Evidence

Reproduced on the GDI Commando (and earlier on the NOD Avatar). We eliminated every data-side cause by
*measuring*, one variable at a time, in-game:

| Hypothesis | Verdict | How |
|---|---|---|
| the weapon / weapon type | ❌ | the *same* rocket works on `GDIMissileSoldier`, fails on the commando → it's the unit |
| armor | ❌ | `GDIEngineerArmor` takes 25% from CANNON (read from `Armor.xml`), not 0 |
| damage radius / type | ❌ | radius-400 direct hit, zero damage **and no impact** |
| the `TracerModelDraw` (beam draw) | ❌ | removed via `xai:joinAction="Remove"`, no change |
| the `SNIPER` KindOf flag | ❌ | removed, no change |
| multi-weapon hardpoint | ❌ | collapsed to one weapon, no change |
| firing modules (AIUpdate / WeaponSetUpdate) | ❌ | identical to the working `GDIMissileSoldier` |
| our own (lossy) GameObject override | ❌ | weapon-only override onto the *stock* unit — still no projectile |
| ~~the hardpoint is a hitscan hardpoint (model)~~ | ⚠ **REFUTED** | was marked ✅ by elimination in 2026-11-21; later **disproven** — Predator launches from a mesh bone, and T5/T12 eliminated the art side in both directions. The gate is **not** a model property. |

**The decisive observation (user):** with a projectile weapon on the commando, his shots *land on the scattered
points a rocket would* — so the weapon's targeting data is read — but delivery is an instant hitscan hit, never
a launched projectile. **The weapon decides *where*; the hardpoint decides *how*, and a hitscan hardpoint's "how"
is fixed to instant.**

**Proof by existence — the Nod Redeemer (`NODMetaUnit`).** It mounts **both** hitscan lasers
(`NODWarmechTriPointLaser1/2/3`) **and** projectile rockets (`NODWarmechRocket`) — but on **separate hardpoints**:
the rockets fire from dedicated rocket-pod turrets (`B_RocketPodturretR` / `B_RocketPodturretL`), the lasers from
their own hitscan hardpoints. The unit carries ~13 weapon slots, each firing from its own modeled turret bone.
You **cannot** make the Redeemer's laser fire its rockets; the rockets exist because the model was *built* with
rocket-pod hardpoints. Exactly mirrors the commando, which has a single hardpoint — his rifle — and it's hitscan.

## The escape hatch (pure data, no art)

Because **weapon-level nuggets DO apply** from a hitscan unit, a `WeaponOCLNugget` can **spawn a self-detonating
shell at the target** (an independent object with its own projectile + warhead), bypassing the hardpoint entirely.
That gets a real, damaging, visible projectile from a hitscan unit without touching its model. Caveats: the OCL
tends to spawn at the *firer* for object targets / at the *position* for ground targets (works best on
attack-ground); and a *new* OCL can't be inserted into a schema-drifted stream like Second Isomer's
(finding [0010](0010-insert-must-match-target-stream-type-schema-hash.md)), so you must reuse an existing
self-detonating-shell OCL.

## How to apply

- **To arm a hitscan unit with damage:** use weapon-level nuggets (`DamageNugget` for instant AoE,
  `SuppressionNugget` for the crouch). Reliable. You can keep a flying-shell `ProjectileNugget` purely for looks —
  it won't launch, but the weapon still fires its FX.
- **For a real launched projectile from a hitscan unit:** either (a) the content pipeline — add a projectile
  hardpoint (turret/launch bone) to the model, like the Redeemer's rocket pods; or (b) the `WeaponOCLNugget` /
  independent-spawn escape hatch above.
- **When planning a mod:** treat "hitscan primary" as "weapon-level damage or a separate projectile hardpoint" —
  never "just put a projectile weapon on the existing slot."

## Methodology notes (hard-won; they nearly cost us the diagnosis)

- **Test against the *stream* unit, not the SDK.** The in-game commando is Second Isomer's heavily-modified unit
  (SNIPER/tracer/voice stripped), not the retail SDK commando we were reading. Our GameObject override
  `inheritFrom`'d the SDK (retail) commando — so our *override* was retail-based and valid to analyse — but the
  *stock* SI unit differs. Always confirm which one you're actually running.
- **`mod bake` accumulates.** Removing an override from the mod source does **not** restore the stock asset — the
  stream keeps the last baked version. To test a truly stock unit, `mod revert` first, then bake only the change.
- **Our decompiler can't read SI-compiled GameObjects** — `inspect GDICommando` desyncs to a `<RawAsset>`
  (`struct GameObject@0 ... past instance end (0)`), the same read-direction gap as
  [0009](0009-decompiler-logiccommand-instance-read-desync.md)/[0010](0010-insert-must-match-target-stream-type-schema-hash.md).
  So `inspect` couldn't show SI's actual commando; we worked from the retail SDK + in-game behaviour instead.
- **Our GameObject override may drop voice/audio refs** — the commando lost his voice lines under our override
  (and SI's stock commando also lacks them). Worth confirming whether our GameObject compile preserves audio
  references; if not, it affects every GameObject-override mod.

## Why it's wired this way — HYPOTHESIS (not confirmed)

Everything above is measured. **This section is not** — it's our best reasoning about the *mechanism* and the
*design intent*, to be tested once an art toolchain can read the model. Treat it as a documented guess, not fact.

**Which model property decides delivery (open).** Proven to be a model/art property rather than data — but we
have **not** isolated *which*: a bone *role* (a "muzzle" bone vs a "launcher" bone), a weapon-fire *event* on the
fire animation clip, or the draw's weapon-fire handling. One data point argues *against* "it's just the bone":
the commando already has a `WeaponLaunchBone` (`B_WEAPONA_FX`) and still launches nothing — which points more at
an **animation launch-event** (his sniper "fire" clip has none; the missile soldier's clip plays a "launch")
than at the mere presence of a bone. Unresolved until the model's bones + animation events can be read.

**Why an engine might couple delivery to the art at all (speculation).** It reads like inflexible design from a
modder's seat, but there are sound reasons for a *shipping-game* engine:

1. **Audiovisual sync.** If the projectile leaves on a specific animation *frame*, the muzzle flash, recoil,
   sound and projectile all line up with the firing pose. Decoupling would let shots visibly desync.
2. **Two real code paths.** Hitscan (instant raycast + damage) and projectile (spawn an entity, simulate flight,
   collide, detonate) are different implementations; routing between them per hardpoint, in the content, is
   reasonable.
3. **Co-authored content.** A SAGE "unit" is model + animation + data designed together as one bundle.
   Orthogonal, freely-swappable layers (data = behaviour, art = visuals) is a *modding-framework* value EA had
   no reason to pay for — nobody on the team was going to bolt a rocket onto a sniper.
4. **Legacy accretion.** SAGE descends from Generals/BFME; the hitscan/sniper path was likely a special case
   grafted on over years, not a clean-slate decision.

**Our read (also hypothesis):** not incompetence — engineering optimised for shipping tightly-synced, performant,
co-authored units, which is incidentally hostile to mix-and-match modding. A modding-first engine would make
weapon delivery fully data-driven and launchable from any bone; SAGE isn't that, and few commercial engines of
its era were. We can't change the coupling — but the *knowledge* of it (this finding) is the part worth owning.

## UPDATE 2026-11-25 — byte-exact re-investigation with the new W3D tooling (retail, clean)

Re-ran the whole investigation on **retail** (no SI confound) using this session's byte-exact W3D decompile
(`W3DHierarchy`/`W3DContainer`/`W3DMesh`/`W3DAnimation`) — the art-read capability 0011 said it was waiting for.
Candidates checked and **eliminated**:

- **GameObject data:** the commando's draw wires `WeaponLaunchBone="B_WEAPONA_FX"` on the PRIMARY slot — *same
  wiring as `GDIMissileSoldier`*. Not the difference.
- **`UseWeaponTiming`:** the commando's fire-state animations have it `false`, the missile soldier's `true`.
  Flipped it to `true` in-game → the commando *animated/timed* like a missile squad but **still launched nothing**.
  So `UseWeaponTiming` is visual-sync only — **not** the launch gate.
- **The launch bone:** `B_WEAPONA_FX` is a **real pivot** in `GU_CMMNDO_SKL` (`<Pivot Name="B_WEAPONA_FX">`) with
  the carbine mesh bound to it (`GU_CMMNDO_SKN.B_WEAPONA_FX`, BoneIndex 21). The bone **exists** — "missing bone"
  is out.
- **An animation fire-event:** both `GU_CMMNDO_ATKA` and `GUMISSLMN_ATKA` are **pure bone-transform channels**
  (Orientation/XTranslation); there is **no weapon-fire event channel** in the W3DAnimation to be missing.
- **The weapon nugget — the canonical hitscan/projectile signal:** `GDICommandoRailCarbine` has a `DamageNugget`
  (instant); `GDIMissileSoldierMissileLauncher` has a `ProjectileNugget ProjectileTemplate=…` (spawns a missile).
  This is DATA, not engine identity — so the earlier "the engine hardwires the commando" framing is wrong (a
  data-driven engine responds to data, not unit id).

**The decisive clean test (retail, pure `ProjectileNugget`, no `DamageNugget`, no `inheritFrom` merge):** the
commando's firing *behavior changed* (single-shot, straight aim = projectile-weapon timing — so the override took
effect) **but it still spawned NO projectile and dealt NO damage** (consistent: a `ProjectileNugget`'s warhead only
applies on projectile impact). 

**→ Conclusion (refines 0011, vindicates its instinct):** the weapon nugget is **necessary but NOT sufficient**.
A pure projectile weapon genuinely does not launch from the commando even on clean retail. So there IS a
**unit/model-specific** factor beyond the weapon and beyond the bone's mere existence — exactly 0011's original
"it's the unit/model" call, now with the simpler explanations (data wiring, `UseWeaponTiming`, missing bone,
animation event) all ruled out. **Leading remaining hypothesis: the weapon mesh/hardpoint at `B_WEAPONA_FX`** (how
the carbine mesh/bone is set up as a launch point) — the next test is to swap the commando's `B_WEAPONA_FX`
mesh/hardpoint for the missile soldier's (now doable with the W3D tooling). What byte-inspection *cannot* settle
is a genuine engine-binary coupling that keys on the model's launch-point setup; that would need the mesh/hardpoint
swap (if it then launches → model property, fixable) or disassembly (out of scope).

*(Aside, unrelated: with this test mod + the community 4K add-on active, the main-menu logo renders **magenta** —
the 4K add-on ships a replacement logo image that isn't loading; a missing/!uncovered texture on the 4K pack's
side, not confirmed isolated from the static overlay. Noted for the texture pillar.)*

## UPDATE 2026-11-25 (follow-up) — three more eliminations via *free oracles*, and a model-property HYPOTHESIS (later REFUTED)

> ⚠ The "bare launch bone" model-property hypothesis proposed in this section was **refuted** the same day by the
> Predator cross-check (see the later UPDATE). The three *eliminations* here (WeaponCategory, WeaponSlotID,
> launch-bone transform) still stand; the proposed *mechanism* does not.

Continuing the ladder without spending an in-game cycle. **Everything in this section is settled by a free oracle
— shipped-data pattern or byte-exact W3D decompile — not in-game.** The remaining *in-game* confirmation test is
pre-registered at the end; it has **not** been run yet.

### Eliminated — `WeaponCategory` (shipped-data oracle)
The commando is `WeaponCategory="GUN"`; the missile soldier is `WeaponCategory="MISSILE"`. Tempting as a
delivery-routing gate — and never checked before. **Refuted from shipped data:** the **AlienSeekerTank** (Scrin
Seeker) is `WeaponCategory="GUN"` *and* its PRIMARY weapon `AlienSeekerTankPlasmaDiskLauncher` is a
`ProjectileNugget` launching `AlienPlasmaDisk` — a visibly-launched projectile on retail. A GUN unit launches
projectiles → `WeaponCategory` does **not** gate delivery. (Also `Reaper17ShardWalker`, GUN + shard projectiles.)
*No fix was shipped on this wrong lead precisely because the free oracle caught it first.*

### Eliminated — `WeaponSlotID` on the launch bone (shipped-data oracle)
The missile soldier's `<WeaponLaunchBone>` carries `WeaponSlotID="1"`; the commando's omits it. **Refuted:**
`GDIGrenadeSoldier` and `NODMilitantRocket` both **launch** projectiles with **no** `WeaponSlotID` on their PRIMARY
launch bone — same omission as the commando. So the missing `WeaponSlotID` does not block launch. (Consistent with
the observation that the commando's muzzle *FX* bone, also lacking `WeaponSlotID`, resolves fine — FX plays.)

### Eliminated — launch-bone *transform* (byte-exact W3D decompile; this was ladder step 3)
Decompiled `GU_CMMNDO_SKL` and `GUMISSLEMAN_SKL` from the clean EA stream. The commando's `B_WEAPONA_FX` pivot is
**byte-identical** to the missile soldier's: `Translation (3.974354, -5.88113, 6.590147)`, `Rotation (0,0,0,1)`,
same `FixupMatrix`. (These GDI-infantry skeletons share a common pivot base — early pivots match byte-for-byte.)
The launch point is **not** degenerate and **not** at the origin — a projectile would spawn at the *exact same
external point* the missile soldier launches from successfully. "Projectile spawns inside the unit" is out.

### A candidate model property (ladder step 2) — a 4/4 shipped-data pattern that was later REFUTED

> ⚠ **Refuted.** The "launch bone must be bare" correlation below (4/4) was broken by the **GDI Predator**, which
> launches from a 93-vertex *mesh* bone (`FXMUZZLEFLASH`). Kept as a cautionary example of a strong correlation that
> was not the cause — exactly why the free-oracle cross-check is run before spending an in-game cycle.
Decompiled the W3DContainers (bone→mesh bindings). The decisive asymmetry:

| Unit | Launches? | PRIMARY launch bone | Mesh bound **to the launch bone**? |
|---|---|---|---|
| GDIMissileSoldier | ✅ | `B_WEAPONA_FX` (bare) | ❌ — missile mesh is on a *separate* bone `MISSLE` (idx 24) |
| NODMilitantRocket | ✅ | `B_WEAPONA_FX` (bare) | ❌ — whole body is one mesh at bone 0 |
| AlienSeekerTank (GUN!) | ✅ | `MUZZLEFX` (idx 5, bare) | ❌ — gun/shard mesh is on a *separate* bone `TURRET` (idx 3) |
| **GDICommando** | ❌ | `B_WEAPONA_FX` (idx 21) | ✅ — **the carbine mesh `GU_CMMNDO_SKN.B_WEAPONA_FX` is bound to the launch bone itself** |

**Every launcher sampled (infantry + vehicle, GUN + MISSILE) launches from a *bare* FX/muzzle bone, with the
weapon's visible mesh on a *different* bone. The commando is the sole outlier: its launch bone *is* the weapon-mesh
bone.** This is the model property 0011 said existed but couldn't name — not the bone's existence (it exists), not
its transform (byte-identical), but **whether the launch bone is a bare FX point vs. a mesh-bearing sub-object bone.**

**Leading hypothesis (NOT yet confirmed in-game):** a projectile launches only from a *bare* launch bone; a bone
carrying a render sub-object is treated as a prop/geometry bone, not a valid launch point — muzzle FX still plays
(FX resolution is more lenient), but no projectile spawns. This vindicates 0011's "modeled hardpoint" core and
finally specifies it; it also predicts a **data-only fix** (no new art): re-point the launch bone to a bare bone.

> ⚠ Discipline note: this is a **strong correlation (4/4) + an inferred mechanism**, not proof. It could be a
> coincidental correlate of the true gate. It is settled *only* by the in-game test below.

### Pre-registered in-game confirmation test (ladder step 2 — decisive, data-only)
The commando skeleton has a **bare prop bone `PROPS0` (bone 20)** adjacent to the mesh-bearing `B_WEAPONA_FX`
(bone 21). Keep the pure `ProjectileNugget` carbine; override the draw to re-point the PRIMARY `<WeaponLaunchBone>`
from `B_WEAPONA_FX` → `PROPS0` (leave the muzzle-FX bone on `B_WEAPONA_FX` so the flash stays at the gun).
- **Projectile launches** → hypothesis **confirmed**: launch requires a bare bone; the carbine-on-the-launch-bone
  was the gate. **Data-only fixable** (re-point to a bare bone, or add a dedicated bare FX child bone). 0011's
  "needs an art change" softens to "needs a bare launch bone," often achievable in data.
- **Still nothing** → hypothesis refuted; escalate to the whole-model swap (ladder step 1) and, if that too fails
  with art matched, genuine engine coupling (ladder step 6).

## UPDATE 2026-11-25 (Avatar cross-check) — an independent hitscan unit that *complicates* the bare-bone theory

User flagged a second long-standing failure: the **NOD Avatar's right-arm beam** also never launched a projectile.
Investigated via free oracles (no in-game cycle). Facts (byte/data-verified):

- The right-arm beam = `NODAvatarLaser` (hardpoint 1 PRIMARY): **hitscan** — `WeaponSpeed="999999"`,
  `ActivateLaserNugget` + `DamageNugget`, `WeaponCategory="CANNON"`. (The *left* arm is the non-firing commandeer
  claw — not a launch bone; correct, it's absent from the draw's launch list.)
- It launches from **`B_CLAWHANDR` (bone 28)**, which is **BARE** — the arm is part of the skinned `AVATAR_TOP`
  mesh (bone 0); **no mesh sub-object is bound to the launch bone.** (Contrast the commando, whose carbine *is* a
  sub-object on its launch bone.)
- The Avatar's *working* projectile weapon, the **flamer** (`NODAvatarFlamer`, a `ProjectileNugget`), launches from
  **`FT_Turret` (bone 56) = BARE.** Its beam-cannon upgrade (`NODAvatarBeamCannonLaser`, hitscan) launches from
  **`NUBEAM` (bone 52) = has a mesh sub-object.**

**Why this complicates the bare-bone theory:** the Avatar's non-launching beam arm launches from a **bare** bone —
which the leading theory predicts *should* be able to launch. **BUT** the prior failure is **confounded**: the stock
laser is `WeaponSpeed="999999"` (and carries an `ActivateLaserNugget`); a nugget-swap that kept either would deliver
instantly/invisibly, i.e. *not a clean "won't launch."* So the Avatar is **not yet a clean data point** — it is a
potential counterexample *or* a confound.

**This makes the Avatar a decisive parallel experiment, now built into the same overlay** (clean beam-arm weapon:
pure `ProjectileNugget`, finite `WeaponSpeed`, no `ActivateLaserNugget`/`DamageNugget`; launch bone left on the bare
`B_CLAWHANDR`; Avatar + prereq instant/free — NOD skirmish). Pre-registered outcomes, read together with the
commando `PROPS0` test:

- **Avatar beam arm (bare) LAUNCHES** → a bare launch bone *is* sufficient on an independent unit → the bare-bone
  theory holds and the commando's failure is specifically the **mesh on its launch bone** (expect `PROPS0` to launch too).
- **Avatar beam arm (bare) still NOTHING** (clean weapon) → bare-bone theory **refuted**: a deeper gate common to
  hitscan hardpoints exists, and the commando `PROPS0` test should also fail. Next: whole-model swap / module-strip.

Net: the Avatar *lowers* confidence that "bare launch bone" is the whole story and raises the prior that there's a
shared hitscan-hardpoint gate — exactly why the two clean in-game tests are now the deciders.

## UPDATE 2026-11-25 (Predator cross-check) — the bare-bone theory is REFUTED; the tracer-draw is the new lead

User suggested the **GDI Predator**: it flips **projectile → hitscan** via the Armory railgun upgrade — a within-unit,
within-model, within-bone control. Investigated via free oracles. Facts (byte/data-verified):

- One `WeaponSlotTurret ID="1"`, one launch bone `FXMUZZLEFLASH`. Base `GDIPredatorTankCannon` =
  **ProjectileNugget** (`FXTankShell02`); upgrade `GDIPredatorTankRailgun` = **DamageNugget** (instant). The
  railgun upgrade only **shows a sub-object (`UGRAIL_01`)** + sets `WEAPON_UPGRADED_01` (swaps the weapon) + a
  sound — it does **not** move the launch bone. So on **one shared bone**, nugget type alone flips projectile↔hitscan.
- **`FXMUZZLEFLASH` (bone 5) has a mesh sub-object bound to it** (`SubObjectID="FXMUZZLEFLASH"`, **93 vertices** —
  the *same* vertex count class as the commando's carbine, also 93). **And the base Predator launches its shell from
  that bone.**

**→ The "launch bone must be bare" theory is REFUTED (both variants).** A launch bone carrying a 93-vertex mesh
sub-object launches projectiles fine; neither "any sub-object blocks" nor "substantial geometry → self-collision"
survives. The commando's carbine-on-the-launch-bone is **not** the gate. *(This is exactly why the free-oracle
cross-checks matter: the theory was killed from shipped data before an in-game cycle was spent on it.)*

**New lead — the one feature unique to the commando.** Surveying launchers (Predator, missile soldier, militant
rocket, seeker, Mammoth) vs the commando: the commando is the **only** one carrying a **`TracerModelDraw`** (the
sniper-beam render) bound to its **PRIMARY firing slot** (all launchers = 0; even the Predator's *own* hitscan
railgun renders its beam via `FireFX`+`LaserNugget`, **not** a TracerModelDraw). 0011's original "removed the tracer,
no change" was on the SI-confounded unit and was never cleanly re-tested on retail.

**New leading hypothesis:** "hitscan hardpoint" is encoded in the **draw** — a `TracerModelDraw` bound to a weapon
slot marks it as a beam/instant slot, and the engine declines to spawn the projectile even with a `ProjectileNugget`.
Mechanistically this is *not obvious* (a TracerModelDraw is a client render module; delivery is logic-side) — so
treat it as a correlate-to-test, not a conclusion. **Installed commando test switched accordingly** (replacing the
now-low-value `PROPS0` bare-bone test): pure `ProjectileNugget` carbine + **both PRIMARY `TracerModelDraw`s removed**
(`xai:joinAction="Remove"`), launch bone left at the stock `B_WEAPONA_FX` to isolate the tracer variable.
- **launches** → the TracerModelDraw was the gate; "hitscan hardpoint" is a *draw* property, removable in data.
- **still nothing** → the tracer isn't it either; escalate to the whole-model swap / module-strip; genuine
  engine-coupling gains weight. (The Avatar clean test — beam rendered via a now-removed `ActivateLaserNugget` —
  is a useful parallel: if the beam-render *is* the gate, the Avatar should launch.)

(The **GDI Mammoth** uses the identical railgun-upgrade pattern and corroborates the Predator; not separately tested.)

## UPDATE 2026-11-26 — tracer-draw REFUTED (T2); art eliminated both ways (T5/T12); free-oracle GameObject differential = no distinguishing data

This section fast-forwards the narrative to the live ledger. See `0011-hitscan-launch-test-registry.md` for the full
in-game test ledger (T0–T17c) and its provenance notes; the highlights that change the picture:

- **T2 (in-game):** removing both PRIMARY `TracerModelDraw`s + a pure `ProjectileNugget` → **still no launch.** The
  tracer-draw lead from the Predator cross-check is **refuted** — the tracer was only the fire *visual*.
- **T5 / T12 (in-game):** the entire art side is eliminated in **both** directions — a missile soldier wearing the
  commando's whole draw still launches (T5); the commando wearing the missile soldier's whole draw still won't (T12).
  The gate travels with the **unit data**, not the model. (T13b further shows it is **not** the `GDICommando` *id* —
  commando data under the `GDIEngineer` id still won't launch; the engine is data-driven.)
- **T4 (in-game):** `DamageNugget` + `ProjectileNugget` on the commando → damage applied + FX play, but **no
  projectile**. So the fire event completes and nuggets execute; the gate is specifically **projectile
  instantiation**.

### Free-oracle GameObject differential (clean retail `static_common`, 2026-11-26)
With the decompiler now reading retail `GameObject` instances cleanly (COVERAGE: GameObject mostly byte-exact; both
units decompiled `ok=1 raw=0`, **no** 0009-style `RawAsset` desync), I diffed **GDICommando vs GDIMissileSoldier**
module-by-module to find the single surviving data factor T5 predicted. Result — **there isn't one:**

- **Shared firing modules** carry identical ids and near-identical contents: `AIUpdate` (differs only in cosmetic
  `IdleScanDelay` 0.01s↔0.8s; `AutoAcquireEnemiesWhenIdle=YES` both), `WeaponSetUpdate` (differs only in the weapon
  list → already eliminated by **T8**), `ActiveBody` (differs only in `MaxHealth` 500↔300), `Physics` (**identical**).
- **83 vs 83 top-level attributes.** Every firing-relevant difference is **already eliminated** — `KindOf` (T9/T10),
  `WeaponCategory` GUN↔MISSILE (AlienSeekerTank is GUN and launches), `id` (T13b), `CommandSet` (build-button ruled
  out). The remaining ~15 diffs are purely cosmetic/economy/meta (descriptions, portraits, `VoicePriority`,
  `BuildCost`, `CommandPoints`, `MaxSimultaneousOfType` 1↔0, …).
- **Commando-unique modules** are nearly all already-eliminated: `TracerModelDraw`×4 (T5/T12), `WeaponFireSpecial-
  AbilityUpdate`×3 + `BezierProjectile` (T11), the `SpecialPower`×4/`AISpecialPowerUpdate`/`CaptureSpecialAbility-
  Update`/`EmotionTrackerUpdate` cluster (T14). The **only** residual commando-unique data modules not provably
  covered by T11/T14 are `ProductionUpdate`, `StancesBehavior`, `StealthDetectorUpdate` — **none projectile-related.**

**→ Conclusion (free oracle, honest bucket):** the commando's and missile soldier's **projectile-firing data
pipelines are identical** modulo eliminated and cosmetic fields. The data side is **exhausted** for this comparison.
That left three possibilities; **T18 (2026-11-26, in-game) then killed (a):** stripping `{ProductionUpdate,
StancesBehavior, StealthDetectorUpdate}` from a pure-`ProjectileNugget` + huge-BLAST commando still produced **no
missile and no damage** (muzzle FX only; jump-jet still worked → unit functional, override took). So the
commando-vs-missile-soldier **data side is exhausted.** Remaining: (b) **genuine engine coupling** not expressed as any
distinguishing data field — needs disassembly (out of scope), now the **leading** explanation; (c) a confound in the
T5 anchor (the missile soldier fires as a **squad member**; the commando is standalone — the two firing paths were
never cleanly separated). **T3 (Avatar, laser-nugget family) then settled it (2026-11-26, in-game): the Avatar ALSO does not launch** a clean
`ProjectileNugget` — it tries (animation plays, attack-move allowed) but spawns no projectile and deals no damage,
exactly like the commando. So the gate is **shared across hitscan families**, not tracer-draw-specific.

**→ Terminal conclusion.** Data side exhausted (null differential + T18) · art eliminated both ways (T5/T12) · both
hitscan families fail identically (commando T0/T4/T18, Avatar T3). A hitscan hardpoint will not spawn a projectile
regardless of the weapon's nugget, and nothing isolable in the model or GameObject data accounts for it → **genuine
engine coupling**, confirmable only by disassembly (out of scope). The original 2026-11-21 instinct ("it's the
unit/hardpoint, not the weapon") was right *in spirit*; every attempt to name a transplantable cause (model bone,
tracer draw, KindOf, modules, any data field) was falsified. Raw decompiles: session scratchpad
(`gobj/GameObject.GDI*.xml`).

**Escape hatch — verified buildable (2026-11-26).** The commando carbine's nugget is now a `WeaponOCLNugget` →
`OCL_GDIMjolnirProjectileStrikes`, which spawns EA's self-detonating Mjolnir strike object
(`GDIMjolnirStrikeProjectileStrike`: `FireWeaponUpdate`→`GDIMjolnirStrikeWarhead` = 800 dmg / r40 CANNON +
`LifetimeUpdate`) ~800u above the target. All data-only overrides of existing assets (build: "15 replaced, 0
inserted" → 0010-safe). Installed + active in `~/cnc-kw-godmod/hitscan-retail-test`. This is the pattern for *any*
"real projectile from a hitscan unit": don't fight the hardpoint — spawn an independent self-detonating object.

**⚠ Escape-hatch limitation — the OCL lands on the FIRER for unit/structure targets (2026-11-26, in-game).** A
`WeaponOCLNugget` fired directly by a hitscan weapon spawns its object at the **aim point for attack-GROUND** (works)
but at the **firer for object targets** (the strike drops on the commando, not the enemy). Root cause, confirmed from
shipped data: **every EA on-unit OCL effect** (MoK magnetic mine, Vertigo disruption pod, Orca sensor pod) carries the
`WeaponOCLNugget` **inside a warhead detonated by a PROJECTILE** (`ProjectileNugget WarheadTemplate=…` →
`…Warhead` containing the `WeaponOCLNugget`) — the warhead fires at the *impact point* (= the target), so the OCL
spawns on the target. A hitscan unit has no carrier projectile, so the OCL fires directly and the engine takes the
firer as origin for object targets. **This is the same coupling one layer down.** KW's `WeaponOCLNugget` has **no**
target-positioning attribute (`TargetAsPrimaryObject` exists only in the RA3 / C&C4 schemas — the TW-vs-KW trap), so
it cannot be redirected in data. Workarounds, by fidelity: (1) **attack-ground** (reliable, manual UX); (2) a
weapon-level **`DamageNugget` + a dramatic impact `FireFX`** — hitscan reliably hits the unit, so damage + an explosion
land *on the target* (instant, no flying arc); (3) spawn an **auto-firing helper object** at the firer (its projectile
appears to fly from the commando to the enemy) — but that needs a reusable EA spawn-turret object/OCL (a *new* one is
blocked by 0010). (1)+(2) are decidable in data today; (3) is a hunt.

</details>

## See also

- **`0011-hitscan-launch-test-registry.md`** — the living test scoreboard: the two hitscan render "natures"
  (tracer-draw vs laser-nugget), the full unit matrix, every eliminated hypothesis, and the in-game test ledger
  (T0–T3) with predictions and pending results.
- `docs/reference/COVERAGE.md` — weapon/armor types are byte-exact; this is a runtime weapon-delivery fact, not a
  data-fidelity gap.
- Findings 0009 / 0010 — the decompiler read-direction desyncs that blocked inspecting SI's own commando.
