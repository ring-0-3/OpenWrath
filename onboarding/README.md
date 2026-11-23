# Onboarding — getting a feel for the codebase

This directory is for people who want to go from "I cloned the repo" to "I can work on this," by **doing**, not
just reading. OpenWrath exists so the knowledge to mod this game isn't gatekept — and that applies to the
toolchain itself. You should be able to pick it up and start contributing without being in anyone's inner circle.

The path is three stages, in order. Each makes the next feel obvious.

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

## 3. Practice (build something) — *in development*

The last stage is a growing set of **practice exercises**: small, self-contained things you build and attach to
the codebase, so you learn the patterns by writing code, not just reading it. The point isn't to ship a specific
feature — it's to get the *feel* of the codebase, so later your energy goes to the problem, not the plumbing.

Planned:

- **A sequence of guided exercises** — each builds a small, pluggable addition against the real code and its
  tests, with a worked solution to check against. (The first, "add a modkit command," exists as a standalone
  walkthrough; as `mod new` / `mod add` land as real features, the exercises move to additions that *don't*
  overlap the core, so each onboardee can do their own.)
- **A practice harness** — a tool that reproduces the codebase with one chosen part removed, so you can try
  *reimplementing* a real piece (a command, a renderer, a container parser) against the existing tests, in
  isolation. Re-deriving real code is one of the fastest ways to truly own a subsystem.

Want to help shape this? Opening an exercise you wish had existed when you started is a great first contribution.

## The philosophy, briefly

Building or using something first and understanding it deeply second is a completely legitimate order — what
matters is that you end up able to **own** it: to maintain, extend, and notice what's wrong. These guides exist
to get you there fast. If a doc leaves you confused, that's a bug in the doc — say so, and it gets fixed (that's
literally how the concept chapters here got written).

When you contribute: keep changes **verified** (the round-trip harness / the test suite are the proof, not
assertion), keep docs **honest** about what's known vs. inferred, and favor code and docs that *teach* the engine
rather than gatekeep it.
