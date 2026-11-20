# 1 · The big picture

> **You'll understand:** the single problem OpenWrath exists to solve, and the three parts that solve it.

## The one problem

Command & Conquer 3: Kane's Wrath runs on the **SAGE engine**. Everything in the game — every unit, structure,
weapon, armor type, visual effect, sound — is defined by *data*, and the engine loads that data as **compiled
binary**. Binary is fast for the engine to load, but it's unreadable and un-editable for a human.

Humans, meanwhile, author game data as **XML** — readable text files that describe an object and its
properties.

So there's a gap:

```
   human-friendly                         engine-friendly
   ┌───────────┐                          ┌───────────────┐
   │    XML     │   ← ? how do we cross →  │ compiled binary│
   └───────────┘                          └───────────────┘
```

Modding is, at its core, the act of **crossing that gap in both directions**:

- To *create or change* game data, you need to go **XML → binary** (so the game can load your changes).
- To *read or edit existing* game data you don't have the source for — the base game, or someone else's mod —
  you need to go **binary → XML** (so you can see and understand it).

OpenWrath is the bridge across that gap, both ways, plus the tooling to get at the files the binary lives in.

## The three parts

### 1. The compiler — `BinaryAssetBuilder`  (XML → binary)

Give it an XML asset definition (say, a tank: its health, weapons, armor, behavior); it produces the exact
compiled bytes the engine loads. Its defining property is that it is designed to be **byte-faithful to EA's own
compiler** — reproducing the shipped bytes exactly, which the project *measures* type by type rather than
assuming (see the coverage matrix). It's how your *edits* become something the game can actually run.

### 2. The decompiler — `bab-decompile`  (binary → XML)

The inverse. Give it compiled game data; it reconstructs the readable XML. This is how you **open up** content
you have no source for — the base game, or a third-party mod. Crucially it's **lossless**: because it reuses the
exact same internal data layout as the compiler, its XML is designed to recompile to *identical* bytes. (More
on why that's possible, and why it's hard, in later chapters.)

### 3. The archive & stream tools — `pytools`

The compiler and decompiler each work on a single compiled **stream** (the next chapter is entirely about what
that is). But the game doesn't ship loose streams — it ships them packed inside **`.big` archives**, often
compressed. The `pytools` scripts handle everything *around* an asset: unpacking and repacking `.big` archives,
decompressing EA's RefPack, and splicing an edited asset back into a stream so it stays valid. They're the glue
that gets your work *into the actual game files* and back out.

## How a real edit flows through all three

```
.big archive ──unpack / decompress──▶ compiled stream        (pytools)
compiled stream ──decompile──────────▶ XML                    (bab-decompile)
        ✎ edit the XML
XML ──compile────────────────────────▶ compiled asset         (BinaryAssetBuilder)
compiled asset ──splice into stream──▶ updated stream         (pytools)
updated stream ──repack──────────────▶ new .big               (pytools)  → the game loads it
```

And underpinning all of it is the **round-trip test** (`tools/roundtrip.sh`): decompile something, recompile
it, and prove the bytes came out identical. That's what makes the toolchain *trustworthy* rather than hopeful —
a theme you'll see throughout.

---

Next: [2 · Asset streams](../02-asset-streams/README.md) — what that "compiled stream" actually is, and why
it behaves far more like a linked executable than like a flowing stream of bytes.
