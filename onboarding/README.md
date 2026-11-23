# Onboarding — getting a feel for the codebase

This directory is for people who want to go from "I cloned the repo" to "I made a real change" — by **doing**,
not just reading. OpenWrath's whole reason for existing is that the knowledge to work on this game shouldn't be
gatekept, and that applies to the toolchain itself: you should be able to pick it up and start contributing
without being in anyone's inner circle.

The fastest way in is three stages, in order. Each one makes the next feel obvious.

## 1. Understand the shape (read)

Build a mental model of how Kane's Wrath stores its data and how OpenWrath takes it apart and puts it back
together. Read the concept path in order — no prior modding experience assumed:

- [`docs/01-the-big-picture`](../docs/01-the-big-picture/README.md) — the one problem the toolchain solves.
- [`docs/02-asset-streams`](../docs/02-asset-streams/README.md) — what a compiled "stream" actually is (closer to
  a linked `.so` than a byte stream), and how relocations work.
- [`docs/03-the-authoring-xml`](../docs/03-the-authoring-xml/README.md) — the human-readable XML you write.
- [`docs/04-references-and-the-import-graph`](../docs/04-references-and-the-import-graph/README.md) — how assets
  link across streams, and why a mod is an overlay on the base game.

## 2. Use it (drive the tool)

You understand a tool far better once you've *driven* it. Set up the modkit and make a tiny mod end-to-end —
`find → inspect → author → bake → verify → revert`:

- [`modkit/README.md`](../modkit/README.md) — start with `openwrath init`, then the quickstart. Change one value
  on one unit, bake it, see it in game, revert it. That single loop teaches more than a day of reading.

## 3. Make a change (contribute)

Now change the toolchain itself. This walkthrough has you add two real commands to the modkit and, more
importantly, learn the **pattern** for adding any command — so afterwards the plumbing is boring and your energy
goes to the actual problem:

- [`adding-a-modkit-command.md`](adding-a-modkit-command.md) — build `mod new` + `mod add`, step by step. Every
  command in it was run for real first; it even flags the one bug you'll hit, so you learn *why* the code is
  shaped the way it is.

## The philosophy, briefly

Building or using something first and understanding it deeply second is a completely legitimate order — what
matters is that you end up able to **own** it: to maintain it, extend it, and notice what's wrong. These guides
exist to get you there fast. If a doc leaves you confused, that's a bug in the doc — say so, and it gets fixed
(that's literally how chapters here got written).

When you contribute: keep changes **verified** (the round-trip harness / the test suite are the proof, not
assertion), keep docs **honest** about what's known vs. inferred, and favor code and docs that *teach* the engine
rather than gatekeep it.
