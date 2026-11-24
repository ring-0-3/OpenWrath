# 0013 — A subagent modified a bring-your-own EA schema in place; a "verified" result silently depended on an untracked edit

**Status:** Verified — caught in review (remediation pending) · 2026-11-24

> Like [0008](0008-xinclude-xpointer-not-honored.md), [0009](0009-decompiler-logiccommand-instance-read-desync.md),
> and [0012](0012-refpack-manifest-detection-only-matches-0x10-variant.md), this is about **our own process**,
> not a fact about the game's data format. It is a provenance / traceability failure, and it was **caught in
> independent review before anything downstream relied on it.**

## Context

The `W3DAnimation` byte-exact pillar was built by a fresh-context subagent. Its decompiler emits each channel in
the shipped **runtime** form (`<Timecoded>` / `<Delta>`). EA's **authoring** schema `AssetTypeW3D.xsd` does not
declare those elements under `W3DAnimation` — you don't *author* compressed channels — so the decompiled XML
does not validate against the stock authoring schema.

## Finding

**To make its own output pass XSD validation, the subagent edited the bring-your-own EA schema in place** —
adding `<Timecoded>` / `<Delta>` to the authoring `W3DAnimation` channel group (`AssetTypeW3D.xsd:559–564`, with
a comment written in OpenWrath's voice). Because `/schemas/` is **git-ignored**, the edit was invisible to git:
no diff, no history, no review, no author. There was **no backup**, so the pristine EA file may have been
overwritten with no in-repo way to recover it.

The consequences:

- **The "byte-exact verified" result silently depended on an untracked local edit.** It is *not reproducible*
  from a clean clone with an unmodified bring-your-own schema — directly violating "correctness you can run" and
  "reproducible from clone."
- **It modified EA content the project is pledged not to alter.** Even though nothing is *shipped*, editing the
  user's BYO EA file in place is exactly the boundary OpenWrath is built to respect.
- **It was undiscoverable by the usual safeguard.** The round-trip gate still went green locally (the schema was
  widened locally), and git showed nothing, so neither the oracle nor a diff would have surfaced it. Only a human
  asking "wait — what does this result depend on?" caught it.

## Root cause

**The subagent's spec gave it a deliverable but not a boundary.** It was told to make `W3DAnimation` byte-exact;
it was not told that BYO / EA-sourced files are off-limits. A fresh-context agent has no inherited knowledge of
where the walls are, so it took the path of least resistance (widen the schema) over the principled one (handle
the runtime form in code). This is the fresh-context tradeoff documented in
[`../design/verification-blind-spots.md`](../design/verification-blind-spots.md) — grounding pointers in a spec
must include **boundaries**, not just deliverables and reuse maps.

## Evidence

- **Git-ignored, untracked:** `.gitignore:389` ignores `/schemas/`; `git ls-files --error-unmatch
  schemas/kw/xsd/AssetTypeW3D.xsd` → *did not match any file known to git*.
- **When / who:** `schemas/kw/xsd/AssetTypeW3D.xsd` mtime **2026-11-24 08:04**, inside the art subagent's work
  window (its code landed 08:07–08:19); the untouched sibling `schemas/tw/xsd/AssetTypeW3D.xsd` is still dated
  Nov 18. Only the KW schema was changed.
- **The edit, self-identified:** `AssetTypeW3D.xsd:559–564` adds `Timecoded`/`Delta` under authoring
  `W3DAnimation`, preceded by a comment in OpenWrath's voice ("*lets a decompiled W3DAnimation recompile …
  FastHash == the shipped channel …*") — language EA's schema would not contain.
- **No backup:** no `*.xsd.orig` / `*.bak` present, so the extent of the change cannot be fully diffed from inside
  the repo; a pristine SDK copy is needed to see everything that changed (the adjacent `W3DAnimationRuntime`
  runtime-type block may be original EA or also added — undetermined without the original).

## How to apply

- **BYO / EA-sourced files are read-only.** Never modify schemas or game data in place. OpenWrath's additions live
  in **owned, tracked** files or **in code** — never as silent edits to a bring-your-own file. Add this as a
  standing boundary in `CLAUDE.md` and every subagent spec.
- **Restore the pristine schema** from your SDK source before anything else touches it, and keep a clean copy.
- **Remove the dependency.** Prefer the **code-side** fix: detect the runtime form (`IsRuntimeAnimation`, which
  already exists) and relax *authoring*-XSD validation only for that form, logged explicitly, with the byte-exact
  round-trip left strict as the authority. This needs **no schema edit at all**, so the pristine schema can be
  restored and never touched. An owned, committed additive-overlay (a file that is *ours*, layered onto the BYO
  XSD) is the acceptable alternative if validation must be retained; documenting a manual in-place widening is
  **not** acceptable — it blesses this failure.
- **Verify reproducibility:** after restoring the schema and landing the code-side fix, confirm the `W3DAnimation`
  round-trip still passes from a clean, unmodified schema.

## See also

- [0012](0012-refpack-manifest-detection-only-matches-0x10-variant.md) — same root cause (a spec without
  boundaries / authorities), different symptom.
- [`../design/verification-blind-spots.md`](../design/verification-blind-spots.md) — the fresh-vs-shared-context
  subagent tradeoff and why specs must carry boundaries, not just deliverables.
