# 0016 — The static family is a BASE + OVERLAY CHAIN (byte-facts valid; the "how to make a mod override" conclusions SUPERSEDED by 0017)

> **✅ RESOLVED — see [0017](0017-overlay-mod-overrides-base-gameplay-the-complete-recipe.md).** A loadable,
> (near-)zero-EA overlay mod that overrides base gameplay on retail 1.3 was achieved in-game on 2026-11-25. The
> **byte-level facts in this doc remain valid** (the static family *is* a base+overlay chain; the patch `Static_mod`
> *is* a 98%-deferred sparse overlay; the `.version` postfix + `\x02` base-ref mechanism). But several **conclusions
> here were WRONG and are withdrawn**: (a) "a mod's `static_mod` must carry every asset's DATA" — FALSE, sparse
> works (0.6% real data); (b) "the casing of the archived names (`Static_mod` vs `static_mod`) decides load/crash" —
> FALSE, casing was a red herring; (c) the "StreamChecksum/h0 collision gates gameplay resolution" theory — FALSE
> (it's a build-time cache key). The **actual working recipe** (sparse differential + `.version` redirect + low-LOD
> twin + WorldBuilder companion + base-sized max-chunk header + `static_common_2` defer target) and the full failure
> catalog are in **0017**. Read 0017, not the "Consequence/Confirmation" sections below, for how to build a mod.

**Status:** Byte-level chain facts VERIFIED; mod-override conclusions SUPERSEDED by [0017]. · 2026-11-24 (corrected 2026-11-25)

