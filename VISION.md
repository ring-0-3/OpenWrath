# OpenWrath — Vision

OpenWrath is an open-source, native-Linux toolchain for the **data and assets** of the real-time
strategy game *Command & Conquer 3: Kane's Wrath*: compile authoring XML into the game's compiled
asset format, decompile it back, and pack/unpack its archives — losslessly, and *verifiably* so.

It is interop tooling only. It ships **no game content**; you bring your own legally-owned game data.

## Why it exists

Tooling for this game's data has largely been Windows-only or closed, and the file formats mostly
undocumented. OpenWrath is an attempt to make working with that data **open, native, and learnable**
— to lower the barrier so anyone who wants to mod, rebalance, or simply *understand* the game's data
can.

## What we value

**Correctness you can check, not trust.** The backbone of the project is a verification harness:
decompile an asset, recompile it, and assert the bytes are identical — and, stronger, compare our
output against the bytes the game itself ships (`tools/roundtrip.sh --from-binary`). Correctness is
therefore something anyone can *run and see*, not a claim to take on faith. "Trust me" is not part of
the design.

**Faithful to the game's real data.** The goal is to reproduce exactly what the game loads. Where the
shipped data does something the public authoring schema doesn't describe, we reproduce it faithfully
— and say so plainly — rather than pretending the schema is the whole truth.

**Honest about its limits.** Where a type or value isn't yet fully handled, the tools say so: labeled,
localized, never silently wrong. The reliability frontier is something we publish, not hide.

**Learnable, not hoarded.** The file formats we work out are written down as explained knowledge, not
just code. The tools stay fully powerful; the "easy" lives in documentation and tutorials layered on
top, so the depth is teachable rather than gated.

**Built to be built on.** OpenWrath is meant to be a foundation for other tools and a host for
community modules. Its boundaries are treated as a public interface — stable, machine-readable, and
honest — so what people build on top can stay reliable and maintainable. That extends to the wider
ecosystem: different mods were built against different *schema versions* of the data, so OpenWrath aims
to be schema-aware — a default schema plus an additive, community-contributed set of supported variants,
each a layout we derived and *verified*, carrying no one else's content (see
[`docs/design/multi-schema-interop.md`](docs/design/multi-schema-interop.md)).

## How it's made

OpenWrath is developed with AI assistance, disclosed plainly (see [`NOTICE`](NOTICE.md)). That
disclosure is anchored to the test suite: every correctness claim here is one you can reproduce
yourself with the verification harness. The aim is durable, audited, well-understood code — not
output taken on trust.

## Non-goals

- Shipping game content or SDK assets. Bring your own legally-owned data.
- A GUI-first workflow that hides capability. Great documentation over a locked-down "simple mode."
