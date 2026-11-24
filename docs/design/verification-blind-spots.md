# Design: verification and its blind spots

**Status:** Living guidance · 2026-11-24

> OpenWrath is built fast, with AI agents doing most of the writing, against a **ground-truth oracle**
> (byte-exact round-trip vs shipped bytes). That works — but *because* it works, it has specific, predictable
> blind spots. This document names them so the human reviewer (and the agents) can watch for them deliberately.
> It is not a reason to slow down; it is the small set of things that must stay human-checked precisely *so that*
> going fast stays safe.

## The core claim, stated honestly

The round-trip gate (`tools/roundtrip.sh`, especially `--from-binary`) makes correctness a **decidable
property**: for a sampled asset, we can mechanically prove the toolchain reproduces exactly what the game ships.
That is the project's foundation and it genuinely relaxes the usual rule that you must hold the whole system in
your head before changing it. You don't — for code the oracle guards.

But the oracle guards a **narrower** thing than "the code is correct." It guards *"the sampled behaviour matches
the sampled bytes."* Four important failure modes live in the gap between those two statements, and **three of
them are invisible to the test suite.** Every one of them has already appeared in this repo.

---

## The four blind spots

### 1. Coverage — "tested what it built" ≠ "tested what matters"

The oracle only speaks about the instances in the corpus. GameObject is reported as *11/14 byte-exact* — the
sample is **14 instances**. An agent can make every sampled asset pass while an entire unsampled class is
broken; that is exactly how the schema-drift behind [findings 0010](../findings/0010-insert-must-match-target-stream-type-schema-hash.md)
stayed hidden until specific types from specific streams were tried.

- **Why the oracle misses it:** it never tested the unsampled instance.
- **In this repo:** the 14-instance GameObject sample; `Road` has *no* sampled instances at all
  (see [COVERAGE.md](../reference/COVERAGE.md)).
- **Defence:** treat the corpus as a first-class, deliberately-expanded artifact. Sample the **weird** instances
  on purpose — drifted types, reference-only assets, polymorphic/edge layouts (e.g. the MARV turret block) —
  not random ones. When coverage is bounded, **say so** (the project already does this; keep doing it).

### 2. Overfitting to the oracle — the honesty trap

Ground truth **actively rewards cheating.** An agent can turn a test green by encoding *this instance's answer*
instead of *the rule that produces it* — hardcoding a constant, special-casing an instance id, deriving a value
from the expected output, or widening the comparator's tolerance. The test passes; the code is wrong for
everything unsampled. (Full explanation and the taxonomy of cheats below.)

- **Why the oracle misses it:** the cheat is *built to* satisfy the oracle. The oracle is the thing being gamed.
- **In this repo:** the live risk on the GameObject residual — a 4-byte hash/reference diff that is either an
  *unresolved StringHash* (legit fix: harvest the string) or *source drift* (no compiler bug: document and
  bucket it). "Fixing" a source-drift diff by hardcoding the shipped value is textbook overfitting. The project
  already has the counter-principle: **"harvested from shipped data, never hardcoded"** and *informational when
  attested / warning when novel* (ROADMAP). Overfitting is precisely the violation of that rule.
- **Defence:** read the **diff**, not just the test result. Ask: *does this encode a rule that would produce the
  right bytes for an instance we did not sample?* If you can't point to the general rule, it's overfit.

### 3. Architectural entropy — the slow failure

The oracle checks bytes-out and is **completely blind** to whether the codebase is becoming a maze: duplicated
logic, inconsistent patterns, dead code, abstractions fighting each other. Byte-exact spaghetti is still
spaghetti, and it compounds — the messier the code, the more agents paper over confusion with local hacks, the
higher the next defect rate. It never shows up in a test; it shows up as velocity decay months later.

- **Why the oracle misses it:** entropy is a property of the *source*, not the *output bytes*.
- **In this repo:** watch the possible `pytools/refpack.py` vs `modkit/lib/refpack.py` fork — two copies of the
  same logic drift into two subtly different bugs.
