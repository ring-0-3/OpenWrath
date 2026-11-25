# 0005 — Overrides must be spliced into the target's single stream

**Status:** Verified · 2026-11-20 · **refined by [0017](0017-overlay-mod-overrides-base-gameplay-the-complete-recipe.md) (2026-11-25)**

> **Refinement (0017):** "a separate override stream has no effect / is never consulted" is true *only* for a stream
> that isn't activated. A separate **overlay** stream **IS** consulted if it (a) is a proper differential (complete
> entry list, data for changes, `\x02` defer-to the base), and (b) is activated by a **`.version` redirect file**
> (`data\<family>.version` = the postfix) that makes it THE stream the engine loads for that family. In other words:
> the activated overlay *becomes* "the one stream that owns" the family — so this finding's rule still holds, it just
> has a second way to satisfy it (a `.version`-activated overlay chain, not only an in-place splice). Still true: only
> **one** stream owns a family at a time, so two overlay mods are mutually exclusive and must be merged. Full recipe
> in 0017.

## Context

The intuitive way to mod is to ship your changed assets as a *separate* stream/package "on top of" the base
game or an existing mod, expecting them to override. They don't.

## Finding

**The modded assets must live in the *same single linked stream* that already carries the assets you're
changing.** A separate override stream has no effect — the engine resolves an asset from the one stream that
owns it, so your copy in a different stream is simply never consulted. To change an asset you must **splice**
your compiled asset into that owning stream (replacing the instance in place), then repack the `.big`.

This is why a mod built on top of another mod (e.g. one whose data lives in its `static_mod` stream) has to be
baked **into that mod's `static_mod` stream**, not alongside it — and why everything for one mod ends up as a
single combined bake, not a stack of independent override packages.

## Evidence

- Observed directly: a separate override mod produced no in-game change; splicing the same compiled assets into
  the target's stream did.
- `openwrath mod bake` automates exactly this: compile all your overrides as one source → splice each resulting
  asset into the target stream by instance id → repack the `.big` (with an automatic backup).

## How to apply

- Put **all** of a mod's overrides in one source compile and bake them into the **one** target stream.
- Don't try to layer multiple mods as separate streams expecting later ones to win — combine them into the one
  stream you're shipping.
- `openwrath mod bake <project-dir>` does the splice; `openwrath mod revert <target>` restores the backup.

## See also

- `../../modkit/README.md` — the bake/revert workflow.
