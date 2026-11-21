# 0010 — Inserting a new asset into a foreign stream must match that stream's per-type schema hash

**Status:** Verified (the crash + its cause) · Hypothesis (the exact fix) · 2026-11-21

> Like [0008](0008-xinclude-xpointer-not-honored.md)/[0009](0009-decompiler-logiccommand-instance-read-desync.md),
> this is about **our tooling** (the modkit's `mod bake` *insert* path), not the game's data format — and it is
> the data-format counterpart of the plan's **Phase 5 "schema-version check"**, now forced by a real crash.

## Context

Every compiled asset entry carries two 32-bit fields: a **TypeId** (which type) and a **TypeHash** (a fingerprint
of that type's *schema*, derived from the XSD/struct). The engine, when loading a linked stream, requires that
**every asset sharing a TypeId also shares one TypeHash** — one schema version per type per stream. Mismatch is
fatal:

```
Type hash mismatch for type 0xe86e4d61 in asset <<Not Available>>.
Expected hash: 0x8b85f295 but got: 0x683d4de5 ... the game will now exit.
```

`0xe86e4d61` is `ObjectCreationList`. We hit this the first time we **inserted a brand-new `ObjectCreationList`**
(a radar-scan burst) into **Second Isomer's `static_mod` stream**.

## Finding

**Second Isomer's stream was built against a different `ObjectCreationList` schema than retail — same TypeId,
different TypeHash — so inserting a retail-schema OCL into it is rejected by the engine.**

- SI's stock OCLs carry TypeHash **`0x8b85f295`** (observed: `OCL_GDICommandPostRadarScanPing` in `static_mod`).
- Our compiler stamps the **retail** hash **`0x683d4de5`** (`XmlCompiler/Plugin.cs` type registry) — and our OCL
  output is byte-exact against *retail* EA, so the compiler is correct; the two just target different schema
  versions. This is **version/schema drift**, not a compiler defect.

**Why it never bit before:** every prior insert was a `WeaponTemplate` or `GameObject` — types where SI's hash
*equals* retail's, so no mismatch. (Confirmed: re-baking the avatar still inserts a new `GameObject` + a new
`WeaponTemplate` into the same SI stream with zero complaint.) **REPLACE is structurally immune** — splicing over
an existing asset keeps that entry's TypeHash, so the stream's schema version is preserved no matter what our
compiler would have stamped. Only **INSERT** introduces a fresh entry whose TypeHash is ours, and only for a type
SI diverged on does that clash. `ObjectCreationList` was the first such type we inserted.

## Evidence

- Crash dialog above, on launch, immediately after a bake whose summary was `4 replaced, 1 new (inserted)` where
  the insert was `OCL_OpenWrathCommandoRadarBurst`.
- `openwrath inspect OCL_GDICommandPostRadarScanPing --type ObjectCreationList --verbose` →
  `TypeHash="0x8b85f295"` for the stock SI OCL; `Plugin.cs` registers `(ObjectCreationList, 0x683D4DE5u, …)` for
  ours. The two differ → mismatch.
- `ObjectCreationList` is byte-exact vs **retail** EA (`docs/reference/COVERAGE.md`), so our bytes are correct
  retail bytes — the drift is SI-vs-retail, not us-vs-EA.
- Recovery: `openwrath mod revert SecondIsomer` (pristine) → re-bake all five mods with the OCL insert removed →
  game loads; the avatar's `GameObject`/`WeaponTemplate` inserts re-applied without issue.

## The real reliability gap (what let a crash-on-load big ship)

`mod bake` verifies the repacked big is **not truncated** (`big_is_complete`, finding
[0007](0007-big-repack-must-be-fsynced-and-verified.md)) — but it does **not** verify **schema-hash consistency**.
So a structurally-complete big that the engine rejects on load passed every gate. A truncated big can't ship; a
schema-incoherent one still could. That asymmetry is the bug.

## How to fix (directions)

1. **Pre-install guard (do first — catches the whole class):** before repacking, for each *inserted* asset, look
   up the target stream's existing entries with the same TypeId. If any exist and their TypeHash ≠ the asset's,
   **abort the bake** with a precise message (`type <name> (0x…): stream uses 0x8b85f295, compiler emits
   0x683d4de5 — schema drift; cannot insert`). Turns a crash-on-launch into a bake-time error. Pure win,
   independent of #2.
2. **Adopt-the-stream-hash insert (to actually ship the OCL):** when the target stream already has that type,
   stamp the new entry's TypeHash with the **stream's** value (`0x8b85f295`) instead of the compiler's. This is
   sound **iff the on-disk layout is identical and only the schema-doc fingerprint drifted** — which the
   engine-fixed-format premise (plan, Phase 5) predicts, but which must be **verified in-game** before trusting
   (insert one OCL with the adopted hash; confirm load + correct behaviour). If layout *also* differs, adopting
   the hash is unsafe and the insert needs SI's actual layout — escalate to a schema-version-aware emit.
3. **Record the divergence:** keep a small per-stream `TypeId → observed TypeHash` map (read from the stream
   itself) so the guard and the adopt-path are driven by *measured* facts, not assumptions.

## How to apply (today, until the fix lands)

- **INSERT only types the target stream shares with retail** (verified so far: `WeaponTemplate`, `GameObject`).
  For `ObjectCreationList` into an SI-derived stream, don't insert yet.
- Prefer **REPLACE** wherever possible — it's immune to this by construction.
- If a new unit ability needs a new OCL, either (a) wait for the adopt-hash fix, or (b) reuse a stock OCL already
  present in the stream (what the commando now does: single `OCL_GDICommandPostRadarScanPing`, pure replace).

## Resolution — what we built, and a deeper truth about the drift

**Tooling shipped (modkit):**

1. **`openwrath schema [--drift-only] [--type T]`** — prints every type in a stream with its schema hash, our
   compiler's native hash, and a status (`match` / `DRIFT` / `unregistered` / `MIXED`). This is the
   observability the project is for: you can now *see* a stream's schema instead of discovering drift by crash.
2. **Bake-time drift guard** — `mod bake` refuses to install when an INSERT would introduce a hash the stream
   doesn't use for that type, with a precise message (verified: converts the crash-on-load into a clean abort,
   nothing installed). `big_is_complete` catches truncation; this catches schema-incoherence.
