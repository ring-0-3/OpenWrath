# 0016 — The static `_mod` stream REPLACES `static_common`; a loadable binary mod must ship the full, version-matched dataset

**Status:** Verified (EA-patch + SI + three confirming reads) · one optional direct test remains (a version-correct *complete* build via our path — Option 2) · 2026-11-24

> About **how the retail engine loads mod streams** and what that forces on `mod package` — the live-launch
> property that findings [0005](0005-mods-must-live-in-one-target-stream.md) / [0015](0015-standalone-overlay-override-needs-sliced-inheritfrom-base.md)
> and the ROADMAP flagged as the one thing only an in-game launch could settle.

## Context

`mod package` produced a **byte-correct, zero-EA** standalone overlay — a `static_mod` carrying only the user's
declared edits and *importing* the rest from the base streams by id ([0015](0015-standalone-overlay-override-needs-sliced-inheritfrom-base.md)).
It **crashed the retail game (1.3 / Patch103) at skirmish load.** Adding the `.version` load handshake
([0015](0015-standalone-overlay-override-needs-sliced-inheritfrom-base.md)) was necessary but did **not** stop the
crash. The open question: does the engine load `static_mod` **alongside** `static_common` (overlay / coexistence)
or **instead of** it (replacement)?

## Finding

**The static `_mod` stream REPLACES `static_common` — the engine loads one complete static stream, not a
base+overlay pair.** A partial `_mod` cannot stand in for the whole dataset, so a mod's `_mod` stream must be
**complete** (carry every asset) **and version-matched** to the running engine's per-type schema hashes. This is
EA's own design, not a limitation of our tooling.

## Evidence