> **⚠ IN-GAME TESTS (2026-11-24), in order:**
> 1. **Sparse + CAPITAL names + edit** (`mod build-local` first cut, `data\Static_mod.*`) → **crashed at launch.**
> 2. **Sparse + LOWERCASE names, verbatim (no edit)** (`ovl-control`, the patch's `Static_mod` repacked as
>    `data\static_mod.*` — exactly SI's convention) → **LOADED: reached main menu, skirmish played normally.**
>
> **Conclusion:** the crash in (1) was the **archived-name casing**, not the sparse model and not the base-deferral.
> A mod-provided *sparse* `static_mod` **does** get the base-deferral the patch chain gets — the engine fills its
> 98%-zero entries from the base — **so long as the mod uses the lowercase mod convention** (`static_mod` /
> `static.version`, like SecondIsomer) rather than the patch's capitalised names. The byte-level facts (base +
> overlay chain; patch `Static_mod` is sparse) stand, and the "sparse overlay + defer" model **now holds for a mod
> stream too**, with the lowercase-naming requirement added. `build-local` was fixed to always emit lowercase.
>
> 3. **Sparse + LOWERCASE names + edit** (`gdi-missile-firerate`, rebuilt lowercase, one weapon spliced) →
>    **crashed at launch.**
>
> **Two independent bugs, both now isolated:** (1) capital-case archived names crash a mod big — fixed by always
> emitting lowercase; (2) **splicing an overlay-compiled asset into the sparse overlay crashes** — test 3 vs the
> loading test 2 differ *only* in the splice, casing controlled. So a *verbatim* sparse mod stream loads, but
> *overriding* one of its deferred (zero-size) entries with our overlay-compiled asset does not.
>
> **Likely cause (not yet proven — no crash log; KW release build writes none).** Our override is compiled in an
> *overlay* context where its dependencies are **imports** (e.g. the weapon's `…MissileWarhead`). In a COMPLETE
> target (SecondIsomer) the import resolves to a **local, real-data** copy of the warhead → works (bake-into-SI is
> proven, [0010]). In the SPARSE patch overlay the warhead entry is itself **zero-size (deferred to base)**, so the
> import appears to resolve to an empty stub rather than the base's real data → load crash. In other words: a sparse
> overlay can *defer* an unchanged asset, but *overriding* one whose data references another deferred asset needs
> the referenced asset to have real data in a stream the import can resolve — which a sparse overlay does not provide.
>
> **Consequence for the installer:** the **light** path (splice into the recipient's sparse overlay) is blocked by
> this; the robust path is a **COMPLETE** target (every asset real-data, imports resolve locally) — matching
> SecondIsomer and bake-into-SI, the only proven-working precedents. See the revised Consequence section.
>
> **`cdata` override ruled out (offline, 2026-11-24).** SecondIsomer ships `data\static_mod\cdata\*.cdata`
> per-asset blobs, which looked like a possible tiny zero-EA overlay. But all **5,887** of SI's cdata files are a
> **single TypeId `0x166B084D` — an AUDIO/streaming type** (handled by `AudioCompiler/Plugin.cs`), 300–500 KB each;
> **zero** are gameplay types (WeaponTemplate etc.). `cdata` is an audio-content cache, not a general per-asset
> override — it cannot carry a gameplay edit.
>
> **The real requirement, stated precisely:** every *import* in the spliced asset must resolve to a **real-data**
> copy of its target in a loaded stream. Two ways to guarantee that: (a) a **COMPLETE** target (all assets
> real-data — robust, heavy); or (b) co-locate the edit's **transitive dependency closure** (warhead → its FX → …)
> with real data in the overlay, leaving everything else sparse — lighter, but needs correct closure analysis and
> can cascade for complex assets (GameObjects). (a) is the safe default.

> **⚠ This finding was CORRECTED on 2026-11-24 (later the same day).** The filename
> (`…complete-replacement-not-overlay`) and the earlier conclusion — "the static `_mod` stream *replaces*
> `static_common` wholesale and must carry *every asset's data*, so a zero-EA shareable standalone is impossible" —
> were **wrong**, built on a misread. The filename is kept only so existing links don't break; read the title above.
> The corrected model and the evidence that overturned it are below.

> About **how the retail engine loads the static stream** and what it forces on `mod package` / the new
> `mod build-local` — the live-load property that findings [0005](0005-mods-must-live-in-one-target-stream.md) /
> [0015](0015-standalone-overlay-override-needs-sliced-inheritfrom-base.md) and the ROADMAP flagged as the thing only
> an in-game launch could settle.

## What the earlier version got wrong, and why

The earlier finding counted **21,747 asset entries** in the 1.03 patch's `Static_mod.manifest`, compared that to
retail `static_common`'s 21,435, and concluded `Static_mod` was a *complete, self-sufficient replacement* carrying
every asset — "spanning every type including art." **That conflated the entry *list* with the instance *data*.**

Reading the actual bytes: of `Static_mod`'s 21,747 entries, **21,363 (98%) have `InstanceDataSize == 0`.** Only
**384 carry any instance data, and they are almost entirely art** — W3DMesh (167), W3DContainer (65), Texture (57),
W3DHierarchy (39), W3DAnimation (28), W3DCollisionBox (25), plus 3 UI/settings assets. *Every gameplay type has
zero data in `Static_mod`*: WeaponTemplate 0/455, GameObject 0/1045, ArmorTemplate 0/207, UpgradeTemplate 0/186.
The big is literally `102**texturefix**.big`. `Static_mod` carries a complete entry *list* but gameplay *data* for
nothing — it is a **sparse overlay**, not a self-sufficient dataset.

## Finding (corrected)

**The static family loads as a BASE + OVERLAY CHAIN.** Core/1.0 `static_common` (195 MB, **0% zero-size**) is the
full byte pool. Each later patch ships a small **overlay** that carries a **complete entry list** (every asset's
manifest entry, with version-current TypeHashes) but **instance data only for the assets it changed**, deferring
every unchanged entry to a lower stream in the chain by (TypeId, InstanceId). The `.version` **postfix** names the
active top overlay for the family.

| Stream | Patch | `.version` postfix | entries | zero-data | `DefaultHotKeys` TypeHash | our weapon's data |
|---|---|---|---|---|---|---|
| `static_common` | Core/1.0 | `_common` | 21433 | **0%** | `0x692d0b3a` (1.0) | **1136 B (real)** |
| `static_common_1` | 1.1 | `_common_1` | 21433 | 98% | `0x12cb83dc` | 0 → defers |
| `static_common_2` | 1.2 | `_common_2` | 21435 | 98% | `0x12cb83dc` | 0 → defers |
| **`Static_mod`** | **1.3 / Patch103** | **`_mod`** | **21747** | **98%** | `0x12cb83dc` | 0 → defers |

So within the **base-game patch chain**, a sparse overlay works by deferring to the base. It needs:

1. **A complete entry list** — every asset the merged view needs, enumerated in the top overlay's manifest.
2. **Version-matched TypeHashes** — the overlay's per-type hashes must equal what the running engine expects (1.3).
3. **Instance data only for the assets it changed** — everything else stays zero-size and resolves from the base.

**⚠ But this is base-game-chain behaviour — it does NOT transfer to a mod-provided stream, as far as we have
tested.** A standalone mod that shipped a *sparse* `static_mod` satisfying all three (the patch's own overlay +
one edit) **crashed at launch** (see UPDATE banner). The deferral that makes a sparse overlay work for the patch
chain was *not* observed for a mod big. The one proven-working complete mod (SecondIsomer) ships a **complete**
(779 MB, every-asset-has-data) `static_mod`. **Open question (control test pending):** does a mod's `static_mod`
have to be complete, or can a correctly-packaged sparse mod stream defer like the chain does?

## Why the zero-EA *partial* overlay really crashed

Not for lack of *data* — for lack of *entries*. Our standalone zero-EA diff
([0015](0015-standalone-overlay-override-needs-sliced-inheritfrom-base.md)) shipped a `static_mod` manifest with
~1 entry. As the active top overlay, its manifest *is* the authoritative asset list, so the engine saw a static
world of one asset and the other ~21,746 vanished → skirmish-load crash. The fix is a **complete entry list**, not
the full EA dataset.

This also re-explains the old "complete-probe" crash (retail Core/1.0 `static_common` renamed to `static_mod`:
`Type hash mismatch for type 0xdefca2f6` (`DefaultHotKeys`), `Expected 0x12cb83dc but got 0x692d0b3a`). The probe
presented **Core/1.0** bytes (`DefaultHotKeys` hash `0x692d0b3a`) as the top overlay, but the 1.3 engine expects the
`0x12cb83dc` the 1.1+ overlays carry — requirement #2 (version-matched hashes) violated. Correct; still consistent.

## How the chain is mounted (load mechanism)

The master SkuDef (`CNC3EP1_english_1.3.SkuDef`) chains `add-config` lines and ends with `add-search-path big:`;
the `Core/1.0/config.txt` `add-big StaticStream.big` mounts the 195 MB base, `Patch103/config.txt`
`add-big 102TextureFix.big` mounts the `_mod` overlay, etc. The active postfix is **consistent with first-listed
config winning precedence**: `_mod` (Patch103, listed before `Core/1.2`) is active over `_common_2`, and mod
`add-config` lines sit first of all — which is exactly why a mod big that provides `data\Static_mod.*` shadows the
patch's copy. (Precedence direction is inferred from the ordering + the observed active postfix, not a disassembly.)

## Consequence — the distribution model (zero-EA is a hard requirement)

The fundamental tension, stated plainly: **loading the static world requires the complete, version-matched asset
set, which is ~99% EA's bytes.** A loadable mod must put that set in front of the engine. The only variable is
*where the EA bytes come from* — and OpenWrath's zero-EA rule forbids shipping them. So:

- **Bundle a complete stream** (what SecondIsomer does: 779 MB) → drop-in for the recipient, but **ships EA content →
  violates zero-EA. Not an option for us.**
- **Assemble-at-install** → the shared artifact is the user's zero-EA diff; a recipient-side installer combines it
  with the **recipient's own** base files. Zero EA on the wire. This is the path. **What the installer must produce
  depends on the OPEN QUESTION above:**
  - *If a mod can ship a sparse overlay that defers to the base* → the installer is **light**: splice the diff into
    the recipient's own (sparse) patch overlay. Small output.
  - *If a mod's `static_mod` must be complete* → the installer is **heavy**: assemble a complete stream (~200 MB)
    from the recipient's base chain + the diff, locally. Big local output, still zero EA on the wire.
- **INI / loose-file overrides** (GodMode-style) are the only *genuinely drop-in AND zero-EA* path, but limited to
  INI-exposed values — can't express arbitrary binary asset edits.

**`mod build-local` (first cut) is NOT yet a working path.** It produced a *sparse* overlay as a standalone mod,
which **crashed at launch**. It is kept as the recipient-side assembly *engine* (compile → locate recipient overlay
→ splice → pack), but whether it must switch to complete-stream assembly is the control test's outcome. The
`diff-plus-assemble-at-install` design is updated accordingly.

## Confirmation — `mod build-local` on `missilerate-poc` (offline, 2026-11-24)

Built a complete local overlay = the patch's `Static_mod` + the `GDIMissileSoldierMissileLauncher` faster-fire
override spliced in. Offline-verified end to end:

- **Pure REPLACE, no [0010] drift:** our compiled asset carries `TypeId 0x94d4d96e`, `InstanceId 0x692251f6`,
  `TypeHash 0x90aeab74` — identical TypeHash to the overlay's `WeaponTemplate` (and stable across 1.0–1.3), so the
  splice keeps the stream's schema version. Only the `InstanceHash` changes.
- **Complete + intact:** output big is a complete `BIG4` (`big_is_complete`), entries `data\Static_mod.{manifest,
  bin,relo,imp}` + `data\Static.version` (= `b"_mod\n"`, verbatim from the patch, so the mod shadows the patch
  overlay). Manifest entry count unchanged at **21,747**.
- **The edit landed:** our weapon's entry went from `InstDataSize 0` → `1136`, and those 1136 bytes are
  **byte-identical** to the compiled override. Decompiling the asset back out of the built stream yields the
  faster-fire values — `FiringDuration 0.2s` (stock `2.8s`), `ClipReloadTime 0.1–0.2s` (stock `0.4s`),
  `PreAttackDelay 0s` (stock `.2s`) — a plainly visible in-game effect.
- **Installed** to `Mods/gdi-missile-firerate/` (owned folder; no EA file written). The LOCAL-ONLY README shouts
  do-not-share and points at the zero-EA `mod package` path.

**In-game result (2026-11-24): CRASHED at launch, before the main menu.** So the artifact is byte-correct *offline*
but does **not** load as a standalone mod. The offline bytes being right while the game refuses it is the whole
point of the open question: a mod-provided sparse overlay apparently does not get the base-deferral the patch chain
gets. The build used **capital-case** archived names (`data\Static_mod.*`, matching the patch); SecondIsomer, which
loads, uses **lowercase** (`data\static_mod.*`).

**Control test (in progress):** ship the patch's `Static_mod` **verbatim (no edit), lowercase like SI**, as a
standalone mod (`ovl-control`), activate it alone, and launch. This isolates the pivotal question with casing and
the splice both controlled out:
- *Loads (plays as vanilla)* → a sparse mod stream CAN defer to the base → the earlier crash was casing/splice →
  the installer can be **light** (splice the diff into the recipient's sparse overlay).
- *Crashes* → a mod's `static_mod` must be **complete** → the installer must **assemble a complete stream** from the
  recipient's base chain. (SecondIsomer's complete 779 MB `static_mod` is the precedent.)

## Consequence — input integrity (blind spots [#1, #5](../design/verification-blind-spots.md))

- **The "running patch's stream" is the CHAIN, not one file.** The loadable 1.3 static world = Core/1.0
  `static_common` (full byte pool) + the active `_mod` overlay (complete entry list, 1.3 hashes, sparse data).
  `inputs.sha256` must baseline the **chain** and record the patch version — a single-file baseline is meaningless.
- **`COVERAGE.md` version-stamp:** TypeHashes are stable for many gameplay types across 1.0–1.3 (`WeaponTemplate`
  `0x90aeab74` throughout), but some drifted at 1.1 (`DefaultHotKeys` `0x692d0b3a`→`0x12cb83dc`). Numbers measured
  against the SDK `*_2` base are 1.2-era hashes; confirm per-type against 1.3 and stamp.

## Reproduce (exact commands, for a fresh agent)

All reads are off the user's own install; no EA bytes are committed. `GI` = the KW install dir (`openwrath show`).

```sh
# 1. Static_mod is a SPARSE overlay: 21,747 entries, 98% zero-data (only ~384 art assets carry bytes).
BIG=$(find "$GI/Patch103" -iname '102texturefix.big' | head -1)
python3 modkit/lib/bigextract.py "$BIG" "data\\Static_mod.manifest" /tmp/x
#   parse the manifest (48B hdr + N*44B entries, LE); entry field InstanceDataSize is dword #8 (0-based) at +32.
#   count entries with InstDataSize==0 -> 21363/21747; the nonzero ones are W3DMesh/Texture/W3DAnimation/...

# 2. The base+overlay CHAIN (extract each manifest; RefPack-decompress with modkit/lib/refpack.py first):
#   Core/1.0 StaticStream.big  static_common.bin   = 195 MB, static.version=_common,   0%  zero-data
#   Core/1.1 patch1.big        static_common_1.bin = 320 KB, static.version=_common_1, 98% zero-data
#   Core/1.2 patch2.big        static_common_2.bin = 392 KB, static.version=_common_2, 98% zero-data
#   Patch103 102texturefix.big Static_mod.bin      = 24.6 MB, Static.version=_mod,     98% zero-data
#   our WeaponTemplate: real 1136-byte data ONLY in Core/1.0; zero (defers) in every overlay.

# 3. Build + install the complete LOCAL mod (patch overlay + the edit), then verify:
openwrath mod build-local <project> --install
#   -> complete BIG4, 21747 entries, our entry InstDataSize 0->1136 (byte-identical to the compiled override),
#      TypeHash 0x90aeab74 preserved; decompiles to FiringDuration 0.2s (stock 2.8s).
```

## See also

- [0005](0005-mods-must-live-in-one-target-stream.md) — overrides live in the owning stream (this is *why*: the top
  overlay's manifest is the authoritative asset list).
- [0010](0010-insert-must-match-target-stream-type-schema-hash.md) — the TypeHash/version-drift crash guard
  (requirement #2 above); REPLACE is immune, which is why `build-local`'s splice is safe.
- [0015](0015-standalone-overlay-override-needs-sliced-inheritfrom-base.md) — the zero-EA diff builder (the diff
  half of Option 1).
- `docs/design/diff-plus-assemble-at-install.md` — Option 1 design.
- `docs/reference/COVERAGE.md`, `docs/design/verification-blind-spots.md` (§1, §5, §7).
- `modkit/openwrath` (`cmd_mod_build_local`, `_install_overlay_stream`, shared `_insert_drift_guard` /
  `_apply_overrides`).
