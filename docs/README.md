# OpenWrath documentation

Everything here is written to be **read in order** if you're new, or dipped into if you're not. The docs are
split by *purpose*, because "understand a concept," "follow a tutorial," and "look up a byte layout" are
genuinely different needs:

- **Understanding OpenWrath** (below) — the concept path. Start here. Read top to bottom to build a mental
  model of how Kane's Wrath stores its data and how OpenWrath takes it apart and puts it back together. No
  prior modding experience assumed.
- **Tutorials** *(coming)* — hands-on, learn-by-doing walkthroughs ("build your first mod").
- **How-to guides** *(coming)* — short task recipes ("change a unit's armor", "repack a `.big`").
- **Reference** *(coming)* — the exact spec: file formats, byte layouts, every flag.
- **[Findings](findings/README.md)** — a dated catalogue of the non-obvious truths we've hit (compiler/schema
  behaviour, how authored data resolves), each with evidence and an honest *verified vs. hypothesis* status.
  Observability over obscurity.
- **[Onboarding](../onboarding/README.md)** — new to the codebase and want to *work on the toolchain itself*? A
  doing-first path: understand the concepts → drive the tool → practice exercises (in development).

## Understanding OpenWrath — the concept path

Read these in order. Each builds on the last.

1. [The big picture](01-the-big-picture/README.md) — the one problem the whole toolchain exists to solve, and
   the three parts that solve it (compiler, decompiler, and the archive/stream tools).
2. [Asset streams](02-asset-streams/README.md) — the central idea: how the game bundles its compiled data, and
   why it's much closer to a linked executable than to a "stream of bytes."
3. [The authoring XML](03-the-authoring-xml/README.md) — the human-readable form you write: the
   `AssetDeclaration` envelope, how `<Includes>` wires files together, and the `inheritFrom` / `xai:joinAction`
   vocabulary that lets a tiny file override a huge asset.
4. [References and the import graph](04-references-and-the-import-graph/README.md) — how assets link within and
   across streams, why cross-stream links use ids, and how a mod loads as an overlay on top of the base game.

*(More chapters will follow — how the decompiler reverses the linking, and then the hands-on tutorials.)*

---

This guide is a work in progress and is written alongside the tooling itself — part of the project's goal is
to make the engine **understandable**, not gatekept. Corrections and additions are welcome.
