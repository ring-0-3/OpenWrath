# 0017 — A loadable, (near-)zero-EA overlay mod CAN override base KW gameplay: the complete recipe

**Status:** VERIFIED in-game on retail 1.3 / Patch103 (edit applies: a WeaponTemplate's fire-rate, ClipSize, and
AttackRange all took effect in a skirmish, no crash) · 2026-11-25

> This is the resolution of the long `mod package` / 0005 / 0016 saga. It supersedes 0016's wrong "a mod's
> `static_mod` must carry every asset's data" and the "stream-checksum collision gates gameplay" theory, and it
> **refines** 0005 ("a separate stream is never consulted") — a separate overlay **is** consulted, *if* it is
> activated by a `.version` redirect and structured as a proper differential. Read this before touching mod
> packaging again.

---

## TL;DR — the working recipe

A mod overrides base-game gameplay on retail 1.3 by shipping a **sparse differential static overlay**, activated by
a **`.version` redirect**. It must have **ALL** of the following — missing any one = crash-at-load or
loaded-and-silently-ignored:

1. **A COMPLETE entry list with SPARSE data.** The overlay manifest lists *every* asset of the base (the 1.2
   `static_common_2` set, **21,435** entries) but carries **instance data only for the assets you changed**; every
   other entry is zero-size and **deferred** to the base. (NOT a 1-asset partial; NOT a full real-data copy.)
2. **Postfix `_mod`, deferring (`\x02`) to `static_common_2`.** The overlay's `RefManNameBuffer` base-reference
   names `static_common_2.manifest` — the always-present 1.2 Core base, which is **schema-identical to 1.3** (see
   §Version-safety), so it is version-safe.
3. **The low-LOD twin `static_l_mod`.** A second stream, complete entry list, **zero data**, whose `\x02` base-ref
   is **`static_mod.manifest`** (it defers to the *high-LOD* mod stream, not to a low-LOD base).
4. **The WorldBuilder companion `worldbuilder_mod`.** A third stream (complete entry list, ~zero data, `\x02` →
   `worldbuilder_2.manifest`). Omitting it crashes at load — the engine wants the families consistent once you flip
   the postfix.
5. **Three `.version` redirect files**, each exactly `_mod\n` (LF, 5 bytes): `data\static.version`,
   `data\static_l.version`, `data\worldbuilder.version`. **This is the activation switch** — the engine appends the
   postfix to the family name (`static` + `_mod` → `static_mod`) and loads *your* stream. No `.version` → your big
   is mounted but never selected (loaded-and-ignored).
6. **Header fields sized from the BASE, not recomputed.** `hdr[4..6]` (Max{Binary,Relocation,Imports}ChunkSize) MUST
   keep the base manifest's values (e.g. `1398268,46572,1516`), NOT be recomputed from your sparse entries. The
   engine sizes its per-asset load buffer from these; recomputing them to your tiny data under-allocates and
   **crashes** when a deferred ~1.4 MB chunk is read from the base. The low-LOD's `hdr[3]` (TotalInstanceDataSize) =
   the high-LOD's. `hdr[1]` (AllTypesHash) must stay the base's. (This was the *final* crash we hit.)
