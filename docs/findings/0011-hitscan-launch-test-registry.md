# 0011 — Hitscan-launch investigation: test registry & unit matrix

**Living ledger for the "why won't a hitscan hardpoint launch a projectile?" investigation.** Companion to
`0011-hitscan-units-do-not-detonate-launched-projectiles.md` (the narrative + dated conclusions). This file is the
*scoreboard*: what's been tested, what's installed, what each test isolates, the prediction, and the (pending)
in-game result. **Oracle for the launch question is in-game**; shipped-data/byte facts are marked `[data]`.

Last updated: 2026-11-26.

> ## ⚠ Provenance audit (2026-11-26) — read before trusting the "RESULT"/"INSTALLED" labels
> This overlay (`~/cnc-kw-godmod/hitscan-retail-test`) is **not version-controlled**, and each commando test
> **overwrites** the previous `src/GDICommando.xml`, so only the *current* config + one `.step0-bak` survive on disk.
> Hard facts I could verify from the filesystem on 2026-11-26:
> - **The currently-installed commando test is T17c**, *not* T7. The last build+install is
>   `dist-local/hitscan-and-money/*.big` at **2026-11-26 00:12**, matching `src/GDICommando.xml` (T17c,
>   `inheritFrom="GDIPredator"`, war-factory, no base-commando include) at 00:11. **T7 is NOT built** — its spec
>   (huge BLAST warhead Radius 40 + `WeaponSlotID="1"`) appears in neither the installed file nor the backup. The
>   three-way "T7 ⏳ INSTALLED now / T3 ⏳ INSTALLED now / T17c ⏳ INSTALLED now" was impossible (one `GDICommando.xml`).
>   **T3 (Avatar, `src/NODAvatar.xml`) *is* genuinely installed.** Status lines corrected below.
> - **T5 has a surviving artifact** (`src/GDIMissileSoldier.xml`, a complete 520-line commando-draw transplant) —
>   real authored work, consistent with having been built + run; credible as a genuine in-game RESULT.
> - **T8/T9/T10/T14** have **no surviving artifact** (overwritten); their RESULTs rest **solely on the prior agent's
>   narrative**. I could neither confirm nor refute them from disk. Internal evidence that the session *did* run real
>   cycles is strong (independent sensory confirmations like T11 "jumpjet visibly broke", and genuine surprises like
>   T13 "build button vanished" / T15–T16 squad+critter inertness that nobody drafts as a prediction), so I did **not**
>   blanket-downgrade them — but treat T8/T9/T10/T14 as **narrative-attested, not independently verifiable**, and the
>   eliminations they anchor as *likely* rather than *proven*. **None was formatted-prediction-as-result** that I could
>   catch; the one demonstrable error was the T7/T17c **install state**, now fixed.

## The key distinction — two "natures" of hitscan render  `[data]`

All hitscan weapons share one thing: a **`DamageNugget`** (instant damage) and **no `ProjectileNugget`** (no
projectile object). What differs is **how the beam/shot is rendered**, and that splits them into two families:

| Family | Render mechanism | Where it lives | Units |
|---|---|---|---|
| **Tracer-draw** | `TracerModelDraw` bound to the weapon slot | a **draw module** (separate from the weapon) | **GDICommando**, **GDISniper**, **GDIRifleSoldier**, **NODMilitant**, **MOKCyborg** (arm A base), **NODScorpionBuggy** (base gatling) |
| **Laser-nugget** | `ActivateLaserNugget` | **inside the weapon template** (a nugget) | **NODCommando**, **NODAvatar** laser, **GDIPredator/GDIMammoth** railgun upgrade, **NODRaiderTank** (laser upgrade), **NODScorpionBuggy** (laser upgrade), **GDIZoneTrooper**, **BlackHandConfessor** (upg), **MOKCyborg** (upg), **AlienRazorDrones** (Scrin "Disintegrator") |
| **FireFX-only** | just `FireFX` (no tracer draw, no laser nugget) | the weapon's `FireFX` particle system | **BlackHandConfessor** (base minigun), **AlienMechapede** Tioxin segment |

(laser-nugget family also includes the **AlienMechapede** Head/RazorDrone segments; the Mechapede additionally offers
*projectile* segments — Proton/Shard — on the same chassis; see "natural within-unit cases".)

**GDI vs NOD Commando** — same hero role (hitscan carbine, satchel charges) but **different render nature**: the GDI
commando is **tracer-draw**, the NOD commando is **laser-nugget** (`NODCommandoLaserCarbine` = DamageNugget +
ActivateLaserNugget, zero TracerModelDraw). So the NOD commando parallels the Avatar/T3 (laser-nugget hero), *not* the
GDI commando/T2.