- **EA's own 1.03 patch delivers via a *complete* `Static_mod`.** It carries **21,747 assets** (vs retail
  `static_common`'s **21,435**), spanning **every type including art** (`W3DMesh`, `Texture`, `GameObject`,
  `WeaponTemplate`, …), plus `data\Static.version` = `"_mod"`. If an overlay/diff were loadable, EA — who wrote the
  engine — would ship only the *changed* assets; shipping a full superset is EA telling us the stream must be
  complete. *(Measured by the builder against the installed 1.03 patch; re-checkable by counting assets in the
  patch's `Static_mod.manifest`.)*
- **Second Isomer ships the same shape** — a complete, self-sufficient `static_mod` (43,994 assets). Every prior
  modkit insert ([0006](0006-new-assets-need-stream-insert.md)) succeeded precisely because it went **into a
  complete stream**; a standalone *partial* stream was never runtime-tested until now.
- **The complete-probe crash was a *version* artifact, not incompleteness.** A retail `static_common` renamed to
  `static_mod` crashed on a **TypeHash mismatch** — `Type hash mismatch for type 0xdefca2f6` (`DefaultHotKeys`),
  `Expected: 0x12cb83dc but got: 0x692d0b3a … the game will now exit` — the [0010](0010-insert-must-match-target-stream-type-schema-hash.md)
  "DID YOU REMEMBER TO BUILD DATA" guard. Cause: the probe was sourced from **Core/1.0** while the engine runs
  **1.3**. This proved (a) the engine *validates per-type hashes of the loaded `static_mod`* — so our
  packaging/registration path mounts correctly, ruling out a structural/registration fault — and (b) the correct
  complete source is the **patch's `Static_mod` (1.3 hashes)**, not Core/1.0.
- **Partial `_mod` streams crash at skirmish load, including a zero-import leaf `ArmorTemplate`** — which rules out
  *dangling cross-stream imports* as the cause. **Confirmed clean (not version drift):** our leaf overlay's
  `ArmorTemplate` TypeHash is `0x6d59c409`, **identical** to the 1.3 patch `Static_mod`'s `ArmorTemplate` hash — so
  the leaf is version-correct for the running engine, and its crash is incompleteness, not a [0010] drift.
- **The static stream is selected by a `.version` *postfix*, one complete stream per family (direct replacement
  evidence).** Three `static.version` files ship with distinct postfixes: `Core/1.0/StaticStream.big` =
  `"_common"` → `static_common`; `Core/1.2/patch2.big` = `"_common_2"` → `static_common_2`;
  `Patch103/102texturefix.big` = `"_mod"` → the complete `Static_mod`. The engine resolves **one** postfix per
  family and loads that single stream — it is not a base+overlay pair. Our package shipped `static.version` =
  `"_mod"` too, so it collides with / undercuts the patch's complete `Static_mod` with our partial one → crash.

## Consequence — the `mod package` feature

- **A zero-EA, shareable, standalone *binary* static mod is not possible on retail KW.** A loadable stream needs
  the full base dataset, which is EA-derived content. `mod package`'s output is a **correct, valuable zero-EA
  *diff*** — not a drop-in loadable mod. **ROADMAP/README must stop presenting standalone `mod package` as a
  done, shareable drop-in** (doc-integrity correction; [verification-blind-spots](../design/verification-blind-spots.md) §7).
- **Loadable paths (user's choice):**
  1. **Diff + assemble-at-install** *(recommended — keeps OpenWrath's zero-EA identity)*: ship the tiny zero-EA
     diff; a small installer assembles the complete stream from the **recipient's own** install at install time.
     The shared artifact stays zero-EA. (Essentially `mod bake` run recipient-side.)
  2. **Local complete build**: assemble the complete `static_mod` from the user's own **patch `Static_mod`** +
     their edits. Loads and overrides — but it is EA-derived, so **local-only, not shareable**.
  3. **INI / loose-file overrides** (GodMode-style): genuinely zero-EA **and** shareable, but only for
     INI-moddable values — a different pipeline.
  4. **`mod bake` into an existing complete stream** (works today): the splice-into-a-complete-stream path.

## Consequence — input integrity (blind spots [#1, #5](../design/verification-blind-spots.md))

- **The correct base is the running patch's `Static_mod` (1.3), NOT Core/1.0 or raw retail `static_common`.**
  `inputs.sha256` is currently **version-blind** (it records no patch version) while the modkit targets 1.3
  installs (`config.example.toml`, tests expect `CNC3EP1_english_1.3.SkuDef`). A pristine-but-1.0 baseline passes
  every input check and still `0010`-crashes a 1.3 engine. **Re-baseline inputs from the patch `Static_mod` and
  record the patch version in the baseline.**
- **`COVERAGE.md`'s "byte-exact vs EA shipped bytes" is version-unqualified** and may have been measured against a
  stream the 1.3 engine does not load. **Re-qualify (or at least stamp) each number with the patch version it was
  measured against.**
- **Re-scope the earlier "no 0010 drift / TypeHash matches retail" all-clear** (the `WeaponTemplate 0x90aeab74`
  check): it was compared against *a* retail version; confirm it was 1.3 before trusting it, since the version
  confound above shows "matches retail" is meaningless without naming the patch.

## Confirming reads (all done — 2026-11-24)

1. **Stream-selection mechanism** — the active static stream is chosen by the `.version` **postfix**, one complete
   stream per family (not a base+overlay pair): `Core/1.0` = `"_common"`, `Core/1.2` = `"_common_2"`, the 1.03
   patch = `"_mod"` → the complete `Static_mod`. Direct replacement evidence (see Evidence).
2. **Version drift, both directions** — `DefaultHotKeys` (type `0xdefca2f6`): 1.3 patch `Static_mod` =
   **`0x12cb83dc`** (= the engine-expected value = our SDK), `Core/1.0` = **`0x692d0b3a`** (the crash "got"). The
   probe died purely on stale-version data.
3. **Leaf is version-correct** — our leaf overlay's `ArmorTemplate` hash `0x6d59c409` == the 1.3 patch's — so the
   zero-import leaf crash is clean incompleteness, not drift.

*The one optional direct test (airtight beyond abduction):* build a **version-correct complete `Static_mod` from the
patch** + an edit, via our packaging path, and launch — if it loads and the edit takes effect, "a correct partial
cannot load / a complete one can" moves from inference to observation, and it doubles as a working local mod
(Option 2). Feasible (`102texturefix.big` is 31 MB; `Static_mod` is manifest 2.5 MB + bin 24.6 MB). Low priority
given the convergent evidence; offered to the user.

## Reproduce (exact commands, for a fresh agent)

All reads are off the user's own installed game; no EA bytes are committed. `GI` = the KW install dir
(`openwrath show` → `game_install`); `MODS` = the Mods dir; `BM` = the SDK base-manifests dir.

```sh
# EA's 1.03 patch ships a COMPLETE Static_mod (21,747 assets) + Static.version="_mod":
BIG=$(find "$GI/Patch103" -iname '102texturefix.big' | head -1)        # 31 MB
python3 modkit/lib/biglist.py "$BIG" | grep -iE 'static.*(manifest|version)'
python3 modkit/lib/bigextract.py "$BIG" "Static_mod.manifest" /tmp/x    # then read manifest header[2]=AssetCount
#   Static.version / Static_l.version = b"_mod\n"; Static_mod: 21747 assets (retail static_common = 21435)

# Postfix selection — one complete stream per family (replacement, not overlay):
#   Core/1.0/StaticStream.big  data\static.version = b"_common\r\n"   -> static_common
#   Core/1.2/patch2.big        data\static.version = b"_common_2\r\n" -> static_common_2
#   Patch103/102texturefix.big data\Static.version = b"_mod\n"        -> Static_mod (the active 1.3 stream)

# Version drift that crashed the complete-probe (DefaultHotKeys, type 0xdefca2f6), both directions:
#   1.3 patch Static_mod TypeHash = 0x12cb83dc (== engine-expected == SDK static_common_2)
#   Core/1.0 static_common  TypeHash = 0x692d0b3a   (the crash "got")
# Leaf is version-correct (so its crash = incompleteness, not drift):
#   our leaf overlay ArmorTemplate (0x3a6c5e8e) hash = 0x6d59c409 == 1.3 patch Static_mod's ArmorTemplate hash
# (read a type's hash: parse manifest entries at 48 + i*44, fields TypeId@+0, TypeHash@+8; RefPack-decompress first)

# FastHash (type-name -> TypeId) matches source/.../Hashing/FastHash.cs; h0 (stream identity) is NOT the name hash
#   FastHash("marvion_mod") = 0xf4a80cc1 != that stream's h0 0x1f289abb  -> renaming stream files is content-safe
```

## See also

- [0005](0005-mods-must-live-in-one-target-stream.md) — overrides must live in the owning stream (this explains
  *why*: there is one complete static stream).
- [0006](0006-new-assets-need-stream-insert.md) — insert path; all prior inserts were into a complete stream.
- [0010](0010-insert-must-match-target-stream-type-schema-hash.md) — the TypeHash/version-drift crash guard.
- [0015](0015-standalone-overlay-override-needs-sliced-inheritfrom-base.md) — the `.version` handshake and the
  zero-EA overlay builder.
- `docs/reference/COVERAGE.md`, `docs/design/verification-blind-spots.md` (§1 coverage, §5 input integrity, §7
  doc integrity).
