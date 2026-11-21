# Design: multi-schema interoperability

**Status:** Proposed (design sketch) · 2026-11-21

> How OpenWrath can read and author data for mods built against **different schema versions** than retail
> Kane's Wrath — faithfully, verifiably, and without shipping anyone's content.

## Summary

OpenWrath today assumes a single schema: retail Kane's Wrath, the layout its compiler reproduces byte-exact. But
real community mods are often built against a *different* schema version — same types, different on-disk layout.
This document proposes making OpenWrath **schema-aware**: a default schema plus an additive registry of known
variants, each a layout description OpenWrath *authored by observation* and *proved* byte-exact, with a
contribution path for new ones. The result is genuine ecosystem interop (the [VISION](../../VISION.md) goal of
being "built to be built on") built on descriptions we own and zero redistributed content.

## Background: schema drift

Every compiled asset entry carries a **TypeId** (which type) and a **TypeHash** (a fingerprint of that type's
*schema*). The engine requires one TypeHash per type across a loaded stream. A mod built against a different
schema version carries a different TypeHash — and sometimes a different byte layout — for a type. We hit this
concretely (see [findings 0009](../findings/0009-decompiler-logiccommand-instance-read-desync.md) and
[0010](../findings/0010-insert-must-match-target-stream-type-schema-hash.md)):

- `openwrath schema --drift-only` on the *Second Isomer* mod shows **12 types** whose hash differs from retail:
  `DamageFX, ExperienceLevelTemplate, FXList, LogicCommand, Mouse, MultiplayerColor, ObjectCreationList,
  PhaseEffect, RadiusCursorLibrary, SpecialPowerTemplate, UpgradeTemplate, Weather`.
- The types we have always modded safely (`GameObject`, `WeaponTemplate`, `LogicCommandSet`) are **not** drifted.

Drift comes in **two flavors**, and OpenWrath can already tell them apart for free (our decompiler reads every
*retail* type, so its behaviour on a *drifted* instance is diagnostic):

- **Hash-only drift** — same layout, different fingerprint. Our reader reads it cleanly (`UpgradeTemplate`). Safe
  to author by adopting the stream's hash.
- **Layout drift** — the structure actually changed. Our reader desyncs to `<RawAsset>` (`ObjectCreationList`,
  `SpecialPowerTemplate`, `LogicCommand`). Our retail-schema compiler **cannot** produce correct bytes for these,
  so neither insert nor replace is safe without the variant's real layout.

## Goal & non-goals

**Goal.** Let OpenWrath read, verify, and author data for streams built against schemas other than retail —
starting with *reading* (interop) and extending to *authoring* where a variant's layout is known and validated.

**Non-goals.** Shipping any mod's or EA's content, schema files, or data (unchanged from the project's standing
posture). A push-button "understand any unknown schema automatically" — that's research; we aim for a
*semi-automatic* derive-and-verify workflow with a human confirming via a decidable check.

## Architecture

### 1. A TypeHash-keyed layout registry

Today the registry maps **TypeId → layout** (one layout per type). The change is to map **(TypeId, TypeHash) →
layout**:

- A type may have several registered layouts, selected per asset by the **stream's** TypeHash.
- Retail hashes → our existing retail layouts (the `SageBinaryData` structs — unchanged).
- A variant's hashes → that variant's layout, loaded from a **data-driven table**, not more hard-coded structs.
- Unknown hash → the existing graceful path (`<RawAsset>`), now also *inviting a contribution* (below).

