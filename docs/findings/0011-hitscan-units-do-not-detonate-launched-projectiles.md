# 0011 — A hitscan hardpoint can't fire a projectile; projectile delivery is a *modeled* hardpoint

**Status:** Verified · 2026-11-21

> A **data-authoring behaviour** finding: what actually happens when you try to give a hitscan unit
> (sniper, laser) a projectile weapon. Observed from how authored data behaves in-game, and confirmed against
> a shipped unit (the Nod Redeemer). Not an engine teardown — just the rule the game enforces on authored weapons.

## Context

A very common mod wish: take a hitscan unit and make it fire a real projectile — give the GDI Commando (rail
carbine, a hitscan sniper weapon) GDI Juggernaut shells or rockets; give the NOD Avatar (laser arm) a rocket.
In every case the result is the same and baffling at first: **the weapon fires (muzzle FX + sound play), but no
projectile is ever launched** — no projectile, no impact, no damage.

## Finding

**A weapon *hardpoint* on a unit launches a projectile only if that hardpoint is a projectile hardpoint — a
turret/bone on the model wired to launch. Hitscan hardpoints (sniper, laser) deliver instantly and never launch
a projectile, no matter what weapon template you put on them.** The hardpoint's *type* is a property of the
**model**, not the data. So:

- You can swap the weapon on a hitscan hardpoint all you like — it reads the weapon's target/scatter (so shots
  still *aim* correctly) but delivers hitscan; the projectile is never spawned.
- To fire a projectile from such a unit you need a **separate projectile hardpoint** (a modeled turret/launch
  bone), i.e. an art change — or you bypass hardpoints entirely (see "escape hatch").

What *does* still work from a hitscan unit: **weapon-level, instant nuggets** — a direct `DamageNugget` (hitscan)
and a `SuppressionNugget` both apply (target takes damage / crouches). It is specifically hardpoint-launched
projectiles that never happen.

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
| **the hardpoint is a hitscan hardpoint (model)** | ✅ | everything else eliminated; the firing animation/FX play, nothing launches |

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

## See also

- `docs/reference/COVERAGE.md` — weapon/armor types are byte-exact; this is a runtime weapon-delivery fact, not a
  data-fidelity gap.
- Findings 0009 / 0010 — the decompiler read-direction desyncs that blocked inspecting SI's own commando.