**Railgun ≡ laser ≡ disintegrator (one mechanism).** The laser-nugget family is cross-faction and cosmetic-only in its
variations: GDI railguns, Nod lasers, and the Scrin "Disintegrator" (`AlienRazorDrones`) are all `DamageNugget` +
`ActivateLaserNugget` (differing only in `Lifetime`/`LaserId`/`DamageType`/`FireFX`, plus flavor flags like the
Disintegrator's `ChaseWeapon="true"` + 0.75s `FiringDuration`). For the launch question they are interchangeable — T3
(Avatar) stands in for the entire family.

So being hitscan does **not** imply a TracerModelDraw — the Confessor's base minigun is hitscan with *neither* a
tracer draw nor a laser nugget. That makes it a useful **negative control**: a tracer-less hitscan infantry (see the
test ledger).

The **tracer-draw family = all basic-infantry small-arms** (assault rifle, minigun, sniper, commando carbine): every
one is `DamageNugget` + `WeaponSpeed=999999` + `TracerModelDraw`, firing from `B_WEAPONA_FX`. They are the commando's
exact nature — so if the TracerModelDraw gates launch, *none* of them can launch a projectile without removing it.
(The `…Squad` objects are containers and carry no weapon/tracer themselves; the firing member unit does.)

**→ Direct answer to the open question:** the **GDI tank railgun upgrade is the *laser-nugget* family — same nature
as the Avatar's laser, NOT the commando's carbine.** The commando's twin is the **Sniper** (tracer-draw). The Zone
Trooper is laser-nugget (railgun-style), i.e. Avatar-family.

Why this matters: if "hitscan-ness blocks launch" is real, the **block may be implemented differently per family** —
so the fix differs: tracer-draw units need the *draw module* removed; laser-nugget units just need the *nugget*
swapped for a `ProjectileNugget` (which automatically drops the `ActivateLaserNugget`). The two installed tests
target one family each.

## Unit matrix  `[data]`

| Unit | Faction | Type | Stock weapon | Delivery | Render nature | Launch bone | Bone has mesh? | Launches stock? |
|---|---|---|---|---|---|---|---|---|
| GDICommando | GDI | infantry | GDICommandoRailCarbine | hitscan (DamageNugget) | **tracer-draw** | B_WEAPONA_FX | ✅ carbine (93v) | ❌ |
| GDISniper | GDI | infantry | GDISniperRifle | hitscan | **tracer-draw** | B_WEAPONA_FX | (n/c) | ❌ (assumed) |
| GDIRifleSoldier | GDI | infantry | GDIRifleSoldierRifle | hitscan | **tracer-draw** | B_WEAPONA_FX | (n/c) | ❌ (assumed) |
| NODMilitant | NOD | infantry | NODMilitantMinigun | hitscan | **tracer-draw** | B_WEAPONA_FX | (n/c) | ❌ (assumed) |
| BlackHandConfessor (base) | NOD/BH | infantry | NODConfessorMinigun | hitscan | **FireFX-only** | (n/c) | (n/c) | ❌ (assumed) |
| BlackHandConfessor (upg) | NOD/BH | infantry | NODConfessorChargedParticleBeam | hitscan | **laser-nugget** | (n/c) | (n/c) | ❌ (assumed) |
| MOKCyborgInfantry — arm A | NOD/MoK | infantry | NODCyborgMinigun (→ChargedParticleBeam upg) | hitscan | **tracer-draw** (→laser-nugget) | BONE_WEAPONA_FX | (n/c) | ❌ (assumed) |
| MOKCyborgInfantry — arm B | NOD/MoK | infantry | NODCyborgEMPCannon (special ability) | **projectile** | — (FireFX) | BONE_FX_WEAPON | ❌ (n/c) | ✅ **launches EMP** |
| NODCommando | NOD | infantry (hero) | NODCommandoLaserCarbine | hitscan | **laser-nugget** | (n/c) | (n/c) | ❌ (assumed) |
| NODScorpionBuggy (base) | NOD | vehicle | NODScorpionBuggyGatling | hitscan | **tracer-draw** | (n/c) | (n/c) | ❌ (assumed) |
| NODScorpionBuggy (upg) | NOD | vehicle | NODScorpionBuggyGatlingLaser | hitscan | **laser-nugget** | (n/c) | (n/c) | ❌ (assumed) |
| NODRaiderTank (base) | NOD | vehicle | NODRaiderTankCannon | **projectile** | — (FireFX) | (n/c) | (n/c) | ✅ |
| NODRaiderTank (upg) | NOD | vehicle | NODRaiderTankCannonLaser | hitscan | **laser-nugget** | (n/c) | (n/c) | ❌ (laser mode) |
| AlienRazorDrones = in-game **"Disintegrator"** (anti-tank; codename ≠ display name; NOT the melee Buzzers) | Scrin | infantry | AlienRazorDroneWeapon (ranged 170, DamageType ROCKET, 75% vs infantry) | hitscan | **laser-nugget** (ChaseWeapon) | FXMuzzle | (n/c) | ❌ (assumed) |
| NODAvatar (R arm) | NOD | vehicle | NODAvatarLaser | hitscan | **laser-nugget** | B_CLAWHANDR | ❌ bare | ❌ (confounded) |
| GDIPredator (upg) | GDI | vehicle | GDIPredatorTankRailgun | hitscan | **laser-nugget** | FXMUZZLEFLASH | ✅ (93v) | ❌ (railgun mode) |
| GDIMammoth (upg) | GDI | vehicle | (railgun upgrade) | hitscan | **laser-nugget** | (n/c) | (n/c) | ❌ (assumed) |
| GDIZoneTrooper | GDI | infantry | ZoneTrooperMachineGun | hitscan | **laser-nugget** | MUZZLEFLASH | (n/c) | ❌ (assumed) |
| — launchers (controls) — | | | | | | | | |
| GDIPredator (base) | GDI | vehicle | GDIPredatorTankCannon | **projectile** | — (FireFX only) | FXMUZZLEFLASH | ✅ (93v) | ✅ |
| GDIMissileSoldier | GDI | infantry | …MissileLauncher | **projectile** | — | B_WEAPONA_FX | ❌ bare | ✅ |
| NODMilitantRocket | NOD | infantry | — | **projectile** | — | B_WEAPONA_FX | ❌ bare | ✅ |
| AlienSeekerTank | Scrin | vehicle | …PlasmaDiskLauncher | **projectile** | — | MUZZLEFX | ❌ bare | ✅ |
| NODAvatar (flamer) | NOD | vehicle | NODAvatarFlamer | **projectile** | — | FT_Turret | ❌ bare | ✅ |

`(n/c)` = not yet checked (not load-bearing for the current hypothesis). "Launches stock?" ✅ = fires a real
projectile in retail; ❌ = instant/no projectile. "confounded" = the user's past attempt likely kept
`WeaponSpeed=999999`/the laser nugget, so it isn't a clean result.

## Natural within-unit cases (shipped data — corroborate but don't *prove* the hypothesis)  `[data]`

- **MOKCyborgInfantry** carries both natures at once: a **tracer-draw hitscan** minigun arm (PRIMARY, `BONE_WEAPONA_FX`)
  that does *not* launch, and a **projectile** EMP arm (SECONDARY, `BONE_FX_WEAPON`, `NODCyborgEMPCannon` →
  `NODEMPBlastProjectile`) that **does** launch. The tracer-bearing slot is the hitscan one; the tracer-less slot
  launches. *Caveat:* different bone + fired as a special ability, so it's correlational, not a controlled same-slot
  flip. (Infantry-can-launch itself is already established by GDIMissileSoldier / NODMilitantRocket.)
- **Charged-particle-beam ("green laser") upgrade** (BlackHandConfessor, MOKCyborgInfantry): swaps the PRIMARY weapon
  `…Minigun` → `…ChargedParticleBeam` via `ObjectStatus="WEAPON_UPGRADED_01"` + a cosmetic model-condition flag. It is
  **hitscan → hitscan** (a render restyle: FireFX/tracer bullets → a laser-nugget beam), **not** a projectile↔hitscan
  flip. So it tells us the two *render* natures are interchangeable on one slot, but says nothing directly about launch.
- **GDIPredator** base→railgun upgrade is the same shape (ProjectileNugget cannon → DamageNugget+ActivateLaserNugget
  railgun on one shared bone) — and it's the one that **refuted the bare-bone theory** (see below).
- **Two upgrade taxonomies across all these units:**
  - *projectile → laser-nugget* (a real delivery change): **GDIPredator**/**GDIMammoth** railgun, **NODRaiderTank**
    cannon→laser. Base launches; upgraded is instant.
  - *hitscan → hitscan render-restyle* (no delivery change): **NODScorpionBuggy** gatling→gatlingLaser
    (tracer-draw→laser-nugget), **BlackHandConfessor**/**MOKCyborg** minigun→chargedParticleBeam. Neither mode launches.
  So an upgrade that flips the *render nature* (tracer↔laser) never changes launch behaviour, whereas an upgrade that
  flips the *nugget* (projectile↔damage) does — consistent with "launch is decided by the nugget, *unless* a render
  path gates it," which is exactly what T2/T3 test.

- **AlienMechapede** (modular Scrin unit, `AlienMillipedeBody`, **TracerModelDraw = 0**) — the strongest natural case.
  Player-chosen segment weapons on identical mounts span **both deliveries and three natures at once**: laser-nugget
  hitscan (`AlienMechapedeHeadWeapon`, `…RazorDroneWeapon`), FireFX-only hitscan (`…TioxinBlastCannon`, DamageNugget
  GRENADE/HEALING), and **projectile** (`…ProtonCannon` → AlienPlasmaDisk; `…ShardWeapon` → AlienTibShardProjectile).
  The nugget alone decides launch-vs-instant on one chassis, and — with **no TracerModelDraw present** — projectile
  segments launch freely. This is the within-unit analogue of the Predator's nugget-flip, extended to a whole menu.
  **Takeaway reinforcing the lead:** every unit that mixes projectile + hitscan without friction (Mechapede, Predator,
  all laser/railgun flips) has **zero** TracerModelDraw; the only units that resist launching are the tracer-draw ones.

## Eliminated hypotheses — all via free oracles, no in-game cycle spent  `[data]`

| Candidate | Verdict | Killer evidence |
|---|---|---|
| `WeaponCategory` (GUN/MISSILE/CANNON) routes delivery | ❌ | AlienSeekerTank = GUN, launches plasma disks |
| `WeaponSlotID` on the launch bone required | ❌ | GDIGrenadeSoldier / NODMilitantRocket launch with none |
| Launch-bone transform degenerate / at origin | ❌ | commando B_WEAPONA_FX pivot byte-identical to missile soldier's |
| **Launch bone must be BARE (no mesh sub-object)** | ❌ | **Predator launches from FXMUZZLEFLASH, a 93-vertex mesh bone** |
| Launch bone's mesh = self-collision at birth | ❌ | same: Predator's bone mesh is 93v (= carbine's size) and launches |
| (earlier, in-game/prior) weapon nugget alone; UseWeaponTiming; missing bone; animation fire-event; GameObject data wiring | ❌ | see main finding |

## Current leading hypothesis (2026-11-26)

The earlier render-path leads are **dead**: ~~bare launch bone~~ (Predator), ~~`TracerModelDraw`~~ (**T2**:
removed, still no launch — it was only the fire *visual*). The art side is gone in both directions (T5/T12), and the
**free-oracle GameObject differential below finds no distinguishing projectile-relevant data field** between the
commando and a launcher. So there is currently **no positive leading hypothesis** — the honest state is a fork:

1. ~~**Residual-data long shot** — `{ProductionUpdate, StancesBehavior, StealthDetectorUpdate}`~~ → **KILLED by T18
   (2026-11-26, in-game): removed all three, still no launch, no damage.** The commando-vs-missile-soldier **data side
   is now exhausted** — every isolable GameObject field is either eliminated, cosmetic, or tested-negative.
2. **Genuine engine coupling** not expressed as any distinguishing data field → needs disassembly (**out of scope**).
   With the data side exhausted and art eliminated both ways (T5/T12), this is now the **leading** explanation. One
   honesty caveat keeps it from being fully terminal: the T5 "it's in the data" anchor rests on a **squad-member**
   oracle (the missile soldier fires as part of `GDIMissileSquad`; the commando is standalone), so "standalone combat
   infantry firing path vs squad-member firing path" has not been cleanly separated from "engine coupling."

**~~RESOLVED (2026-11-26) → broad engine coupling~~ — REFUTED 2026-11-26, SOLVED below.** T3 looked like it settled it
("Avatar also won't launch → shared engine coupling"), and we briefly closed the finding as "engine coupling,
data-unfixable." **That was wrong.** The null GameObject differential was correct but mis-read: the gate isn't in the
GameObject, it's in the **stream load-ORDER** of the `ProjectileNugget`'s referenced templates.

## ✅ SOLVED (2026-11-26) — stream load-order of the projectile/warhead templates

**The rule:** a `ProjectileNugget` binds its `ProjectileTemplate` and `WarheadTemplate` by **forward lookup during the
sequential stream-load pass** — each must appear **before** the referencing weapon in the compiled manifest order, or
it binds to **null silently**. Projectile-order → the *spawn*; warhead-order → the *detonation*; independent. Fixed in
data by reordering the stream (`modkit/lib/reorder_stream.py`, which permutes `.bin/.relo/.imp` in lockstep —
relo/imp are asset-local, 0010-safe — then `retag_checksum.py`). **Unit-agnostic:** proven on the GDI Commando AND the
NOD Avatar. Every T0–T20 "failure" was a forward reference; EA launchers "just work" because EA authored each unit's
projectile/warhead before its weapon.

**In-game proof matrix (commando, `GDICommandoRailCarbine` at base-order index 19237; projectile 19314 / warhead 20690):**

| build | projectile vs weapon | warhead vs weapon | RESULT (in-game) |
|---|---|---|---|
| CLEAN (base order) | after | after | ❌ nothing (= every T0–T20) |
| **A2** | after | **before** | ❌ nothing — projectile-order is *necessary* for the spawn |
| **A1** | **before** | after | ⚠ **spawns & flies, NO detonation/damage** — projectile-order=spawn, warhead-order=detonation |
| **WORKING** | **before** | **before** | ✅ **spawns + flies + detonates + damage** |
| **C1 (Avatar)** | **before** | **before** | ✅ **Avatar launches + damages** → rule is unit-agnostic |

**Why the earlier call was wrong:** the "order is irrelevant" argument compared *distance* (a working launcher
references its projectile 1,377 entries away) but not **direction** — that launcher's projectile is 1,377 *earlier*
(backward, fine); the commando's was *later* (forward, null). The first reorder crashed only because it moved manifest
entries without the parallel `.bin/.relo/.imp` blocks (cumulative-offset desync); the lockstep reorder loads + launches.

(The `WeaponOCLNugget` → `OCL_GDIMjolnirProjectileStrikes` escape hatch still works as an *alternative*, but is no
longer necessary — the hardpoint launches directly once the stream order is fixed.)

## Free-oracle GameObject differential — GDICommando vs GDIMissileSoldier (clean retail, 2026-11-26)

Decompiled both `GameObject`s from the decompressed retail `static_common` (`ea-roundtrip/eastream`), `ok=1 raw=0`
(clean — the decompiler now reads retail GameObjects, unlike the 0009 SI desync). Diffed module-by-module to find the
single data factor T5 predicted. **None survives:**  `[data]`

| Area | Commando vs Missile Soldier | Verdict |
|---|---|---|
| `AIUpdate` (id 0x12fa48ba, shared) | identical but `IdleScanDelay` 0.01s↔0.8s; `AutoAcquireEnemiesWhenIdle=YES` both | cosmetic |
| `WeaponSetUpdate` (id 0x720f4a50, shared) | only the weapon **list** differs | eliminated by **T8** |
| `ActiveBody` (id 0xb313f576, shared) | only `MaxHealth` 500↔300 | cosmetic |
| `Physics` (id 0x6d41764b, shared) | **byte-identical** | — |
| Top-level attrs (83↔83) | firing diffs = `KindOf`, `WeaponCategory`, `id`, `CommandSet` | **all already eliminated** (T9/T10, Seeker, T13b, build-button) |
| Top-level attrs (rest) | descriptions, portraits, `VoicePriority`, `BuildCost`, `CommandPoints`, `MaxSimultaneousOfType` 1↔0 … | cosmetic/economy/meta |
| Commando-unique modules | `TracerModelDraw`×4, `WeaponFireSpecialAbilityUpdate`×3+`BezierProjectile`, `SpecialPower`×4 + `AISpecialPowerUpdate`/`CaptureSpecialAbilityUpdate`/`EmotionTrackerUpdate` | eliminated by T5/T12, T11, T14 |
| Commando-unique **residue** | `ProductionUpdate`, `StancesBehavior`, `StealthDetectorUpdate` | **only untested data candidates** (none projectile-related) |

**→ The projectile-firing data pipelines are identical modulo eliminated + cosmetic fields. The data side is
exhausted for this comparison.** Raw decompiles: session scratchpad `gobj/GameObject.GDICommando.xml`,
`gobj/GameObject.GDIMissileSoldier.xml`. (Caveat: GDIMissileSoldier is a squad **member** (T15); a standalone-combat
launcher would be a cleaner oracle, but no standalone *combat* infantry launcher exists in retail — the only
standalone infantry launcher is the Viceroid, an ambient critter with a wander-AI, T16.)

## In-game test ledger

| ID | Unit (faction) | What it changes | Isolates | Prediction (leading hyp.) | Result | Notes |
|---|---|---|---|---|---|---|
| T0 | Commando (GDI) | weapon → pure ProjectileNugget, else stock | nugget alone | launch | ❌ **no launch** (FX only) | prior clean retail test; the anchor fact |
| T1 | Commando (GDI) | + re-point launch bone B_WEAPONA_FX→PROPS0 (bare) | bare-bone theory | launch | — superseded, not run | built+installed, then **replaced** after Predator refuted bare-bone |
| **T2** | **Commando (GDI)** | ProjectileNugget + **remove both PRIMARY TracerModelDraws**, stock bone | **tracer-draw gate** | launch | ❌ **REFUTED — no launch, no damage**; weapon only twitches on its ~1.3s reload cycle; removing the tracer just removed the fire *visual* (the override weapon has no FireFX). Tracer is NOT the gate. |
| **T4** | **Commando (GDI)** | weapon = **DamageNugget + ProjectileNugget** + explicit FireFX; **stock draw** (tracer restored) | does the weapon fire its nuggets at all, or fail only on projectiles? | — | ✅ **RESULT: damage dealt, carbine FX play, but NO projectile.** → **PROJECTILE-SPAWN GATE confirmed**: the fire event completes, nuggets execute, `DamageNugget` applies damage — but `ProjectileNugget` instantiates nothing. |

**Self-collision ("spawns inside the carbine and dies") — DISFAVORED, not yet directly proven.**
⚠ *Retraction:* an earlier version argued "no self-damage → no projectile." That is **invalid** — in SAGE a projectile
normally excludes its own firer from collision, so it wouldn't self-damage even if it spawned; and T4's enemy damage is
the **DamageNugget**, not the projectile warhead, so it says nothing about the projectile. (Credit: user caught this.)
The honest indirect evidence that leans toward *never-spawns* rather than *spawns-and-dies*:
  - **T0** (pure ProjectileNugget, no DamageNugget) dealt **zero** damage to the target — a firer-immune projectile that
    spawned would fly to the target and apply its warhead; none did, so nothing reached the target.
  - No projectile is ever visible leaving the muzzle, and no detonation FX appears at the commando (a muzzle death would
    show the warhead's explosion + splash the ground).
  - The missile soldier launches from the **byte-identical** `B_WEAPONA_FX` position and the Predator from a 93-vertex
    muzzle-mesh bone → neither the position nor a mesh-on-the-bone is lethal to a projectile.
This is strong but **indirect**. A **direct discriminator** (pure ProjectileNugget + a huge, unmistakable warhead: boom
at the enemy = launches; boom at the commando = spawns-and-dies; no boom = never spawns) is the clean settle if needed.
| T6 | Commando (GDI) | add `WeaponSlotID="1"` to PRIMARY launch bone | multi-weapon-hardpoint launch-bone binding | — | folded into **T7** (its SlotID fix is kept there) |
| **T7** | **Commando (GDI)** | **pure ProjectileNugget + a HUGE BLAST warhead (Radius 40)** + the T6 `WeaponSlotID="1"` fix; muzzle FireFX confirms firing | **direct discriminator: never-spawns vs spawns-and-dies vs launches** (no DamageNugget confound) | — | **⏳ PENDING — DRAFTED, NOT BUILT** (2026-11-26 audit: this spec is in no file on disk; the installed commando config is T17c). Needs authoring into `src/GDICommando.xml` before it can run. boom at ENEMY → launches (SlotID fixed it); boom at COMMANDO → spawns-and-dies at muzzle; no boom → never spawns |
| **T3** | **Avatar R-arm (NOD)** | NODAvatarLaser → pure ProjectileNugget, finite speed (drops ActivateLaserNugget), bare bone | **laser-nugget gate** | **launch** | ✅ **RESULT (2026-11-26): does NOT launch, NO damage** — tries to fire (animation plays, allows attack-move), muzzle only, no projectile. → **the laser-nugget family ALSO won't launch a clean ProjectileNugget.** Both hitscan families (tracer-draw T0/T4/T18 + laser-nugget T3) fail identically → the gate is **shared across hitscan families** (broad), not tracer-draw-specific. |
| **T5** | **Missile Soldier (GDI)** — REVERSE | give the known launcher the **commando's whole draw** (model GU_Cmmndo_SKN + anims + launch wiring w/ SlotID); keep its stock launching weapon | is the commando's DRAW the gate, or its unit-data? | — | ✅ **RESULT: missile soldiers wearing commando art STILL launch + deal damage.** → **commando DRAW/model/bones INNOCENT**; the gate is in the commando's **unit-data/identity**. Entire art side eliminated. |
| **T8** | **Commando (GDI)** | `WeaponSetUpdate` **collapsed to a single PRIMARY** projectile weapon (drop satchel/contained); big BLAST warhead; stock draw | multi-weapon hardpoint / extra weapons? | — | ✅ **RESULT: no blast, muzzle FX only.** → multi-weapon hardpoint / weapon-set config is **NOT** the gate. |
| **T9** | **Commando (GDI)** | remove **`SNIPER`** from KindOf (clean retail re-test); single PRIMARY big-BLAST projectile | does KindOf SNIPER force the hitscan path? | — | ✅ **RESULT: no change, muzzle FX only.** → `SNIPER` KindOf is **NOT** the gate (clean-retail confirm of 0011's old SI claim). |
| **T10** | **Commando (GDI)** | set KindOf to the **missile soldier's minimal set** (drop all remaining extra flags at once); single PRIMARY big-BLAST | any KindOf flag the gate? | — | ✅ **RESULT: no change.** → **all KindOf eliminated.** |
| **T11** | **Commando (GDI)** | strip the 3 `WeaponFireSpecialAbilityUpdate` (satchel/jumpjet) + `BezierProjectile` modules; single PRIMARY big-BLAST | weapon-adjacent modules? | — | ✅ **RESULT: no change** (jumpjet visibly broke, confirming the strip took). → NOT those modules. |
| **T12** | **Commando (GDI)** | **forward art swap**: give the commando the **missile soldier's full draw** (model GUMissleman_SKN + anims + launch wiring) — mirror of T5; single PRIMARY big-BLAST | final art test — does commando launch wearing a launcher's art? | — | ✅ **RESULT: no change** (commando now looks like a missile soldier, still fires only carbine FX). → **art exonerated in BOTH directions** (T5 + T12). |
| T13 | Commando CLONE (GDI) | new `GDICommandoTestClone` + repoint barracks button | name vs data | — | ⚠ **build button VANISHED** — a brand-new inserted unit doesn't register in the build UI when a button is repointed to it. Approach abandoned; redone as T13b. (Weak hint only; not a weapon signal.) |
| **T13b** | **Engineer-as-Commando (GDI)** | hijack `GDIEngineer` → inheritFrom GDICommando (commando data, **id stays GDIEngineer**) | name vs data | — | ✅ **RESULT: engineer-commando (commando icon/voice/mesh, id GDIEngineer) still won't launch.** → **NOT name/identity-hardcoded**; the engine is data-driven; the gate is a commando **data property** (inherited by the clone). |
| **T14** | **Commando (GDI)** | strip the **entire special-ability/cosmetic module cluster**; projectile big-BLAST | any module, or deeper? | — | ✅ **RESULT: no change.** → no strippable module is the gate. |
| **T15** | **Commando (GDI)** — total replacement w/ missile soldier | `GDICommando inheritFrom="GDIMissileSoldier"` | data vs id | — | ⚠ **CONFOUNDED: the unit couldn't even attack.** `GDIMissileSoldier` is a squad **member**, non-functional standalone (no squad to direct it). Reveals infantry squad architecture; doesn't test launch. |
| T16 | Commando (GDI) — viceroid replace | `inheritFrom="Viceroid"` | data vs id | — | ⚠ not buildable (inherited Viceroid's `Side="Neutral"`/EmptyCommandSet) → redone as T16b |
| T16b | Commando (GDI) — viceroid replace | + Side=GDI/CommandSet/IsTrainable | data vs id | — | ⚠ still not buildable — Viceroid also lacked `ProductionQueueType`/`UnitCategory` (barracks produces the INFANTRY queue). Fixed in T16c. |
| T16c | Commando (GDI) — viceroid replace | + ProductionQueueType/UnitCategory=INFANTRY | data vs id | — | ⚠ buildable now, but **couldn't attack / wandered in place** — the Viceroid uses a `WanderAIUpdate` (ambient critter AI), not a combat `AIUpdate`. Fixed in T16d. |
| T16d | Commando (GDI) — viceroid replace | AI swap via joinAction="Replace" | data vs id | — | ⚠ still can't fire + still wanders → the cross-type `Replace` likely no-op'd (type mismatch). Redone as T16e. |
| T16e | Commando (GDI) — viceroid replace | proper AI swap (Remove wander + Add combat AI) | data vs id | — | ⚠ **still can't be ordered to fire.** Viceroid is fundamentally an ambient critter, not a controllable combat unit — dead end as a source. |
| T17 | Commando (GDI) — tank via barracks | `inheritFrom="GDIPredator"` + INFANTRY queue | data vs id | — | ⚠ doubtful a vehicle builds from the barracks (VEHICLE KindOf/infantry exit). Rerouted to war factory as T17b. |
| T17b | Commando (GDI) — tank, war factory | `inheritFrom="GDIPredator"`, included base GDICommando.xml | data vs id | — | ⚠ **builds + moves but CAN'T attack** (no red cursor). Third source unit to go combat-inert as GDICommando → pattern. Suspected cause: including base GDICommando.xml while redefining it with inheritFrom MERGES into a broken unit. |
| **T17c** | **Commando (GDI)** — TANK, war factory, **no base-commando include** | `inheritFrom="GDIPredator"` with the base `GDICommando.xml` include REMOVED (clean define) | **is the combat-inertness a merge artifact of my override, or the GDICommando id itself?** | — | ⏳ **DRAFTED, de-installed 2026-11-26** (config backed up to `src/GDICommando.xml.t17c-bak`; superseded by T18 as the installed commando test). can attack + launches shell → merge artifact (id innocent), 100% DATA; still can't attack → GDICommando id/object genuinely special-cased |
| **T18** | **Commando (GDI)** — residual-data strip + T7 discriminator | pure `ProjectileNugget` PRIMARY + **huge BLAST warhead** (existing `GDIMissileSoldierMissileWarhead` bumped to Radius 40 / Dmg 2000) + **remove the 3 residual commando-unique data modules** (`ProductionUpdate`=`ModuleTag_ProductionUpdate`, `StealthDetectorUpdate`=`ModuleTag_StealthDetect`, `StancesBehavior`=`ModuleTag_Stance`); stock draw/bone | **the cheapest decisive data-side move left** — the only commando-unique data the 2026-11-26 differential left untested | — | **⏳ PENDING — BUILT + INSTALLED + ACTIVE 2026-11-26 00:30** (`src/GDICommando.xml`; build "16 replaced, 0 inserted" → all data-only overrides, 0010-safe; GDI skirmish, standard map). **boom at ENEMY → a module was the gate (DATA, decisive); boom at/under COMMANDO → spawns-and-dies at muzzle; NO boom, muzzle FX only → data side EXHAUSTED → genuine engine coupling (disassembly, out of scope).** → ✅ **RESULT (2026-11-26): NO boom — muzzle + bullet-shot FX only, NO missile spawned, NO damage** (jump-jet still works → unit functional, override took). "No damage" corroborates *never-spawns* (= T0; a pure ProjectileNugget's warhead only applies on impact). → **the 3 residual modules are NOT the gate; the commando-vs-missile-soldier DATA side is now exhausted.** |
| **T19** | **Commando (GDI)** — ESCAPE HATCH v1 (not a diagnostic) | carbine nugget → `WeaponOCLNugget WeaponOCL="OCL_GDIMjolnirProjectileStrikes"` (spawns `GDIMjolnirStrikeProjectileStrike`, self-detonating, 800 dmg / r40, ~800u above target); stock commando otherwise | **make it work** (bypass the hardpoint) | real damaging projectile from a hitscan commando | ✅ **RESULT (2026-11-26): works on attack-GROUND (orbital shell drops on the point); on a UNIT/structure target it lands on the COMMANDO** (WeaponOCLNugget origin = firer for object targets). Superseded by T20. Backup `…t19-ocl-mjolnir-bak`. |
| **T20** | **Commando (GDI)** — ESCAPE HATCH v2 / helper-spawn | carbine → `WeaponOCLNugget OCL_GDISuperSonicAirAttack` (auto-acquiring summoned jet, 1.7s life) + **override its weapon `GDISupersonicAirWeapon` → `ProjectileNugget` + `ANTI_GROUND`** so the helper fires a real missile at the commando's target | **real flying projectile at a UNIT target** (sidestep the firer-origin limit via an auto-acquiring helper) | escort jet spawns near commando, acquires the enemy, launches a missile at it | **⏳ BUILT + INSTALLED + ACTIVE 2026-11-26** (`src/GDICommando.xml`; "16 replaced, 0 inserted" → 0010-safe). Attack a ground unit: expect a FireHawk jet to streak in and fire a missile at the target. Missile flies to enemy → SUCCESS; jet ignores enemy / no missile / wrong direction → tune AntiMask / acquire range / FireWeapon aiming. → ❌ **RESULT (2026-11-26): jet spawns at the commando but does NO damage** (ground or air); fires nothing useful at the target. Cause: the jet discharges its weapon via `FireWeaponUpdate` (blind OneShot timer), **not** aimed at the `JetAIUpdate`-acquired enemy, so the missile goes nowhere. Reusable-asset helper-spawn path is **not working** (v1 firer-origin, v2 no-engage). |
| **T21** | **Commando (GDI)** — ✅ **BREAKTHROUGH** | post-build **stream reorder**: move projectile(19314)+warhead(20690) to **before** the weapon(19237) in the compiled manifest, `.bin/.relo/.imp` permuted in lockstep + retag (`reorder_stream.py`) | does compiled stream ORDER gate the spawn? | — | ✅ **RESULT: commando LAUNCHES a real projectile + damage.** The "impossible / engine coupling" conclusion is REFUTED — it was stream load-order all along. |
| **T22 (A2)** | **Commando (GDI)** | reorder **warhead only** before weapon (projectile left after) | is projectile-order necessary for the spawn? | nothing | ✅ **RESULT: no launch, no damage** → projectile-order is **necessary**. |
| **T23 (A1)** | **Commando (GDI)** | reorder **projectile only** before weapon (warhead left after) | split spawn vs detonation | spawn, no boom | ✅ **RESULT: projectile spawns & flies, NO detonation/damage** → projectile-order=spawn, warhead-order=detonation (independent). |
| **T24 (C1)** | **Avatar (NOD)** | reorder projectile+warhead before `NODAvatarLaser` | unit-agnostic? | launch+damage | ✅ **RESULT: Avatar launches + damages** → rule generalizes across units/factions/families. |

**User observation (sharp):** T15 (missile data) AND T16 (viceroid data), both under the GDICommando id, can't even *try*
to fire — raising "is the no-fire tied to the commando id?" **Counter-evidence:** T13b (commando data under the
*engineer* id) DID fire, and the real commando always fires — so the GDICommando id isn't fire-broken. The shared cause
in T15/T16 is that both *source* units are non-standalone-combat (missile=squad member; viceroid=wander-AI). T16e tests
this by making the viceroid genuinely controllable; if it then fires, the id theory is dead.

**Squad hypothesis — RAISED then REFUTED (data).** After T15, suspected infantry launch might be squad-mediated (all
launching infantry — missile soldier, militant rocket, grenade, cyborg, stalker, black hand — are squad members). But
the **Viceroid** is a **standalone** infantry (no squad) that launches `NeutralViceroidSpittleWeapon` (ProjectileNugget,
speed 300). So standalone infantry CAN launch → not a squad/standalone gate. (The commando is also standalone; it fires
hitscan fine, so standalone combat works — the gate stays a data property.)

**Note (user, mid-T12):** the commando is **NOT** data-identical to the missile soldier — it still has its own voice
lines, command set (jumpjet button visible), geometry, and ~15 untouched modules. So we have **not** proven
"hardcoded despite identical data"; we've eliminated the *obvious weapon-relevant* data. T13 tests the name-vs-data fork.

**Build-button theory — RULED OUT (data).** `Command_ConstructGDICommando` is literally `{Type="UNIT_BUILD",
<Object>GDICommando</Object>}` — no weapon/behavior/status fields; it only names the template to instantiate. Buttons
can't shape unit behavior. (Also: the missile soldier's identical-structure button builds a launching unit.)

**Installed + ACTIVE right now** (investigation ✅ SOLVED 2026-11-26): currently the **C1 Avatar probe**
(`scratchpad/probes/probe_C1.big`). Probe `.big`s + a swap helper live in the session scratchpad
(`probes/use_probe.sh <A1|A2|C1|WORKING|CLEAN>`): `WORKING` = commando launches+damages (both templates before weapon),
`CLEAN` = base order (nothing), A1/A2/C1 as in the matrix above. The **fix tool** is `modkit/lib/reorder_stream.py`
(lockstep stream reorder) + `retag_checksum.py`. Source configs still in `src/` (`…step0-bak` pure ProjectileNugget,
`…t19-ocl-mjolnir-bak` orbital strike, etc.). To ship the fix cleanly, the reorder should become an `openwrath` build pass. This is the **usable escape hatch**: aim at the GROUND near a target → an orbital
shell drops + detonates (800 dmg / r40). It does NOT deliver onto a unit/structure target (lands on the firer — the OCL
limitation). The flying-projectile-onto-a-unit goal was abandoned as **data-unachievable** (helper-spawn failed both
ways: T19 firer-origin, T20 no-engage; the only remaining route is a new-asset insert, out of scope). Backups:
T20 escort-jet at `…t20-escortjet-bak`, T18 residual-strip at `…t18-residualstrip-bak`, T17c at `…t17c-bak`.

> **Final word (2026-11-26):** hitscan GameObjects in KW are a sealed box — the engine hard-wires instant delivery and
> blocks projectile spawning at every data layer (hardpoint launch, OCL-on-target, auto-acquiring helper). What you CAN
> get from a hitscan unit, reliably: instant `DamageNugget`/`SuppressionNugget` on the target, and an **attack-ground**
> OCL strike. A real projectile that flies onto a *unit* target is not reachable without inserting new assets.

**Why T19→T20 (on-unit OCL limitation, finding 0011 main §escape-hatch):** a `WeaponOCLNugget` fired by a hitscan
weapon spawns at the aim point for attack-GROUND but at the **FIRER** for unit/structure targets (EA's on-unit OCL
effects use a projectile-carried warhead that detonates on the target — impossible for hitscan). KW's `WeaponOCLNugget`
has no target-positioning flag (`TargetAsPrimaryObject` is RA3/C&C4-only). T20 sidesteps this with an **auto-acquiring
helper** that fires its own projectile at the enemy. No reusable EA object is *both* auto-acquiring and projectile-firing
(`GDISuperSonicAirAttack` = auto-acquire + sonic/hitscan; `GDIOrca_BombingRun` = projectile + strafe-area/no-acquire),
so T20 overrides the auto-acquiring jet's weapon into a projectile. A literal "projectile from the commando's gun" at a
unit target would need a *new* helper GameObject+OCL (blocked by 0010 without `--adopt-schema`, untested in-game). Project `~/cnc-kw-godmod/hitscan-retail-test`; rebuilt with
`python3 modkit/openwrath mod build-local ~/cnc-kw-godmod/hitscan-retail-test --no-check --install --force`
(the `--no-check` is needed only to skip pre-existing `fastbuild.xml` structure-validation noise; the commando/weapon
edits validate clean). T17c is preserved at `src/GDICommando.xml.t17c-bak`; T7 remains drafted-not-authored (its BLAST
discriminator is now folded into T18). Play on a **standard map** (R23/tournament maps crash on their own — 0017).

## Available next tests (not built)

- **Sniper (tracer-draw family, infantry)** — redundant confirmation of T2 on an independent unit; single-shot vs
  the commando's auto. Build only if T2 is ambiguous.
- **Zone Trooper (laser-nugget family, infantry)** — infantry analogue of T3/Avatar; confirms the laser family isn't
  vehicle-specific. Build only if T3 is ambiguous.
- **Whole-model swap (commando ← missile soldier draw)** — ladder step 1; the escalation if T2 fails (removes the
  tracer AND everything else model-side at once).
- **Predator reverse** — add a TracerModelDraw to the Predator's slot; does its cannon stop launching? (positive→
  negative control for the tracer hypothesis). Harder to interpret; last resort.
- **T5 (user theory) — emulate a launcher's weapon-slot setup on the commando.** Make the commando's weapon slot look
  like a unit whose ProjectileNugget *does* launch. **Nuance:** the Predator's *upgrade* (WeaponSetUpgrade + ObjectStatus)
  only swaps weapons — the **base** Predator launches with no upgrade at all — so what actually matters is its
  launch-capable *slot config*, not the toggle. And slot **type** isn't the gate (GDIMissileSoldier uses a
  WeaponSlotHardpoint and launches), so the most faithful emulation is matching the **missile soldier** (same class:
  infantry) — i.e. converge on the whole-model/draw swap (ladder step 1). Priority depends on T4: **projectile-spawn
  gate → this direction is right**; **fire-event-never-completes → a firing/animation fix is needed instead.**

## Interpretation key (updated 2026-11-26 — render-path leads already dead)

T2 already came in **refuted** (tracer removed, still no launch), so the old render-path key is retired. The live
deciders are now:

- **T17c** (commando-id as a Predator tank, via War Factory): **attacks + launches a shell** → the `GDICommando`
  id/object is innocent and the gate is 100% data — but since the differential finds *no* distinguishing data, that
  pushes toward the residual-data long shot or a merge-only artifact; **can't attack at all** → the combat-inertness
  seen in T15/T16/T17b was a merge/override artifact, inconclusive on launch (re-cast the test).
- **T3** (Avatar, laser-nugget family): **launches** → the laser family only ever needed a `ProjectileNugget`;
  narrows the open puzzle to the tracer-draw family. **Still nothing** → a gate shared across hitscan families,
  strengthening the engine-coupling bucket.
- **Residual-data strip test** (new, cheapest decisive data move): single-PRIMARY `ProjectileNugget` + BLAST commando
  with **`ProductionUpdate` + `StancesBehavior` + `StealthDetectorUpdate` removed** (`xai:joinAction="Remove"`).
  **Launches** → one of those three was the gate (astonishing, but decisive). **Still nothing** → the data side is
  fully exhausted → honest terminal bucket: **genuine engine coupling, needs disassembly (out of scope).**
- **T7** (pure `ProjectileNugget` + huge BLAST, no DamageNugget confound): the clean never-spawns-vs-spawns-and-dies
  discriminator; still worth authoring+running to confirm T4's "never spawns" read directly.
