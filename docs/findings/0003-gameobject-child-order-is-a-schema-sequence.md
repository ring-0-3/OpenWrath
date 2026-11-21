# 0003 — GameObject children are an ordered sequence; `VisionInfo` comes last

**Status:** Verified · 2026-11-20

## Context

An `inheritFrom` override that touches several things (say vision + locomotion + a behaviour) lists several
child elements. The order you write them in is **not free**.

## Finding

**The `GameObject` content model is an `xs:sequence`: children must appear in the schema's declared order**, and
the compiler validates it. An override block whose children are out of order fails validation even though each
child is individually valid. In particular, `VisionInfo` sits **near the very end** — *after* `Body` — which is
surprising if you think of vision as a "basic" property.

Observed canonical order (abridged), from a stock unit:

```
DisplayName → LocomotorSet → SkirmishAIInformation → Draws → Behaviors → AI → Body → … → VisionInfo
```

So an override that writes `VisionInfo` *before* `LocomotorSet` is rejected: the parser, having accepted
`VisionInfo` (late in the sequence), then refuses the earlier-ordered `LocomotorSet`.

## Evidence

- Element line order in a stock unit definition: `DisplayName`, `LocomotorSet`, `Draws`, `Behaviors`, `AI`,
  `Body`, then `VisionInfo` last.
- The `GameObject` complex type in `CnC3Types.xsd` is a sequence.
- Reproduced: a `VisionInfo`-first override failed with an invalid-child/sequence error; moving `VisionInfo`
  after `Behaviors` fixed it.

## How to apply

Order your override's children to match the base definition. A safe pattern for a typical unit tweak:

```
LocomotorSet(s)  →  Behaviors  →  VisionInfo
```

When in doubt, open the stock unit and copy the relative order of the elements you're adding.

## See also

- [0002](0002-insertposition-top-is-parent-scoped.md) — the related trap: `Top` can shove an element out of order.