3. **`mod bake --adopt-schema`** (+ `insert_asset.py --type-hash`) — opt-in: stamp the new entry with the
   *stream's* hash for that type instead of the compiler's, so an insert can match a drifted stream.

**The bigger reveal: Second Isomer drifted on 12 types, not one.** `openwrath schema --drift-only` on SI's
`static_mod`: `DamageFX, ExperienceLevelTemplate, FXList, LogicCommand, Mouse, MultiplayerColor,
ObjectCreationList, PhaseEffect, RadiusCursorLibrary, SpecialPowerTemplate, UpgradeTemplate, Weather`. The types
we have always modded safely (`GameObject`, `WeaponTemplate`, `LogicCommandSet`) are **not** drifted — which is
exactly why every mod before the OCL insert worked.

**Drift comes in two flavors, and `--adopt-schema` is only sound for one:**

- **Hash-only drift** — same on-disk layout, different schema *fingerprint*. Our decompiler (which walks the
  *retail* layout) reads these instances **cleanly** (observed: `UpgradeTemplate` → `<UpgradeTemplate …>`), so our
  compiled bytes are layout-correct and adopting the stream's hash is safe.
- **Layout drift** — the schema's actual structure changed. Our decompiler **desyncs** to `RawAsset` (observed:
  `ObjectCreationList` `len 28 past instance end (0)`, `SpecialPowerTemplate` `len 1020 …`, `LogicCommand`
  `len 24 …`). For these, our compiler can't produce correct bytes for the drifted stream at all — so **both
  INSERT (even with `--adopt-schema`) and REPLACE are unsafe**: adopting the hash just stamps a correct label on
  wrong-layout bytes.

**The discriminator is free:** our decompiler reads *retail* instances of every registered type (the COVERAGE
roundtrip proves it), so if `openwrath inspect` reads a **drifted** instance cleanly, the drift is hash-only
(adopt-safe); if it desyncs, it's layout drift (adopt-unsafe). This also **subsumes finding
[0009](0009-decompiler-logiccommand-instance-read-desync.md)**: the `LogicCommand` "desync" was never a plain
model bug — `LogicCommand` is a layout-drifted type in SI, so the decompiler was reading it against the wrong
schema. Non-drifted types read fine from the very same stream.

**Consequence for the radar burst:** `ObjectCreationList` is layout-drifted in SI, so the 9-ping burst (a new
OCL) cannot be produced correctly by our retail-schema compiler for SI — `--adopt-schema` would not save it. The
commando keeps the single stock scan (pure REPLACE of a non-drifted `GameObject`, referencing an OCL already in
the stream). Authoring OCL *content* for SI would require SI's OCL schema — a future, schema-version-aware path.

**Follow-on ideas (not built):** a `schema --probe` that decompile-tests each drifted type and labels it
hash-only vs layout drift automatically; and teaching `--adopt-schema` to refuse layout-drift types (probe first)
rather than trusting the operator.

## See also

- Plan, **Phase 5** (foreign-mod robustness / schema-version check) — this is that check, promoted from "nice to
  have" to "required before insert."
- `modkit/lib/insert_asset.py` (where the new entry's TypeHash is written),
  `modkit/openwrath` (`cmd_mod_bake`, where the pre-install guard belongs, next to `big_is_complete`).
- `XmlCompiler/Plugin.cs` type registry (our native per-type hashes).
- `docs/reference/COVERAGE.md` (OCL byte-exact vs retail — why this is drift, not a compiler bug).
