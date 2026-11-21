# 0004 — A unit's locomotor is chosen per `Condition`; duplicate conditions resolve *last-wins*

**Status:** Verified (last-wins) · 2026-11-20

## Context

Because an overriding `LocomotorSet` **appends** rather than replaces
([0001](0001-joiner-matches-list-elements-by-id-only.md)), an `inheritFrom` override that adds a `LocomotorSet`
for an already-defined `Condition` leaves the unit with **two** sets for that condition — the inherited one and
yours. Which one does the unit actually use?

## Finding

A unit selects one locomotor **per `Condition`** (`NORMAL`, `NORMAL_UPGRADED`, …). With duplicate conditions,
the **last-parsed** set for a given condition wins — consistent with a one-slot-per-condition store that each
parsed set overwrites. **Confirmed in-game 2026-11-20** (see below).

If this holds, **appending your `LocomotorSet` last is the clean, unit-local way to change a unit's locomotor**
(and per-set speed) without editing the shared `Locomotor` template that other units reference.

## How to verify

1. Bake a unit with an appended `LocomotorSet` (different `Locomotor` and/or `Speed`) placed **after** the
   inherited one for the same `Condition`.
2. Launch and observe: does the unit move with the **new** locomotor/speed (last-wins) or the **inherited** one
   (first-wins)?
3. Record the result here and flip the status.

**Confirmed:** a Mothership override appends a `NORMAL` set at Speed 200 after the inherited Speed-20 set. The
decompiled asset shows both sets with ours **last**; in-game the Mothership moves at the **appended** Speed 200
(visibly racing across the map) — so the last set won. The same technique drives the MARV hover (appended
`AlienMCVLocomotor` after `GDIMammothLocomotor`). Append-last is now a proven way to change a unit's locomotor
without replacing the inherited set.

## How to apply

**Append your set last.** It's unit-local (no shared-template side effects) and it wins. This is the standard
way to re-locomote a unit (hover, fly, speed) via `inheritFrom`. Note you *cannot* prepend to force first —
`insertPosition="Top"` breaks schema order ([0002](0002-insertposition-top-is-parent-scoped.md)) — but you no
longer need to: last is what wins.

## See also

- [0001](0001-joiner-matches-list-elements-by-id-only.md), [0002](0002-insertposition-top-is-parent-scoped.md).
