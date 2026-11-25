# Design — community mods as frontier existence-proofs (study the mechanism, reimplement clean)

**Status:** Proposed (research strategy) · 2026-11-25 · feeds the content pipeline (textures / particles / new
geometry)

> The Kane's Wrath community has already shipped content that OpenWrath can't yet produce — 4K/HD texture add-ons,
> total-conversion mods with **new units** (new geometry, textures, FX), and patches that rework **particle
> effects** (e.g. reworked NOD laser effects). Each is an **existence-proof** that the retail engine *accepts* a
> given kind of non-EA content. That is enormously useful — but only if we take from it the right thing: the
> **format/loading mechanism**, verified ourselves, reimplemented clean. Never the content, never their bytes as
> ground truth.

## Why this is a lever (the reframe)

The frontier's defining problem (verification-blind-spots §4) is "no oracle": for textures we can't bit-reproduce
EA's compressor, so byte-exact isn't even the right question. Community mods dissolve a chunk of that by proving a
**weaker-but-sufficient** bar is reachable: *the engine loads and renders it.* We don't need EA's exact bytes for
**new** content (there is no EA original to match); we need bytes the engine accepts. The community has repeatedly
demonstrated that's possible. Studying how turns "frontier, no oracle" into "stated tier with an **in-game
acceptance gate**."

## The discipline — community mods are NOT ground truth

This shifts the project's epistemology, so state the rule plainly:

- **EA's actual bytes remain the authority** for round-tripping *shipped* assets. A community mod is *another
  interpretation* of the format — possibly correct, possibly lossy, possibly a hack. Treating its output bytes as
  the oracle would be exactly the overfitting the project guards against.
- **What we take is the *mechanism*, which we verify ourselves:** what the engine accepts, in what container, via
  what load path. The oracle for that is the **retail engine in-game** (does it load / render / not crash) plus,
  where an EA original exists, byte-exact against EA.
- **BYO / zero-EA extends to this work.** Reverse-engineering a *file format* for interop is legitimate (it is what
  the whole project does with EA's format). Absorbing a mod's *content* — or shipping anything derived from it — is
  not. "Reimplement, don't copy" has a real trap: do not launder derived content by reconstructing it from their
  files. We characterize the format, reimplement the format support in owned code, and ship **nothing** of theirs.
  Test corpora use *your own legally-owned* install and the mods *you* legally have; OpenWrath distributes none of
  it.
- **Credit and engage the community.** The KW scene is small and these mods represent real reverse-engineering
  effort. Name the mechanism's source in the finding; prefer collaborating over silently absorbing. Good-citizen
  *and* legally-safest.
- **Hypothesis-flagged until examined.** We do not yet know any of these mods' internals. Everything below is a
  *question to answer*, not a claim.

## The corpus spans three tiers — not one

The single most useful insight: the named examples sit on **different** difficulty tiers, and each teaches a
different lesson.

| Tier | Example mods (names per your install — verify) | OpenWrath type(s) | Likely difficulty |
|---|---|---|---|
| **Data type (probably byte-exact)** | particle/FX patches — reworked **laser effects**, Redeemer et al. | `FXParticleSystemTemplate` (today **commented-out** in the *XmlCompiler* — the data toolchain, not art) | **Low.** Likely a normal data type → register + round-trip byte-exact like the existing 37. The mods prove it's moddable and give us non-EA test instances. May not be "frontier" at all. |
| **Authoring / re-pack** | new-units / total-conversion mod (new geometry + skinning) | `W3DMesh` authoring path + `W3DHierarchy`/`W3DContainer` | **Medium.** Gated on the **re-pack equality test** (see [blender-integration](blender-integration.md)); the new-unit mods are existence-proofs that non-EA geometry loads, and a source of test instances. |
| **True frontier (stated tier)** | 4K / HD texture add-on; texture patches | `Texture` / `PackedTextureImage` / `OnDemandTexture(Image)`, DDS | **High.** Can't bit-reproduce EA's compressor; the mods likely prove we don't need to — emit a texture the engine accepts. In-game acceptance gate, never claimed byte-exact. |

The payoff of sorting them: **start where the oracle is strongest.** Particle templates may promote to byte-exact
cheaply; textures stay a stated tier. Don't let the excitement of the 4K add-on pull the first effort onto the
hardest tier.

## The investigation method (per mod, produces a finding)

For each mod examined, characterize — don't copy — answering:

1. **What does it replace or add, and where?** A repacked BIG? a new/replaced stream? standalone files? a
   `.version` redirect or mount-order trick (cf. finding 0017's overlay chain)?
2. **What is the payload format?** For textures: standard DXT1/5 from a generic encoder? uncompressed? mip chain?
   does the DDS/container header match EA's or a vanilla one? For geometry: authored-and-repacked via the runtime
   layout, or something else? For particles: the normal `FXParticleSystemTemplate` record, or a variant schema?
3. **Does it replace asset *records*, raw *files*, or both?** (Which of the Not-modeled types it touches.)
4. **How does the engine get pointed at it?** The load/override path — the thing that makes acceptance *reproducible*.

Each answered set becomes a dated **finding** (verified mechanism, with its community source credited) and feeds the
relevant row in **[COVERAGE.md](../reference/COVERAGE.md)** — promoting a type from "Not modeled" to either
byte-exact (data tier) or "stated tier + in-game acceptance gate" (frontier tier). Nothing is marked done on a mod's
say-so; it is marked done on *our* reproduction passing *our* gate.

## Boundaries / non-goals

- Ship **no** community or EA content; reimplement format support in owned code. No derived bytes.
- Do not treat a mod's output as the oracle. Byte-exact is for EA originals / data types; the frontier gate is
  in-game acceptance.
- Keep format knowledge in OpenWrath, not forked into mod-specific hacks (§3 duplication at ecosystem scale).
- Each type still enters via a fresh builder spec (goal + reuse-map + boundaries) and independent review.

---

*Research strategy, written while the W3D pillar is in flight. Its purpose is to fix the discipline — community
mods are existence-proofs of "the engine accepts X," studied for mechanism and reimplemented clean, **never** a
replacement for EA ground truth — before the texture/particle/new-geometry work begins, so the frontier is unlocked
honestly rather than by trusting someone else's bytes.*