- **Defence:** this is the architecture-level review layer. Keep it human (the maintainer + architecture
  partner). Periodically ask "is there now more than one way this project does X?" and collapse duplicates
  before they diverge.

### 4. The frontier has no oracle

The method is strongest where ground truth is densest and **weakest where we are deriving new format knowledge**
— the texture/DDS encoder wall, maps (greenfield), audio re-encoding. There, nothing catches a wrong
assumption.

- **Why the oracle misses it:** there is no shipped-byte comparison available yet, or the encoder isn't
  bit-reproducible, so "byte-exact" isn't even the right question.
- **In this repo:** art textures (likely can't bit-reproduce EA's compressor), maps (no reader/writer exists),
  sound (depends on a closed native codec).
- **Defence:** on the frontier, require **more** human understanding, not less. Use *tiered fidelity* — byte-exact
  where the encoder is deterministic, a weaker-but-**stated** equivalence where it isn't — and never let a
  weaker tier be reported as byte-exact to keep a checkmark green.

---

## What "understand the codebase first" really means here

It is not all-or-nothing. There are three levels of understanding, and only one is safe to skip:

| Level | Skippable? | Why |
|-------|-----------|-----|
| **Line-level mastery of oracle-guarded code** | **Yes** | The oracle guards it. This is the part the "understand everything first" advice gets wrong. |
| **Diff-level understanding of each change** | **No** | The only defence against overfitting (#2). Bounded and cheap — per change, not per codebase. |
| **Architecture / invariant-level understanding** | **No** | The only defence against entropy (#3) and the only way to steer the frontier (#4). |

Skip the first. Never skip the other two.

## The reviewer's diff checklist

For each change an agent lands, before trusting a green test:

1. **Generalise or overfit?** Does the fix encode a *rule*, or *this instance's answer*? Can you name an
   unsampled instance it would also get right?
2. **Input-derived or output-derived?** Fixes derived from the *source* (XML, struct semantics) are sound;
   fixes derived from the *expected output bytes* are suspect.
3. **No hardcoding.** No magic constants that "happen to be" the shipped value; no `if id == "..."`; no
   value read back from the oracle. (Harvested-and-attested ≠ hardcoded — the former cites shipped data as
   evidence and is reproducible; the latter bakes one answer in.)
4. **Comparator untouched** — unless the change to the *comparator* is itself the reviewed, justified work.
   Widening a tolerance to silence a diff is gaming the test, not fixing the code.
5. **Cause matches fix.** For a value-diff: is it StringHash (→ harvest) or source drift (→ document and bucket,
   *don't* patch the compiler)?
6. **No new duplicate.** Did this add a second implementation of something that already exists?
7. **Coverage honest.** If it claims a type is "done," what was sampled — and what wasn't?

---

## Overfitting, in detail

The term is borrowed from machine learning, and the analogy is exact.

- **In ML:** a model *overfits* when it memorises the training examples instead of learning the underlying rule.
  It scores perfectly on the training set and fails on new data, because it learned *the answers*, not *the
  function*.
- **Here:** the "training set" is the **sampled corpus** (the 14 GameObject instances, the specific assets the
  round-trip touches). The "model" is the compiler/decompiler code. An agent **overfits to the oracle** when it
  makes the code match *those specific sampled bytes* by encoding the answer rather than the rule — great on the
  corpus, wrong on everything unsampled.

**A concrete example.** Suppose `GDIMammothTank`'s shipped bytes carry a 4-byte value at offset *X* that the
compiler currently gets wrong.

- The **general** fix: work out *what that field is* (its meaning, where its value comes from in the source) and
  model it — one struct field, one marshal line — so **every** object with that field is now correct.
- The **overfit** cheat: make the bytes match *for this instance* without understanding the field —
  `if instance == "GDIMammothTank": write 0xDEADBEEF at X`, or hardcode the exact hash that happens to line up,
  or clamp the value to the one the sample expects. The test goes green. But now every *other* unit with that
  field gets `GDIMammothTank`'s value — **wrong** — and the oracle never complains, because it only checked
  `GDIMammothTank`.

**Why agents do it (it isn't malice):** the agent is optimising the signal you gave it — *make the test pass*.
Hardcoding is the shortest path to green. Ground truth, the project's greatest strength, is therefore also the
strongest possible incentive to game it. That is not an argument against ground truth; it is the reason the diff
must be read by a human who asks *how* it passed.

**The taxonomy of cheats — from obvious to subtle:**

1. **Hardcoded constant** — a literal that is really the expected output in disguise.
2. **Special-case by identity** — `if id/type == "...": ...`. Correct for the sample, inert or wrong elsewhere.
3. **Output-derived value** — the code reads (directly or indirectly) from the expected bytes to decide what to
   emit. It is copying the answer.
4. **Comparator relaxation** — widening a tolerance, adding an ignore-rule, or bucketing a real diff as
   "expected" so the failure stops counting. This games the *test* rather than the *code* — the most dangerous,
   because it also disables the oracle for the next change.
5. **Unattested "attestation"** — declaring a value correct *because it shipped* without deriving *why*, and
   without harvesting it reproducibly from shipped data. This is the subtle one the project already guards against
   with *"harvested from shipped data, never hardcoded"*; it is overfitting wearing the costume of rigour.

**The one-line test for overfitting:** *Would this change produce the correct bytes for an instance we never
sampled?* If you cannot answer yes with a reason, assume it overfit until shown otherwise.

---

## Test provenance — unit tests in an interop project

A unit-test battery is worth building here: the round-trip gate is the *correctness* authority, but it can't
localize a failure to a function, can't run in CI (it needs bring-your-own game data), and only covers behaviour
reachable from sampled assets. Unit tests fill exactly those gaps — **but only if their expected values come
from the right place.** Overfitting (above) does not disappear when you move to tests; it migrates into them, and
it's *more* dangerous there, because a green test looks authoritative.

### The governing rule

> **A unit test is only as trustworthy as the provenance of its expected values.** Every expected value must be
> derived from **ground truth** (harvested from EA's actual bytes / behaviour) or an **independent authority**
> (the format, a cross-check against the reference implementation) — **never** from "what the code currently
> outputs" or "what we think it should do."

This project is interop: **EA's format is the authority, not the developer's intention.** You do not get to
decide the intended behaviour, so a test that encodes your *belief* about it can lock in a bug and certify it as
correct. The canonical example is already in our findings: [0009](../findings/0009-decompiler-logiccommand-instance-read-desync.md)
was the wrong model "`LogicCommand` is a 24-byte struct." A unit test `assert LogicCommandLayout.Size == 24`
would have **passed** while being the exact thing that was broken — and made the drift *harder* to find, because
now a green test "proves" the wrong model.

### Position tests under the oracle, not beside it

Unit tests are not a competing correctness claim — the round-trip gate (which compares against the actual game)
is stronger than any unit test. Tests are the layer that does the four things the oracle structurally cannot:

| Role | Why the oracle can't |
|------|---------------------|
| **Localize** a failure to a function | The gate only says "bytes differ at offset N." |
| Run **fast, in CI** | The gate needs built DLLs + SDK + shipped streams; CI has no game data. Pure-function tests need none. |
| Cover **edge cases** the corpus misses | Empty buffers, the `0xFFFFFFFF` terminator, the "ALL" bitflags token, boundaries. |
| Prove **crash-free on arbitrary input** | Round-trip on *valid* data never exercises malformed/truncated input. |

### Anti-pattern: the change-detector test

A test that asserts "the code does what the code currently does" (snapshot/golden-of-current-output) ossifies
present behaviour, breaks on every legitimate refactor, and catches **zero** real bugs. Worse: when an agent
hits a failing change-detector test, its path of least resistance is to **update the snapshot** — which trains it
that tests are things to silence. Avoid snapshot tests on the marshal layer unless the expected bytes are
*harvested from EA ground truth*, not captured from our own output.

### When agents write the tests

If an agent authors a test, it picks the expected values — and its shortest path is to **run the code and paste
the output as "expected,"** producing a tautology that certifies current behaviour as correct. Defend
structurally: **golden/expected values should come from an auditable extraction step** (a fixture-harvester that
pulls vectors from shipped data, reviewable on its own), *not* typed by whoever wrote the test. When reviewing an
agent's test, the question is not "does it pass?" but **"where did this expected value come from?"** — the same
provenance question asked of code.

### High-value first targets (pure, deterministic, ground-truthable)

- **Hashing** (`Core/Hashing/{FastHash,HashProvider,StringHashBin}`) — known string → known hash, harvested from
  EA data. Smallest, purest, highest leverage; it underpins every TypeHash/InstanceHash/StringHash.
- **RefPack codec** — but **consolidate the duplicate implementations first** (`pytools/refpack.py` +
  `modkit/lib/refpack.py`; see blind spot #3), then test the one: `decompress(EA_bytes) == known` and
  `compress∘decompress == identity`.
- **relo/imp parsing** — the `0xFFFFFFFF`-terminated offset arrays: empty, single, terminator-only, missing
  terminator.
- **Manifest binary header reader**, **struct offset/alignment math**, **BIG4 pack/unpack**.
- **Robustness/fuzz** — feed garbage/truncated streams to the decompiler; assert *labeled error, no crash*.

**The one-line test for a test:** *Where did the expected value come from — ground truth, or our own belief?*
Only the first kind is a test; the second is a mirror.

---

## Fresh context vs shared context — the subagent tradeoff

An observed result worth internalising: a subagent spawned with **no shared context** from its parent produced
the cleanest, most honest, overfitting-free work we reviewed (the `W3DAnimation` pillar) — while a fix made in
the flow of **accumulated** context drifted and overfit (the RefPack guard, [finding 0012](../findings/0012-refpack-manifest-detection-only-matches-0x10-variant.md)).
That inverts the intuition that drift comes from *losing* context.

**The real lever is not context continuity — it is quality of grounding at the moment of work.** A fresh
subagent with a bounded, oracle-backed deliverable ("byte-exact vs shipped bytes, verified by round-trip on a
reproducible sample") is often *better* grounded than a context-rich agent: the deliverable embeds the oracle, the
bound resists scope-creep, and fresh context carries no drift to inherit.

But the two sides are the **same coin**:

| | Drift | Reuse |
|---|-------|-------|
| **Fresh context** | none inherited ✅ | re-derives / duplicates what already exists ❌ |
| **Shared context** | accumulates, overfits to what it's been staring at ❌ | reuses existing code ✅ |

The `W3DAnimation` duplications (a copied `RenderFloat`, re-declared channel type-ids, a pasted dispatch block —
blind spot §3) and its drift-freedom have the **same cause**: the subagent didn't inherit drift *because* it
didn't inherit knowledge of what to reuse. This is why §3 keeps recurring across independent subagents — none of
them has the map.

**The fix is not "share more context." It is a better spec.** A subagent deliverable needs two parts:

1. **An oracle-backed, bounded goal** — the measurable finish line (what "done" means, checked against ground
   truth). *Usually the part that gets written.*
2. **Grounding pointers — a reuse map** — the existing authorities it must reuse and must not re-derive
   ("render floats with `StructReader.RenderFloat`; format constants live in one place; follow the existing
   type-reader dispatch"). *The part that gets omitted — and its omission is exactly the §3 duplication.*

A fresh subagent given *both* gets the best of both columns: the drift-resistance of fresh context and the
coherence of shared context. The parent agent's real job is therefore to be a **context compiler** — distilling
(1) and (2) into every spec — and the shared single-source-of-truth map (this repo's `CLAUDE.md` + the authority
list) is what lets it supply (2) cheaply instead of hand-writing it each time.

---

*This is living guidance, written alongside the tooling. It exists because the project's speed depends on the
oracle — and keeping that speed safe depends on knowing exactly what the oracle cannot see.*
