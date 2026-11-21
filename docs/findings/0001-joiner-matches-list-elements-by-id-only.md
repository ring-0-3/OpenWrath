# 0001 — The node-joiner matches override list elements by `id` only

**Status:** Verified · 2026-11-20

## Context

When you override or extend an asset with `inheritFrom` (or an `xi:include` override), the compiler merges your
element into the base element. For a repeated child (a *list* element — many per parent), the joiner has to
decide *which* base child your override corresponds to, so it can replace, remove, or recurse into it.

## Finding

**The joiner identifies "the same" child only by an `id` attribute.** A list element keyed by any *other*
attribute has no `id`, so the joiner never finds a match — and it **appends** your element as a new one instead
of replacing the base child. This happens **regardless of `xai:joinAction`**: `Overwrite`/`Replace`/`Remove`
all run *after* the match step that already failed, so on a non-`id`-keyed element they are effectively no-ops
(for `Overwrite`/`Replace` you get a duplicate; for `Remove` you get a "attempts to remove non-existent node"
warning and nothing is removed).

Concretely:
- `LocomotorSet` is keyed by `Condition` (not `id`) → cannot be replaced via override; it appends.
- `WeaponSlotHierarchicalTurret` is keyed by `ID` (capital — a different attribute than `id`) → appends. This
  is actually *useful*: it's how you add new weapon slots to a unit without disturbing the inherited ones.
- Behaviour modules **do** carry `id` (e.g. `WeaponSetUpdate id="ModuleTag_WeaponSetUpdate"`) → they match and
  the joiner **recurses into the matched module**, so you can merge new children into an existing module.

## Evidence

`source/BinaryAssetBuilder.Core/BinaryAssetBuilder/Core/SageXml/NodeJoiner.cs`:

- `SelectMatchingKey` compares **only** the `id` attribute of candidate vs. source.
- `SelectSame` / `ReplaceXmlNode` (the `idMatchRequired` path): when no match is found, `AppendCorrespondedXmlNode`
  adds the node rather than replacing.
- `JoinAction` enum: `Append=0`, `Overwrite=Override=Replace=1`, `Remove=2` — and the remove/overwrite branches
  only fire *after* a match is found.

This is a faithful port of EA's BAB behaviour, confirmed by decompiling a baked unit and seeing both the
inherited and the appended sets present.

## How to apply

To change a non-`id`-keyed list element you **cannot** cleanly replace it via `inheritFrom`. Choose one:

1. **Append and rely on resolution order.** Add your element; the engine picks one per key. See
   [0004](0004-locomotorset-resolution-is-per-condition.md) for the (hypothesised) last-wins rule for
   `LocomotorSet`.
2. **Override the referenced *template* instead.** e.g. rather than swapping a unit's `LocomotorSet`, edit the
   `Locomotor` template it points at — but check whether that template is **shared** (editing a shared template
   affects every unit that references it).
3. **Redefine the object without `inheritFrom`** (rarely worth it — you lose all the base content).

Do **not** try to "fix" the joiner to key by `Condition`/`ID`: that changes *every* inherit/override merge in
the whole dataset and would silently break byte-exact fidelity elsewhere. See the global-change caution in the
project notes.

## See also

- [0002](0002-insertposition-top-is-parent-scoped.md) — why you also can't reorder an appended element to the top.
- [0004](0004-locomotorset-resolution-is-per-condition.md) — the resolution rule that makes append-last work.
