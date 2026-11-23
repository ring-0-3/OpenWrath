# 4 · References and the import graph

> **You'll understand:** how assets point at each other — inside a stream and across streams — why cross-stream
> links use **ids** instead of offsets, how a mod loads as an **overlay** on top of the base game rather than a
> replacement, and how to walk the resulting graph with `trace` and `uses`.

## Assets don't live alone

Game data is a web. A unit references its weapons; a weapon references its projectile, its warhead, its fire
FX; those reference sounds and art. Every one of those is a **reference** — one asset pointing at another. Taken
together they form the **reference graph**: assets are the nodes, references are the edges.

Chapter 2 showed the four parts of a stream. This chapter zooms into the edges — because there are two kinds,
and the difference between them is the whole story of how modding works.

## Two kinds of edge

- **Internal edge → relocation.** The target lives in the *same* stream. On disk the field holds an **offset**;
  at load the engine computes `base + offset` (chapter 2). Pure arithmetic, within one blob.
- **External edge → import.** The target lives in a *different* stream. On disk the field holds the target's
  **id** (a hash of its name); at load the engine **looks that id up** in a table of everything loaded and
  patches in the real address.

It's exactly the internal-vs-external symbol split a linker makes:

| | Internal (same stream) | External (other stream) |
|---|---|---|
| On disk | a byte offset | an asset **id** |
| At load | `base + offset` (arithmetic) | id → lookup (symbol resolution) |
| Table | `.relo` | `.imp` |
| Linker analogy | relative fixup | dynamic symbol resolution |

## Why an import *can't* just be an offset

Because the target is in a **separately-loaded blob at its own base**. An offset measured from *your* base would
point into nothing. So the field has to *name* the thing — carry its id — and let the loader find wherever it
actually ended up.

There's a neat consequence worth noticing: **the existence of the import mechanism is itself evidence that
streams don't share one contiguous base.** If every stream sat in one block at one shared base, cross-stream
references could use plain offsets and imports wouldn't need to exist. The fact that they carry ids is the format
admitting "the thing I point at is in a different, independently-loaded blob."

## How an import resolves

1. The `.imp` table lists the **positions** of all the import fields in `.bin`.
2. Each import field holds a target **id** — a `(TypeId, InstanceId)`, where the `InstanceId` is a hash of the
   asset's name.
3. At load time the engine keeps a **global registry of every loaded asset, keyed by id** — its symbol table.
4. For each import: read the id → look it up → write that asset's real address into the field.

**Concretely:** your modded unit still plays the base game's `GDI_MissileSoldier_MissileFire` sound. Your stream
never copies that sound — it just stores the sound's **id** in an import slot. At load, the engine finds the
sound (already loaded from a base stream), and links your unit to it. One id, resolved to one address.

## Streams are overlays: vanilla *and* mod, together

Each stream loads as its own blob at its own base — like several shared libraries each mapped at their own
address. And a mod stream does **not** contain a copy of the whole game. It carries only the assets it **adds or
changes**, and **imports** everything it leaves alone.

This isn't a guess — it's visible in the data. A mod's `.imp` entries reference **base-stream** asset ids, which
is exactly why the toolchain needs the base manifests (`global_common_2`, `static_common_2`, `global_english_2`)
to resolve cross-stream references, and why `openwrath extract-manifests` pulls precisely those. So at runtime the
base-game streams and the mod stream are **both live**, and the mod's import edges reach into the base.

A mod is an **overlay**, not a replacement. That's why a mod can be small, and why the base game must be present
for it to load at all.

## The load path, end to end

```
.big archive  ─▶  read out stream parts + RefPack-decompress
                       │
          for each active stream:  load .bin  ─▶  base address  ─▶  apply .relo (internal fixups)
                       │
          register every asset by id  ─▶  global symbol table
                       │
          resolve .imp:  id → lookup → patch real address
                       ▼
                live, linked game objects (base + mod)
```

## Walking the graph: `trace` and `uses`

The reference graph isn't just a mental model — the tools make it browsable:

- **`openwrath trace <asset>`** walks the **outgoing** edges: *what does this asset depend on?* — unit → weapons
  → projectiles → FX. Internal edges are followed; external ones are shown as imports.
- **`openwrath uses <asset>`** walks the **incoming** edges: *what depends on this?* Run it before editing a
  shared template, so you don't change one weapon and silently alter ten units that import it.

That's the whole point of the project in miniature — the graph laid bare instead of gatekept.

## Why it matters for modding

- You mod by **replacing or overriding nodes.** Edges keep working: imports are by id (they find your replaced
  asset by its unchanged id), internal edges are re-spliced when the stream is rebuilt.
- Because mods are overlays that **import** from the base, editing a *shared* asset affects everyone who imports
  it — `uses` first. See [finding 0005](../findings/0005-mods-must-live-in-one-target-stream.md).
- A brand-new asset must be **reachable** (something has to reference it) and its own references must **resolve**.
  That's why adding an asset of a schema-drifted type, or referencing a base asset that isn't there, fails to
  load — see findings [0006](../findings/0006-new-assets-need-stream-insert.md) and
  [0010](../findings/0010-insert-must-match-target-stream-type-schema-hash.md).

## Honest: what we know vs. what we infer

- **Known** (verified by parsing and byte-exact round-trip of the *data*): the reference structure, that imports
  carry ids, that the manifest keys assets by id, and that a mod like Second Isomer imports from the base streams.
- **Inferred** (the engine's *runtime* behaviour — separate bases, the global id registry, the exact
  allocate → relocate → resolve sequence): strongly grounded — it mirrors every ELF/PE loader and it's the only
  way the data makes sense — but we have **not** instrumented the engine to watch it. OpenWrath reasons from the
  on-disk format and standard loader behaviour, not from a runtime teardown. Treat the runtime picture as
  well-supported inference, not observed fact.

## Recap

- Assets form a **graph**: nodes are assets, edges are references.
- **Internal** edges are relocations (`base + offset`); **external** edges are imports (`id → lookup`) — the
  linker's relative-fixup vs dynamic-symbol split.
- Imports must use ids because other streams load at their **own independent bases** — and that's why imports
  exist at all.
- A mod is an **overlay**: it carries only its changes and **imports** the rest from the live base streams.
- `trace` (outgoing) and `uses` (incoming) make the graph browsable.

---

Previous: [3 · The authoring XML](../03-the-authoring-xml/README.md) ·
Next: *how the decompiler reverses the linking (coming)*
