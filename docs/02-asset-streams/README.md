# 2 · Asset streams

> **You'll understand:** what a SAGE "stream" actually is, the four parts it's made of, and why it behaves like
> a linked executable rather than a flowing stream of bytes.

## First: unlearn the word "stream"

If you have a programming background, "stream" probably means a *flowing sequence of bytes or packets* you
consume over time — a TCP socket, a file read, a UDP packet stream. **That is not what "stream" means here.**

In SAGE, a **stream is a packaging concept**: a compiled bundle of game assets that are stored and loaded
together. Same word, different world.

The analogy that makes it click:

> **A SAGE asset stream is to game data what a linked object file / shared library (an ELF `.so`, a Windows
> `.dll`) is to code.**

That's not a loose comparison — the structure lines up almost part-for-part.

## What a stream is made of

A Kane's Wrath stream is **four parallel parts** (stored as four files, or four sections):

| Part | What it holds | Executable-format equivalent |
|------|---------------|------------------------------|
| **`.manifest`** | the index — every asset listed with its type, id, name, sizes, and where its data lives | symbol table / section headers |
| **`.bin`** | the actual serialized asset data — every object's bytes, concatenated | the data segment |
| **`.relo`** | relocation table — a list of positions inside `.bin` that hold *internal pointers* | relocation table |
| **`.imp`** | imports table — positions that hold *references to assets in other streams* | import table (dynamic linking) |

Put together, a stream is a **serialized object graph**: a pile of game objects (units, weapons, effects) saved
to disk with their pointer structure preserved.

## The key insight: relocations and imports

Here's the part that rewards a systems background. On disk, a pointer field **cannot** hold a real memory
address — nothing is loaded anywhere yet. SAGE solves this exactly the way an executable loader does.

**Internal pointers → relocations.**
When asset A points to a sub-object that lives in the same stream, the on-disk pointer field doesn't store an
address — it stores a **byte offset**, and the `.relo` table records *"a pointer lives at offset X."* When the
engine loads the `.bin` into memory, it walks the relocation table and patches each of those slots to
`base_address + offset`. This is **literally code relocation** — the same fix-up a loader performs on a shared
library.

**Cross-stream references → imports.**
When asset A references asset B that lives in a *different* stream — a mod unit referencing a base-game weapon,
or any object referencing a shared audio event — the on-disk field stores an asset **id**, and the `.imp` table
records *"an import lives at offset Y."* At load time the engine resolves it against all the other loaded
streams. This is **dynamic-library symbol linking**, applied to game data.

So the engine's load path is:

```
read .bin into memory  →  apply .relo (fix internal pointers)  →  resolve .imp (link to other streams)
                                                                           ↓
                                                                 live game objects
```

And *that* is why it's called a "stream": it's a block of data **streamed into memory and relocated** — a
memory image you load and fix up, not a document you parse field-by-field.

## Why this matters for modding

Second Isomer — a complete overhaul mod — ships its entire contents as **one stream**, `static_mod`, holding
roughly **44,000 assets** packed contiguously, with all their relocations and imports. That packing is the
reason modding a stream isn't "open file, edit line, save":

- You can't just resize one asset's bytes in place. Everything after it would shift, and every offset in the
  manifest and relocation tables would silently become wrong.
- So replacing an asset means **rebuilding the stream's bookkeeping** — the manifest entries, the cumulative
  offsets, the reference buffer — so the whole thing stays internally consistent. That's precisely the job of
  `pytools/splice_asset.py`.

It's also why the **decompiler's** task is subtle: to turn a stream back into XML it has to *reverse the
linking* — follow every relocated offset-pointer, and resolve every import id back to a named reference. Doing
that mechanically and exactly is the same reason the round-trip can come out **byte-identical**: decompiling is
un-doing a precise, deterministic linking step, not guessing.

## Recap

- A stream is a **compiled, relocatable, linkable bundle of serialized game objects** — the asset-world
  equivalent of a linked ELF object.
- Its four parts map to a symbol table (`manifest`), data (`bin`), relocations (`relo`), and imports (`imp`).
- The engine **loads and relocates** it like a shared library.
- A `.big` archive is simply the file that *contains* one or more streams.

---

Previous: [1 · The big picture](../01-the-big-picture/README.md) ·
Next: *the on-disk format in detail (coming)*
