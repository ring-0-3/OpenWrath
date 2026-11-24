# 0014 — Runtime W3DAnimation channel dispatch depended on a schema-stamped TypeId that the authoring schema can't supply

**Status:** Resolved (verification pending clean set) · 2026-11-24

> About **our own tools** (the W3X runtime marshaler + the decompiler), turning on one fact about BAB: how the
> compiler learns a polymorphic child's TypeId. Discovered while remediating [0013](0013-byo-schema-edited-in-place.md)
> (the in-place schema widening). It is the *downstream consequence* of fixing 0013 correctly.

## Context

A Kane's Wrath `W3DAnimation` ships in its compressed **runtime** form. The decompiler emits it as
`<W3DAnimation>` (the element must stay `<W3DAnimation>` — its name drives the asset TypeHash `0xCC069193`),
with per-bone `<Timecoded>` / `<Delta>` channels (the shipped pre-compressed form). The compiler recognizes this
form (`Marshaler.IsRuntimeAnimation`) and writes the channels straight back, byte-for-byte.

The runtime marshaler dispatches each channel by reading a **`TypeId` attribute**
(`Marshaler.W3DRuntime.cs`: `switch (ParseUInt(ch.GetAttributeValue("TypeId", "0")))`). The *authoring* channel
marshalers read the same attribute (`Marshaler.W3D.cs:166`). But the decompiler never emitted a `TypeId`
attribute, and the schema's `AnimationChannelBaseRuntime` declares no such attribute. So where did `TypeId` come
from?

## Finding

**BAB *stamps* the `TypeId` attribute itself**, during instance processing, from each element's **schema-bound
type name** — `AssetDeclarationDocument.cs:1048`:

```csharp
if (navigator.SchemaInfo?.SchemaType?.Name is not null)
    navigator.CreateAttribute(..., "TypeId", ...,
        HashProvider.GetCaseSensitiveSymbolHash(navigator.SchemaInfo.SchemaType.Name).ToString(...));
```

For `<Timecoded>` bound to schema type `AnimationChannelTimecoded`, the stamp is
`GetCaseSensitiveSymbolHash("AnimationChannelTimecoded")` = `0x60D8CF69`; for `<Delta>` → `AnimationChannelDelta`
→ `0x77F97305`. **The stamp only happens when the element is schema-bound** (`SchemaInfo.SchemaType` non-null).

The art pillar's byte-exact result was obtained **while the authoring `W3DAnimation`'s `<Channels>` choice had
been widened in place to include `<Timecoded>`/`<Delta>`** (the 0013 boundary violation). That widening is what
bound those elements to their schema types, which is what produced the stamp, which is what fed the marshaler's
dispatch. Reverting the widening (correct, per 0013 and the BYO-read-only invariant) removed the binding → no
stamp → the marshaler reads `"0"` → `default` branch → `"Unknown runtime animation channel TypeId 0x00000000"`.

**So relaxing the validation error alone (the obvious reading of the runtime-form fix) is necessary but *not
sufficient*: a runtime channel under an authoring `<W3DAnimation>` is outside that content model, never gets a
schema-stamped TypeId, and the recompile fails regardless of whether its validation error was suppressed.**

## How it was fixed — bind the runtime channels, in code (not by editing a BYO file)

First attempt (relax validation + have the decompiler emit the channel's own `TypeId`) proved the point but is
**abandoned**: validation is not the only consumer of schema binding. The per-descendant instance-processing
loop (`HandleReferenceType`) throws `Critical: Element Timecoded ... doesn't have a schema type` because
reference resolution, instance hashing, and the `TypeId` stamping all require every element to be bound. Binding
is load-bearing across the whole pipeline, so a runtime channel *must* be schema-bound — relaxing validation
cannot substitute for that.

The chosen fix binds the runtime channels using **EA's own already-defined types**, in OpenWrath's code, before
the schema compiles — **`SchemaSet.BindRuntimeAnimationChannels()`**. EA's schema already declares
`AnimationChannelTimecoded` / `AnimationChannelDelta` (the channels of the `W3DAnimationRuntime` type); it simply
does not reach them from the authoring `W3DAnimation`'s `<Channels>` choice. We add that reach in memory:

- Locate the `W3DAnimation` complex type; add `<Timecoded>`/`<Delta>` element particles (→ EA's
  `AnimationChannelTimecoded`/`Delta`) to its `<Channels>` choice, **before `Schemas.Compile()`**.
- The runtime channels are now schema-bound, so the entire normal pipeline works through them — validation,
  `HandleReferenceType`, instance hashing, and the existing `TypeId` stamping (which stamps `0x60D8CF69` /
  `0x77F97305` from the bound type name and drives the marshaler's dispatch). The asset element stays
  `<W3DAnimation>` (TypeHash `0xCC069193` unchanged).

This reuses EA's own types, invents nothing, and **never edits a bring-your-own schema file** (CLAUDE.md
invariant 1 — "additions live in owned files or *in code*"). It reproduces the exact mechanism that produced the
original byte-exact result (the in-place widening did the same thing to the same type), but as owned code. It is
**data-shaped** — a `(element, type)` table — and is the *prototype* binding that migrates into the
schema-overlay registry when that exists (ROADMAP). The two first-attempt patches (validation relax; decompiler
`TypeId` emission) were **removed**; the channel byte still comes from the compiler's own constant
(`SageBinaryData.AnimationChannelTypeIds`), so the stamp only drives dispatch, never bytes.

## Verification — byte-exact RESTORED from the pristine schema

- **Builds clean** (`BinaryAssetBuilder.sln`, Debug|x64, 0 errors).
- **W3DAnimation byte-exact vs shipped bytes**, `static_common`, from the **pristine** (un-widened) schema +
  the in-code binding: a reproducible **seed-7 sample of 125/125** recompiles byte-identical
  (`exact=125, sizeok_valdiff=0, sizediff=0`), and all 1792 instances decompile cleanly (`ok=1792, raw=0`).
  Codec coverage confirmed on `ABBHIVE_D2AN` (20 mixed channels), `ABBHIVEDR_CLS` (time-coded only),
  `ABBHIVEDR_OPN` (adaptive-delta only), and `ABGATEWAYFXDIE` (empty channels) — all BYTEEXACT.
- **No data-type regression** from the shared schema augmentation: closed-loop `Armor.xml` 207/207 and
  `Weapon.xml` 456/456 byte-exact. (The augmentation only adds particles to the `W3DAnimation` type.)

## Lessons (project-wide)

- **A green round-trip can depend on an input defect.** The byte-exact pass was real but rested on an in-place
  schema edit; removing the edit removed the result. Exactly the input-integrity blind spot the `inputs.sha256`
  preflight is meant to close — verify inputs, not just outputs.
- **Schema binding is load-bearing, not cosmetic.** "Just relax the validator" was wrong because binding feeds
  reference-resolution, hashing, and dispatch. When a form must round-trip, make it *bound* (reusing EA's own
  types in code), don't paper over the one symptom you happened to see.

## See also

- [0013](0013-byo-schema-edited-in-place.md) — the in-place schema widening whose (correct) removal exposed this.
- [0012](0012-refpack-manifest-detection-only-matches-0x10-variant.md) — same session; duplicated-knowledge dedup
  (the shared `AnimationChannelTypeIds` constants landed with this change).
- `docs/design/verification-blind-spots.md` — §1 coverage / input provenance.
