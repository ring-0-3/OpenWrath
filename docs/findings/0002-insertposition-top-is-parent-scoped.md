# 0002 — `insertPosition="Top"` prepends to the whole parent, not to the sibling group

**Status:** Verified · 2026-11-20

## Context

Having learned that a non-`id`-keyed override element **appends** ([0001](0001-joiner-matches-list-elements-by-id-only.md)),
a natural next move is to force the appended element *earlier* than the inherited ones with
`xai:insertPosition="Top"` — e.g. to make it win a first-match resolution.

## Finding

**`insertPosition="Top"` inserts the new node at the very beginning of the *parent element's* child list — not
at the top of the run of same-named siblings.** So a `LocomotorSet` with `Top` inside a `GameObject` is placed
*before* `DisplayName`, `Draws`, everything. Because the `GameObject` content model is an ordered
`xs:sequence` with required earlier elements, this produces an **XSD sequence-order validation error**, e.g.:

```
The element 'GameObject' has invalid child element 'DisplayName'.
List of possible elements expected: 'LocomotorSet, Buildable, ThingClass, ... Behaviors, AI, Body'.
```

(The parser, having accepted a `LocomotorSet` first, now refuses the later `DisplayName` that the schema wanted
*before* any `LocomotorSet`.)

## Evidence

`NodeJoiner.AppendCorrespondedXmlNode` — the `Top` branch resolves to `parentNode.InsertAfter(node, null)`,
which prepends to the parent. Reproduced: adding `xai:insertPosition="Top"` to a `LocomotorSet` override made a
previously-compiling unit fail validation with the error above; removing it fixed the compile.

## How to apply

- Don't use `Top` to reorder *within* a sibling group — it isn't group-scoped.
- If you need the appended element to take effect, append it normally (default `Bottom`) and rely on the
  engine's per-key resolution rather than XML order — see
  [0004](0004-locomotorset-resolution-is-per-condition.md).
- When adding children to an order-sensitive parent, keep them in schema order — see
  [0003](0003-gameobject-child-order-is-a-schema-sequence.md).

## See also

- [0001](0001-joiner-matches-list-elements-by-id-only.md), [0003](0003-gameobject-child-order-is-a-schema-sequence.md).