7. **Only the `\x02` base-ref record** in `RefManNameBuffer` (strip the base's `\x01` ref-manifest records), and a
   **unique, content-derived `StreamChecksum`** (`hdr[0]`, also stamped as the 4-byte prefix of `.bin/.relo/.imp`).

Package: all 3 streams (`.manifest/.bin/.relo/.imp`) + the 3 `.version` files into one `.big`; a `.skudef` with
`add-big <mod>.big`; activate by adding `add-config …\<mod>.skudef` to the master SkuDef **above** the Core/Patch
configs. All archived names lowercase `data\…`.

**Verified artifact:** `modkit/lib/build_overlay.py` built exactly this (high-LOD `static_mod` with one edited
`WeaponTemplate`, low-LOD + worldbuilder shells), and it loaded + applied the edit in a standard-map skirmish.

---

## The byte-level structure (per stream)

Manifest = 48-byte header (`<11I>` from offset 4) + `AssetCount`×44-byte entries (`<4I7i>`:
tid,iid,th,ih,refOff,refCnt,nameOff,srcOff,instSize,reloSize,impSize) + AssetRefBuf + RefManNameBuf + AssetNameBuf +
SrcNameBuf. `.bin/.relo/.imp` = 4-byte prefix (= `StreamChecksum`) + per-asset chunks in manifest order.

Header fields (what to set vs keep for a differential overlay):
- `hdr[0]` **StreamChecksum** — recompute unique over your final entries (see `modkit/lib/retag_checksum.py`,
  which reproduces Core/1.0 `static_common`, Core/1.2 `static_common_2`, and GodMoney's stored checksums
  byte-exact: FastHash over per-asset `(TypeId,TypeHash,InstanceId,InstanceHash,RefCount)`, buffer padded to the
  .NET `MemoryStream` capacity, seeded with that capacity). Stamp it in `hdr[0]` **and** the first dword of
  `.bin/.relo/.imp`. Not an integrity hash the engine recomputes — an opaque per-stream identity.
- `hdr[1]` **AllTypesHash** — KEEP the base's (`0x12b3e763` for static). Checked at load; wrong = reject.
- `hdr[2]` **AssetCount** — the complete base list (21,435 static / 12,698 worldbuilder).
- `hdr[3]` **TotalInstanceDataSize** — your own data total for the high-LOD; for the low-LOD, set = the high-LOD's.
- `hdr[4..6]` **Max{Binary,Relocation,Imports}ChunkSize** — KEEP the base's (do NOT recompute). *The crash fix.*
- `hdr[7..10]` buffer sizes — consistent with your actual AssetRefBuf/name buffers (we keep the base's, since we
  only change one asset's data, not its refs/names).

The three streams in the working build:

| stream | entries | real-data entries | `\x02` base-ref | `.version` |
|---|---|---|---|---|
| `static_mod` (high-LOD) | 21,435 | **your edits only** (1 in the test) | `static_common_2.manifest` | `static.version=_mod\n` |
| `static_l_mod` (low-LOD) | 21,435 | 0 (shell) | **`static_mod.manifest`** | `static_l.version=_mod\n` |
| `worldbuilder_mod` | 12,698 | 0 (shell) | `worldbuilder_2.manifest` | `worldbuilder.version=_mod\n` |

Base manifests come from the **recipient's own** install (Core/1.2 `patch2.big`: `static_common_2`,
`worldbuilder_2`), version-matched to the running patch.

---

## Why each ingredient — the failure catalog

Every attempt, and the single missing piece that explains it:

| # | Attempt | Result | Missing / wrong |
|---|---|---|---|
| 1 | 1-asset partial overlay (`mod package`) | crash @ skirmish load | incomplete entry list (engine's static world had ~1 asset) |
| 2 | full 416 MB real-data stream (`build-local`, flattened) | loads, **edit ignored**, magenta | hand-flattening broke `.imp/.relo` linkage; no companion streams; collided with patch `_mod` |
| 3 | sparse `static_mod2`, **no `.version`** | inert (unchanged game) | the `.version` redirect — stream never selected |
| 4 | `_owmod` (complete list, defer `static_mod`, `static.version` only) | crash @ launch | **no low-LOD twin** (+ no worldbuilder, capital base-ref, arbitrary postfix) |
| 5 | KWBandage-style (`static_common_mod`, defer `static_common_2`, hi+lo LOD, both `.version`) | crash @ launch | **no worldbuilder companion**; low-LOD deferred to `static_l_common_2` not `static_mod`; recomputed maxchunk |
| 6 | defer-to-`static_mod` + hi+lo LOD + both `.version` | crash @ launch | **no worldbuilder**; recomputed maxchunk |
| 7 | 3 streams incl. worldbuilder, both+wb `.version` | crash @ launch | **`hdr[4..6]` recomputed → 0/1136 (buffer under-alloc)**; extra `\x01` base-refs |
| 8 | #7 with `hdr[4..6]`=base's, `\x01` stripped, low-LOD `hdr[3]`=high-LOD's | **WORKS** ✅ | — |

The two decisive late fixes: the **WorldBuilder companion** (#5→#7) and the **max-chunk header** (#7→#8).

---

## ⚠ The R23-map confound (critical testing lesson)

Several "mod crashes" were actually the **R23 / tournament map pack crashing at match start**, independent of the
mod. This masked which builds *loaded* (they did) vs which *applied the edit*. **Always test mods on a plain
standard skirmish map, never an R23/tournament map.** Distinguish three failure points explicitly: (a) crash before
the **main menu** = stream load-time (structure); (b) crash at **match start** = possibly the map; (c) loads +
plays but **no effect** = overlay not selected/consulted. A mid-saga Steam update was a non-issue (we verified
`static_common_2` was byte-identical and the SkuDef intact).

---

## Version-safety: 1.2 base is correct for the 1.3 engine

The overlay defers to `static_common_2` (the **1.2** Core base), yet runs on the **1.3** engine. This is safe and
correct: **all 73 gameplay types have byte-identical TypeHashes between `static_common_2` (1.2) and the patch
`Static_mod` (1.3)** — the schema drift was 1.0→1.1; 1.2 and 1.3 are identical. The "1.3 patch" (Patch103) is a
**texture** fix, not a gameplay-schema change (its `Static_mod` is 98% zero-data; only ~384 art assets carry
bytes). Deferring to `static_common_2` is therefore version-matched per invariant 4; the only cost is the overlay
bypasses Patch103's texture fix (cosmetic) while active. Your authored asset must be compiled `-bps` against the
**running patch's** `static_common_2` so its TypeHash matches (WeaponTemplate = `0x90aeab74` across 1.0–1.3).

---

## The reference that cracked it

We dissected a **real, confirmed-working 1.3 overlay — "Kane's Wrath Classic" v2** (kaneswrath.com, a plain zip,
read-only byte analysis, nothing executed). It is a genuine sparse stat-balance overlay: `static_mod` = 21,435
entries / **128 real** (0.6%), defer `static_common_2`; `static_l_mod` shell → `static_mod`; `worldbuilder_mod`
shell → `worldbuilder_2`; three `.version`=`_mod\n`; base's max-chunk header; unique checksums. Byte-diffing our
build against it is what surfaced the max-chunk and base-ref bugs. (The official KW Mod SDK's `BuildMod.bat` /
`KWBandage/_Extras/BuildPatch.bat` + the ModDB sample `map_mod` corroborate the same structure: `-version:_mod`,
`-bps:static_common_2.manifest`, `.version` emit.)

---

## Distribution models (project-policy decision)

Shipping a loadable overlay inherently includes the **complete entry list** (ids/type-hashes/instance-hashes/names
copied from `static_common_2` + `worldbuilder_2`) — **EA-derived metadata** (no asset *bytes*, but a derivative of
EA's manifests). Two models:

- **Strict zero-EA (OpenWrath's DEFAULT, chosen 2026-11-25):** ship only the user's **authored diff** (~1 KB) + a
  recipe; a small **bundled client-side assembler** (a standalone-packaged `build_overlay`) reconstructs the full
  overlay on the recipient's machine from **their own** `static_common_2`/`worldbuilder_2`. Nothing EA-derived
  crosses the wire. ~one-click (standard mod-installer UX) — not "install OpenWrath." Keeps the project on the clean
  side of its zero-EA identity (and off EA's DMCA radar).
- **Drop-in (LOCAL-ONLY):** the full ~6 MB overlay. Works as a plain copy-in with no tool, but **contains EA-derived
  entry-list metadata**, so OpenWrath treats it as *local-only* (for a user modding their own machine) and never
  presents it as shareable. This is how community mods (Classic, One Vision) actually ship; OpenWrath deliberately
  does not, to protect the project.

(Not legal advice — reasoning aligned with OpenWrath's stated zero-EA principle.)

---

## Mutual exclusivity + the planned multi-mod merger

The engine loads **one** static stream per family (the `.version` postfix selects it). So **two static-overlay mods
cannot both be active** — they each claim `static.version` and one wins by load order. Classic, One Vision, and an
OpenWrath overlay are mutually exclusive. INI mods (GodMode-style) likely coexist (different mechanism — verify
before promising). **To run multiple gameplay mods together, their edits must be merged into ONE overlay.** Planned
facility (go-forward): the OpenWrath installer lets a user **select N mods and bake them into a single overlay** so
all features run; clash detection/resolution (two mods editing the same asset/field) is future work. OpenWrath is
well-suited to this — it's just more declared overrides compiled into one differential.

---

## Reproduce

`modkit/lib/build_overlay.py <base_prefix> <asset_or_NONE> <base_ref_name> <out_dir> <out_stem>` builds one sparse
differential (complete entry list, data only for the spliced asset, retargeted `\x02` base-ref, base's max-chunk
header kept, unique checksum). The working build:
```sh
# high-LOD: static_common_2 + edited weapon, defer static_common_2
build_overlay.py  <sc2_prefix>  <weapon.asset>  static_common_2.manifest   <out>  static_mod
# low-LOD shell: defer to the high-LOD static_mod
build_overlay.py  <sc2_prefix>  NONE            static_mod.manifest        <out>  static_l_mod
# worldbuilder shell: defer worldbuilder_2
build_overlay.py  <wb2_prefix>  NONE            worldbuilder_2.manifest    <out>  worldbuilder_mod
# then: patch static_l_mod hdr[3] := static_mod hdr[3]; pack all 3 streams + 3 data\*.version (=b"_mod\n") into a big
# + a .skudef (add-big); activate via add-config at the top of the master SkuDef; test on a STANDARD map.
```
Bases (`sc2_prefix`, `wb2_prefix`) are extracted read-only from the recipient's own `Core/1.2/patch2.big`
(`static_common_2.*`, `worldbuilder_2.*`); the weapon `.asset` is compiled `-bps:static_common_2.manifest`.

## See also
- [0005](0005-mods-must-live-in-one-target-stream.md) — refined: an overlay IS consulted, via the `.version` redirect.
- [0016](0016-static-mod-stream-is-complete-replacement-not-overlay.md) — superseded on "must be complete data" / the
  checksum-collision theory; this finding is the resolution.
- [0010](0010-insert-must-match-target-stream-type-schema-hash.md) — version-match (why `static_common_2` is safe for 1.3).
- `docs/design/diff-plus-assemble-at-install.md` — the zero-EA distribution design.
- `modkit/lib/build_overlay.py`, `modkit/lib/retag_checksum.py`, `modkit/lib/assemble_complete_stream.py`.
