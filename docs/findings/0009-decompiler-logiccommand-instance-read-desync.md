# 0009 — The decompiler can't read `LogicCommand` instance data (desyncs to a raw block)

**Status:** RESOLVED (root cause found) · 2026-11-21

> Like [0008](0008-xinclude-xpointer-not-honored.md), this is about **our own tool** (the decompiler /
> `openwrath inspect`), not a fact about the game's data format.

## Resolution (what it actually was)

**Not a `LogicCommand`-specific model bug — it's schema drift.** `LogicCommand` is one of 12 types Second
Isomer's stream diverged from retail on (confirmed by the new `openwrath schema --drift-only`: `LogicCommand`
stream hash `0x548adf93` vs our compiler's `0x97d0a46e`). Our decompiler walks the **retail** layout, so reading
a *layout-drifted* SI instance desyncs to a `RawAsset`. The H1/H2 discriminator below is answered: it's drift,
and the decisive test turned out to be free — **non-drifted** types (`GameObject`, `WeaponTemplate`) read fine
from the *same* `static_mod` stream, while **layout-drifted** ones (`LogicCommand`, `ObjectCreationList`,
`SpecialPowerTemplate`) desync; **hash-only-drifted** ones (`UpgradeTemplate`) still read cleanly. Full write-up,
including the two flavors of drift and the tooling built (`openwrath schema`, the bake guard, `--adopt-schema`),
is in [0010](0010-insert-must-match-target-stream-type-schema-hash.md). This finding stands as the first
*observation* of the symptom; 0010 is the general truth and the fix.

## Context

While wiring a special-power ability onto a unit, we wanted to read a command's `<SpecialPower>` binding
straight from the stream with `openwrath inspect <cmd> --type LogicCommand`. Every attempt fell back to a
`<RawAsset>` block instead of a rendered `<LogicCommand>`.

## Finding

**The decompiler's `LogicCommand` reader desyncs on read: it expects a 24-byte instance struct at offset 0,
but computes the instance's data end as 0, so the struct-walk would overrun.** The desync guard (the Phase-5
anti-crash property) correctly aborts *that asset* to a labeled raw block and keeps going — nothing crashes —
but the fields (`Options`, `Type`, `<SpecialPower>`, …) are not recovered:

```
<RawAsset TypeId="0x7d464170" TypeHash="0x548adf93" InstanceId="..."
          reason="desync: struct LogicCommand@0 len 24 past instance end (0)" />
```

It is **not instance-shape-specific** — it hit every `LogicCommand` tried, including a reference-only
special-power command and a plain built-in:

| Instance | Result |
|----------|--------|
| `Command_CommandPostRadarScan` (a `SPECIAL_POWER` command) | RawAsset — `past instance end (0)` |
| `Command_AttackMove` (built-in) | RawAsset — `past instance end (0)` |
| `Command_ActivateAdaptiveArmor` | RawAsset — `past instance end (0)` |

## Why this matters / scope

This is a **decompile-direction read gap, not a compile gap.** `Command_ActivateAdaptiveArmor` is the very
instance [`../reference/COVERAGE.md`](../reference/COVERAGE.md) lists as **byte-exact** for `LogicCommand` — but
that number comes from the ground-truth *roundtrip* gate against the base `static_common` stream. The failures
above were observed reading the **baked `static_mod`** stream via `openwrath inspect`. So either:

- **(H1) Stream/instance-size specific:** in `static_mod` these `LogicCommand` entries carry `InstanceDataSize`
  the reader resolves as 0 (payload entirely in relocations/imports, e.g. the `<SpecialPower>` asset-ref), and
  the fixed 24-byte struct expectation is wrong for the reference-only case. Other types (`WeaponTemplate`,
  `GameObject`, `ObjectCreationList`) read fine from the *same* `static_mod` stream, so it is type-local, not a
  whole-stream (e.g. compression) problem.
- **(H2) Model gap:** the `LogicCommand` struct layout / size derivation in the reader is simply wrong, and it
  would desync in any stream.

These are distinguishable: **inspect a `LogicCommand` from the base `static_common` stream.** If it also
desyncs → H2 (model gap). If it reads fine → H1 (the mod stream's instances store their data differently than
the reader assumes). That one check is the next step; until it's run, this stays a Hypothesis.

## Evidence

- `openwrath inspect Command_CommandPostRadarScan --type LogicCommand` (and `Command_AttackMove`,
  `Command_ActivateAdaptiveArmor`) against the baked `ada_1_Streams.big` / `static_mod` → `<RawAsset …
  reason="desync: struct LogicCommand@0 len 24 past instance end (0)">` for all three.
- The compile/roundtrip number in `COVERAGE.md` (LogicCommand BYTEEXACT on `Command_ActivateAdaptiveArmor`) is
  from `static_common`, so it does **not** contradict this — different stream, different direction.

## How to apply (for now)

- To read a command's binding today, go to the **authored SDK XML** (`GlobalData/LogicCommand.xml`) rather than
  `inspect` — that's how the radar-scan wiring was verified (`<SpecialPower>SpecialPowerRadarScan</SpecialPower>`).
- Don't trust `inspect`'s silence on `LogicCommand` as "no such command" — a `RawAsset` with this `reason` means
  *found but unreadable*, not *absent*. (`openwrath find` still lists it correctly.)

## How to fix (directions)

1. Run the H1/H2 discriminator above.
2. If H1: make the `LogicCommand` reader honor the real `InstanceDataSize` and treat a 0-length inline struct as
   "all fields defaulted / carried in refs" instead of forcing a 24-byte read — then resolve `<SpecialPower>`
   and friends from the `.imp`/`.relo` lists (the same reference-resolution path Phase 3 uses).
3. Add a `LogicCommand` instance to the decompiler round-trip corpus so the fix is measured and can't regress.

## See also

- `docs/reference/COVERAGE.md` (LogicCommand row — compile-direction byte-exact; add a decompile-read caveat).
- The decompiler plan, Phase 3 (reference/import resolution) and Phase 5 (graceful degradation — which worked
  here: the desync guard downgraded to a raw block rather than crashing).
