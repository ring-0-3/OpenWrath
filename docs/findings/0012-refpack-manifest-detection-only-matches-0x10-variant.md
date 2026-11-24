# 0012 — RefPack manifest detection only matches the `0x10` variant, so other variants still misreport as Xbox360

**Status:** Resolved · 2026-11-24

> **Resolution.** Discrimination now turns on the `0xFB` signature, not a sampled flags value. C#: a single
> authority `source/BinaryAssetBuilder.Decompiler/Containers/RefPack.cs` (`IsRefPack` = `data[1] == 0xFB`),
> consumed by `Manifest.cs`; the "0x10FB magic" wording is corrected to "0xFB signature". Python: `is_refpack()`
> added to the canonical `modkit/lib/refpack.py` and consumed at both `modkit/openwrath` detection sites (which
> previously tested the flags byte against `{0x10,0x90,0x11}` — the same overfit, and it missed `0x91`); the
> byte-identical orphan `pytools/refpack.py` (zero importers) was deleted so the rule has one home per language.
> Guarded by `test_is_refpack_all_variants` (all four flags variants recognized, non-RefPack rejected).

> Like [0008](0008-xinclude-xpointer-not-honored.md) and [0009](0009-decompiler-logiccommand-instance-read-desync.md),
> this is about **our own tool** (the decompiler's manifest reader), not a fact about the game's data format —
> though it turns on one: what actually identifies a RefPack stream.

## Context

The decompiler's `Manifest.Load` reads a manifest's first bytes to decide endianness. A *decompressed* manifest's
first byte is its `IsBigEndian` flag (`0` = PC/little-endian). But shipped manifests are often RefPack-compressed,
and RefPack data starts with a non-zero byte — so a compressed manifest was being misreported as an
"Xbox360 big-endian" manifest, a misleading dead end (the real cause is "it needs decompressing first").

Commit `5b79e93` added a guard to name the real cause instead of blaming the platform. **The guard is too
narrow**, and the original symptom reproduces for compressed manifests that don't use the exact byte the guard
checks.

## Finding

**RefPack is identified by its *second* byte (`0xFB`), not its first.** The first byte is a *flags* byte that
legitimately varies — `0x10`, `0x11` (bit `0x01` → 4-byte size fields), and the EA-KW **`0x90` variant**
(bit `0x80` set). The decompiler's guard matches only `_raw[0] == 0x10 && _raw[1] == 0xFB`, so any
compressed manifest whose flags byte is not exactly `0x10` **bypasses the guard** and falls through to the
endianness heuristic — where its non-zero first byte trips `IsBigEndian` and throws the very "Xbox360 is out of
scope" error the fix was meant to eliminate.

Trace a `0x90 0xFB…` manifest (the EA-KW variant documented as shipping on `static_common.bin`):

| Step | `Manifest.cs` | Result for `0x90 0xFB` |
|------|---------------|------------------------|
| RefPack guard | `_raw[0] == 0x10 && _raw[1] == 0xFB` | `0x90 != 0x10` → **skipped** |
| Endianness | `IsBigEndian = _raw[0] != 0;` | `0x90 != 0` → **true** |
| Scope check | `if (IsBigEndian) throw "…Xbox360…out of scope"` | **throws the misleading error** |

So the fix *narrowed* the bug to the one magic value it was tested against; it did not close it.

### Two root causes (both are documented project-wide failure modes)

1. **Overfitting to the sampled instance.** The fix encoded *the specific value observed* (`0x10FB`) instead of
   *the rule* (`byte[1] == 0xFB`). It fails the one-line overfitting test from
   [`../design/verification-blind-spots.md`](../design/verification-blind-spots.md): *"would this handle an
   instance we didn't sample?"* — a `0x90FB` manifest, unsampled, still breaks.
2. **Duplicated knowledge that diverged.** "What is a RefPack stream" is now defined in **two places that
   disagree**: `pytools/refpack.py` knows the signature is `byte[1] == 0xFB` with a variable flags byte (4
   variants); the new C# guard knows only `0x10`. The C# fix re-derived the rule instead of consulting the
   authority already in the repo — the architectural-entropy risk (blind spot §3) biting in the small.

## Evidence

- **Authoritative RefPack rule** — `pytools/refpack.py`: `magic = data[pos + 1]; if magic != 0xFB: raise`; and
  its header comment: *"bit `0x01` selects 4-byte … size fields; bit `0x80` means …"* and *"EA KW `0x90`
  variant (as on `static_common.bin`): bit `0x80` set, bit `0x01` clear."* The flags byte varies; only `0xFB`
  is fixed.
- **The over-narrow guard** — `source/BinaryAssetBuilder.Decompiler/Containers/Manifest.cs:53`:
  `if (_raw.Length >= 2 && _raw[0] == 0x10 && _raw[1] == 0xFB)`, falling through to
  `IsBigEndian = _raw[0] != 0;` (`:59`) and `if (IsBigEndian) throw …` (`:61–63`).
- **Introduced in** commit `5b79e93` (*"decompiler: detect RefPack-compressed manifests instead of misreporting
  Xbox360"*).

Which flags byte a *given* manifest carries depends on how it was compressed, so the specific stream that trips
this will vary; the point is the guard is strictly narrower than the format's own definition, so a lawful
RefPack manifest *can* slip through. The `0x90` variant is attested in-repo as real.

## How to apply

- **Discriminate on the signature byte, not the flags byte:**
  `if (_raw.Length >= 2 && _raw[1] == 0xFB)` → "RefPack-compressed; decompress first." Leave
  `IsBigEndian = _raw[0] != 0;` for genuinely decompressed input, where `_raw[0]` really is the endianness flag.
- **Fix the wording.** The comment and exception say *"0x10FB magic"* as if that were the signature; say
  *"RefPack-compressed (0xFB signature)"* so the next reader doesn't inherit the wrong model.
- **Collapse the duplication.** Introduce a single authoritative `IsRefPack(bytes)` (second byte `== 0xFB`) that
  both the C# and Python sides use, so the rule can't diverge again — and unit-test it against harvested
  headers of each variant (`0x10/0x11/0x90/0x91` + `0xFB`). See the RefPack-consolidation note in
  [`../design/verification-blind-spots.md`](../design/verification-blind-spots.md).

## See also

- [`../design/verification-blind-spots.md`](../design/verification-blind-spots.md) — §2 (overfitting) and §3
  (entropy / duplicated knowledge); this finding is a live instance of both firing on one commit.
- [0007](0007-big-repack-must-be-fsynced-and-verified.md) — RefPack / archive handling in the big-repack path.