This is deliberately **additive**: adding variant support changes nothing about retail support. (The decompiler
plan anticipated this — "keep the registry TypeHash-keyed so a second schema version is additive future work, not
a rewrite.")

### 2. Variant layouts as data, not code

A variant layout is a description OpenWrath loads at runtime — field order, types, sizes — e.g.:

```
schemas/
  retail-kw/                     # the default: our structs / XSD (provenance-gated, bring-your-own)
  variants/
    second-isomer/
      ObjectCreationList.layout  # OUR authored layout table, derived by observation + validated
      _PROVENANCE.md             # how it was derived; attests it ships no SI content
      _STATUS.md                 # per-type: verified byte-exact | experimental, with receipts
```

Keeping layouts as data makes the registry community-extensible without recompiling, and keeps each variant's
provenance and verification status next to it.

### 3. Selection & degradation at runtime

- On read/write, for each asset look up `(TypeId, TypeHash)`; use the matching layout.
- Known retail hash → retail layout. Known variant hash → variant layout. Unknown → labeled raw block + a
  message pointing at the contribution flow. **Never crash, never silently wrong** (the VISION "honest about its
  limits" value).
- `mod bake` already **guards inserts** against drift it can't honor and offers `--adopt-schema` for the
  hash-only case; with a registered variant layout, a layout-drift insert becomes a *supported* operation.

## Deriving a variant schema (no schema ships, so we derive one)

Mods generally don't ship their schema (Second Isomer ships only `.big` archives). So OpenWrath must **derive** a
layout description from observation. Two levers make this tractable and *honest*:

1. **A byte-exact retail oracle.** Our compiler/decompiler reads every retail type perfectly — a reference layout
   to diff against. Drift is almost always "retail + a few fields moved/added," not a ground-up redesign.
2. **Decidable correctness.** `tools/roundtrip.sh` byte-compares a recompile against the original. Any candidate
   layout can be *proven*: decompile all of a variant's instances of a type with it → recompile → byte-match.

### The paired-asset "Rosetta" method

Many stock assets exist in **both** retail (`static_common`) and a mod (`static_mod`) with identical semantics —
same InstanceId, unchanged by the mod, merely recompiled under its schema (e.g. `OCL_GDICommandPostRadarScanPing`
appears in both). For such a pair we can align:

- **known field *values*** — decompile the retail copy (the oracle handles it), against
- the variant's **raw bytes** for that same asset, plus free structural hints: the `.relo` list marks pointer
  slots, `.imp` marks asset-ref slots, the manifest gives total instance size.

With enough paired assets, the variant's field offsets/order are recoverable — especially as retail-plus-deltas.
Then **validate** across every instance of the type (byte-exact or it isn't accepted).

### Honest limits of derivation

- **Semi-automatic, not magic.** The tool proposes a layout; the round-trip gate confirms it; a human curates.
- **Structurally-invisible drift** (enum-value remapping, default changes) won't show in layout alignment and
  needs semantic probing.
- **Types a mod rewrote everywhere** lack paired assets and fall back to harder pure inference.
- A variant layout is only ever published **after** it round-trips byte-exact on that variant's own data; until
  then it's marked `experimental`.

## Content policy

Multi-schema support follows the same policy as the rest of OpenWrath — interop tooling, bring your own data,
ship no content:

1. **OpenWrath authors its own descriptions.** We do not copy anyone's schema or SDK files (mods generally ship
   none). A variant layout table is *derived by observing data* and written as our own description — OpenWrath's
   own work product.
2. **Zero content redistribution.** The repo ships *descriptions*, never anyone's streams, assets, or files.
   Contributors bring their own data; the toolchain reads it locally. A variant folder carries a layout table +
   provenance + status, nothing of the mod itself.
3. **Credit and provenance.** Each variant records how it was derived and whose data format it interoperates with,
   named plainly.

The clean design is also the simpler one: derived-not-copied, descriptions-not-content, bring-your-own-data,
validated-and-credited.

## The model: default + supported + "talk to us to add yours"

- **Default:** OpenWrath assumes **retail Kane's Wrath**.
- **Supported variants:** a registry of known schemas, each a validated, credited layout table. `openwrath
  schema` labels a stream's hashes `match` (default) / `<variant> (supported)` / `unknown`.
- **Unknown schema → a real contribution path** (proposed addition to [CONTRIBUTING](../../CONTRIBUTING.md)):
  "your stream uses a schema OpenWrath doesn't know — run `openwrath schema --probe` and open an issue." The
  contributor supplies
  **their own** sample streams (not redistributed in the repo); the derive-and-verify harness produces the layout;
  a maintainer confirms it byte-exact and adds the **derived table** to `schemas/variants/`. The repo accrues a
  credited library of formats it interoperates with, carrying no one's content.

Every variant wears its status honestly, the way COVERAGE/findings already do: `verified byte-exact` vs
`experimental`, with the validation receipts.

## Effort & phasing

| Phase | What | Rough effort |
|---|---|---|
| **0. Identify** | Is a drifted hash a *known* schema variant (a KW patch, a mod-SDK schema)? If so, register its layout directly. | hours to check |
| **1. Observe** | `openwrath schema --probe`: classify each drifted type hash-only vs layout, and dump the recoverable skeleton (size + annotated pointer/ref slots + hexdump) for layout-drift types. | ~days |
| **2. Derive harness** | The paired-asset Rosetta aligner + round-trip validation, reusable across all types; variant layouts as loadable data. | ~1–2 weeks |
| **3. Per-type solve** | Run the harness on a target type (e.g. `ObjectCreationList`), fix edge cases, prove byte-exact, publish the table. | hours–days each |
| **4. Registry + contribution** | `schemas/variants/` layout, `schema` labeling, the CONTRIBUTING flow, graceful-unknown invites. | ~days |
| **(stretch) Fully automatic** | Zero-human inference for arbitrary foreign streams. | open-ended / research |

## What already exists (the groundwork)

- **`openwrath schema [--drift-only] [--type T]`** — sees a stream's per-type hashes and flags drift vs our
  compiler. (Revealed the 12 SI-drifted types.)
- **Bake-time drift guard** — refuses to install a drifting insert with a precise message, instead of shipping a
  crash-on-load archive (verified).
- **`mod bake --adopt-schema`** (+ `insert_asset.py --type-hash`) — the hash-only-drift authoring path.
- **The decidable validator** — `tools/roundtrip.sh` (closed-loop + `--from-binary` ground-truth), the
  acceptance test every derived layout must pass.
- **Findings [0009](../findings/0009-decompiler-logiccommand-instance-read-desync.md) /
  [0010](../findings/0010-insert-must-match-target-stream-type-schema-hash.md)** — the drift discovery, the two
  flavors, and the discriminator.

## Open questions

- Do SI's drifted hashes match any *known* schema version (Phase 0), or are they genuinely SI-specific?
- Does `ObjectCreationList` have enough retail↔SI paired assets for the Rosetta method to converge?
- Layout-table format: reuse a subset of the XSD shape, or a purpose-built compact schema description?
- How to represent structurally-invisible (semantic) drift when we hit it.

## See also

- [VISION.md](../../VISION.md) — "built to be built on"; interop as a first-class goal.
- [ROADMAP.md](../../ROADMAP.md) — Platform & extensibility.
- [docs/reference/COVERAGE.md](../reference/COVERAGE.md) — the per-type fidelity matrix (retail schema today).
