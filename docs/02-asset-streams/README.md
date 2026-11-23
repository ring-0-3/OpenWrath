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
Two *different* offsets are in play here, and keeping them apart is the whole trick:

- A pointer **field** sits at some position inside the `.bin` — its **slot offset**. The `.relo` table is
  simply a list of these: *"a pointer lives at this offset."* It records **where the pointers are**.
- That field doesn't hold an address (nothing is loaded yet) — it holds a **target offset**: the position of
  the sub-object it points *to*, measured from the start of the same `.bin`. It records **where the target is**.

At load time the engine reads `.bin` into memory starting at some `base_address`, then walks `.relo`. For each
slot offset it visits `base_address + slot_offset` (that *finds* the pointer field), reads the `target_offset`
stored there, and overwrites the field with `base_address + target_offset` (that *is* the pointer's new value).
So "base + offset" happens **twice, with two different offsets** — one to *locate* the pointer, one to compute
what it *points at*. This is **literally code relocation** — the same fix-up a loader performs on a shared library.

Concretely: the blob loads at `0x10000`; a weapon's projectile-pointer field is at slot offset `40`, and the
projectile sub-object itself at offset `500`. On disk, slot `40` holds the value `500`, and `.relo` lists `40`.
The loader reads `.relo` entry `40` → visits `0x10000 + 40` → finds `500` → writes `0x10000 + 500 = 0x101F4`.
The pointer now holds the projectile's real memory address.

**Where does `base_address` come from?** It isn't stored on disk at all — that's the whole point. The offsets
are written *as if the blob loaded at zero*, so the on-disk form is independent of where it actually ends up.
The real `base_address` is simply wherever the engine allocates the blob in memory at load time; relocation
then slides every pointer to match. (Same idea as position-independent code / RVAs in an ELF or PE file.) And
it's why OpenWrath's own tools never need a real base: they stay in the **offset domain** — `base = 0`, walking
`.relo`-marked slots as blob-relative positions — and never load anything into real memory. That
base-independence is exactly what lets a stream decompile and recompile **byte-for-byte**.

**Cross-stream references → imports.**
When asset A references asset B that lives in a *different* stream — a mod unit referencing a base-game weapon,
or any object referencing a shared audio event — the field can't use an offset at all (the target isn't in this
blob), so it stores an asset **id**, and the `.imp` table records the position of each such field. At load time
the engine resolves each id against all the other loaded streams and patches in the real address. This is
**dynamic-library symbol linking**, applied to game data.

So the engine's load path is:

```
read .bin into memory  →  apply .relo (fix internal pointers)  →  resolve .imp (link to other streams)
                                                                           ↓
                                                                 live game objects
```

And *that* is why it's called a "stream": it's a block of data **streamed into memory and relocated** — a
memory image you load and fix up, not a document you parse field-by-field.

## Why this matters for modding

A complete overhaul mod can ship its entire contents as **one stream** — tens of thousands of assets packed
contiguously, with all their relocations and imports. That packing is the reason modding a stream isn't "open
file, edit line, save":

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
