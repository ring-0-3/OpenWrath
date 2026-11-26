# 0025 — W3DMesh semantic decode + the re-pack equality gate (the Blender keystone)

**Status:** Verified · 2026-11-26

> The decidable test that turns a *hopeful* Blender exporter into a *trustworthy* one. OpenWrath already
> round-trips a shipped `W3DMesh` byte-exact — but only by carrying its packed `W3DMeshVertexData` through as opaque
> base64 ([0018](0018-w3dmesh-byte-exact-via-runtime-vertexdata-passthrough.md)); a base64 blob is not editable
> geometry. This finding adds the **semantic decode** (packed buffer → per-vertex position / normal / UV / bone
> influence) and the **re-pack equality gate**: decode a shipped mesh → recompile through the *real* compiler
> packer → byte-compare to the shipped bytes. Green ⇒ the *decode ∘ `W3DMeshProcessor.BuildVertexData`* pair is a
> faithful EA reimplementation, proven on EA's own bytes. It also **exposed and fixed a real packer bug** that
> pass-through could never reach. Implements the milestones in `docs/design/blender-integration.md`.

## The mechanism — decode is the exact inverse of the Windows packer, driven by the D3D declaration

A shipped `W3DMeshVertexData` is `{int NumVertices; List<byte> VertexElementData (interleaved vertex buffer, the
`Count` field is the per-vertex STRIDE); List<byte> VertexDeclaration (D3DVERTEXELEMENT9[]); List<ushort> Bones
(the bone-remap table)}`. The **declaration is the self-describing key**: an array of 8-byte
`{short Stream; short Offset; byte Type; byte Method; byte Usage; byte UsageIndex}` entries (terminated by
`Stream==0xFF`) that names, for every attribute, where it sits in each vertex and how it is encoded. The decoder
(`StructReader.ReadSemanticVertexData`, opt-in behind `--semantic-mesh`) reads the declaration and inverts each
conversion `BuildVertexData` applies — **input-derived from the format, never pattern-matched to an instance**:

| Declaration element | Packer conversion (forward) | Decode (inverse) |
|---|---|---|
| `POSITION/NORMAL/TANGENT/BINORMAL` `FLOAT3` | `CopyDirect<Vector3>` (verbatim) | read `Vector3` verbatim → `<Vertices>/<Normals>/<Tangents>/<Binormals>` |
| `TEXCOORD` `FLOAT2` | `CopyTexCoord`: `destV = 1 − srcV` (V-flip) | `(X, 1 − Y)` → `<TexCoords>` |
| `COLOR` `D3DCOLOR` | `Vector4ToD3DCOLOR`: `A<<24｜R<<16｜G<<8｜B`, each `(uint)(c·255)` | `byte/255` → `<VertexColors>`; **all-white ⇒ omit** |
| `BLENDINDICES` `D3DCOLOR` | `ConvertBlendIndex`: 1 byte/influence = `inverseBoneMap[bone]` | `Bones[byte]` → the original bone id |
| `BLENDWEIGHT` `FLOAT{n}` | `CopyDirect<float>` × n | n per-influence weights |

Two subtleties that make it byte-exact rather than merely plausible:

- **Vertex colour is the one genuinely lossy field.** `BuildVertexData` synthesises a default-white colour when the
  authoring source carried none — so a shipped `0xFFFFFFFF` is indistinguishable from "authored white", and both
  re-pack identically. The decoder therefore **omits `<VertexColors>` whenever every vertex is white** and emits it
  otherwise; `byte/255.0f` re-encodes exactly for all 256 values (checked), so non-white colours round-trip too.
- **Bone-influence channel count `num`** = the `BLENDWEIGHT` component count when present, else 1 (`BuildVertexData`
  emits weights only when `num>1`). The two per-vertex bone bytes of a 2-bone skin live packed in the one
  `BLENDINDICES` `D3DCOLOR`; the remap table recovered from `Bones[]` reproduces `ComputeBoneMappingTable`'s sorted
  set exactly (every table entry is referenced by construction, so decoding all vertices recovers all of it).

The decode emits the **authoring** tags EA's source carried, so recompilation flows through the **existing**
packer: a mesh with `<Vertices>` and no `<VertexData>` has `IsRuntimeMesh==false`, so `Marshaler.W3D` runs
`W3DMeshProcessor.BuildVertexData`. **No vertex packing/unpacking is forked** — the gate validates the one packer
that already exists (CLAUDE.md invariant 3). Pass-through stays the default; semantic decode is opt-in.

## The bug the gate exposed — `BuildVertexDeclaration_Windows` mis-widened BlendWeight

Pass-through never calls `BuildVertexData`, so its packer had **never been byte-checked** against shipped data. The
gate's first 2-bone-skin mismatch (`GBMEDBAY_ASN.NEWSKIN`, size-exact but one byte off at the `BLENDWEIGHT`
element) pinned it immediately. EA's shipped declaration encodes the two per-vertex weights as a **single
`FLOAT2`** element (`Type=FLOAT2, Usage=BLENDWEIGHT`); the reconstruction bumped the wrong field for the extra
weight — `last.Usage += 1` (→ `BLENDINDICES`, Type left `FLOAT1`) instead of **`last.Type += 1`** (widen
`FLOAT1→FLOAT2`, Usage unchanged). The data layout (two adjacent floats) was already a `FLOAT2`, so only the
declaration byte differed — a *size-exact, byte-divergent* defect that is invisible to anything but a byte compare
of the declaration. Fixed to encode the rule (*each extra weight widens the single BlendWeight element's type*),
not the instance; verified byte-exact.

## The re-pack equality gate (`tools/mesh-repack-gate.sh` + `.py`)

`tools/mesh-repack-gate.sh --from-binary <stream.manifest> [--sample N] [--seed S] [--all]`:
decompile all meshes `--semantic-mesh` → **reproducibly + stratifiedly** sample (every distinct vertex-declaration
layout forced in — coverage of the weird on purpose, verification-blind-spots §1 — then seeded-random fill) →
recompile each through `BuildVertexData` → byte-compare to the shipped stream, bucketed honestly. Reuses
`tools/compare-stream.py`'s manifest parser/stream loader (single source of truth for the stream format). Unlike
the `TypeHash`/`InstanceHash` the comparator wildcards, the **packed vertex bytes are part of the compared instance
buffer**, so a green here *is* oracle-verified on exactly the bytes that matter.

### Results (static_common, 2026-11-26)

`tools/mesh-repack-gate.sh --from-binary <static_common.manifest> --sample 300 --seed 42`:

```
  compared=300
    BYTEEXACT          300
    SIZEOK_VALDIFF     0
    SIZEDIFF           0
    RAW-FALLBACK       0
    RECOMPILE-MISSING  0
  VERDICT: GREEN — decode∘packer byte-exact on the sample
```

**300 / 300 byte-exact** — a reproducible, **stratified** seeded draw over `static_common`'s 3420 meshes (all **20
distinct vertex-declaration layouts** forced into the sample, 0 raw-fallback). The sample exercised: single-position
283 / double-position (2-bone skin) 17; tangent+binormal 192; TexCoord channels 0 / 1 / 2+ = 3 / 248 / 49; non-white
`D3DCOLOR` vertex colours 50; bones none / rigid-1 / skinned-2 (`FLOAT2` weights) = 239 / 40 / 21. No regression:
closed-loop `Armor.xml` **207/207**, `Weapon.xml` **456/456**; `W3DMesh` pass-through still byte-exact; all three
`schema-selftest` guards pass. (`--all` gates the whole corpus; it was not run end-to-end here — the stratified 300
covers every layout shape the corpus contains.)

**Two latent compiler bugs the gate exposed and fixed, plus one decoder accommodation** (all invisible to
pass-through, which never calls the packer or the authoring marshalers):

1. **(bug) `BuildVertexDeclaration_Windows` mis-widened BlendWeight** — `last.Usage += 1` → **`last.Type += 1`** (see
   below). The 2-bone-skin declaration bug; size-exact but byte-divergent.
2. **(bug) `RGBAColor*` list marshaler was `private`** — the reflection-based `List<T>` element dispatch
   (`Marshaler.List.cs`, public-only `GetMethod`) couldn't find it, so **every mesh with non-white
   `<VertexColors>` failed to compile** ("Cannot find marshal method for type 'RGBAColor*'"). `<VertexColors>` is a
   `List<RGBAColor>` — the first authoring path to marshal `RGBAColor` as a list element, so this had never fired.
   Made public (mirrors the public `Vector2*`/`Vector3*` element marshalers). Cleared all 48 colour meshes.
3. **(accommodation, not a packer bug) Unreferenced bones in the remap table** — a mesh authored with more influence
   channels than `num = min(Vertices.Count, BoneInfluences.Count)` has a `Bones` table that lists bones the written
   blend indices never reference (the packer *correctly* drops the surplus channel's indices/weights but folds its
   bones into the table). To round-trip the table byte-exact the **decoder** emits one extra, `num`-exceeding
   `<BoneInfluences>` channel that covers the full table (so `ComputeBoneMappingTable` re-derives the identical sorted
   set); the surplus influence's per-vertex weight is a genuine, stated decode loss (weight-0, visually inert).

### Honest coverage — packer paths exercised vs. unverified

**Exercised and proven byte-exact** by the sample: single- and double-position channels, 0/1/2 normal channels,
tangent+binormal, 0/1/2 TexCoord channels, non-white `D3DCOLOR` vertex colours, and bones = none / rigid-1 /
skinned-2 (the `FLOAT2`-weight path, incl. the fixed declaration). **Reached but deliberately NOT verified** (no
shipped `static_common` instance exercises them — reported, never silently greened):

- **Half-float paths** (`CompressTexCoord`, `Vector3ToHalf4`, `FloatToHalf`) — no declaration in the corpus uses a
  `FLOAT16_*` type; the Windows packer emits full-float for these usages.
- **`CompressNormalizedDirection`** (the `// TODO` sbyte/DEC3N normal compressor) — **dead on Windows**:
  `BuildVertexData` copies normals/tangents/binormals as `FLOAT3` directly; this path belongs to the Xenon decl.
- **`BuildVertexDeclaration_Xenon`** (`throw new NotImplementedException()`) — the stream is little-endian; the
  big-endian/Xbox360 path is untouched and unproven.
- **>2 blend weights** (`FLOAT3`/`FLOAT4` `BLENDWEIGHT`) — the corpus maxes at 2; the "widen type per extra weight"
  rule generalises but is unverified beyond `FLOAT2`.
- **Zero-vertex / null `VertexData`** — 0 of 3420 (as in 0018); the decode/packer branches are defensive only.

## Go / no-go for a trustworthy Blender exporter

**GO for the round-trip tier.** The gate proves *decode ∘ packer* reproduces shipped bytes for every mesh shape
`static_common` actually ships, which is the acceptance test `docs/design/blender-integration.md` names as the
prerequisite: an importer can now surface editable geometry, and an exporter of *unmodified* imported geometry is
provably byte-faithful (a regression guard the add-on can run from the ecosystem edge). **Authored/edited geometry
remains the stated tier** ("the game loads + renders it") — it has no shipped ground truth by definition and is
never to be reported as byte-exact (verification-blind-spots §4). Blender must shell out to this CLI, never fork a
second packer. The unverified paths above gate what the exporter may *emit*: until a corpus exercises them, an
exporter that produces half-float / Xenon / >2-weight declarations is outside what the gate has proven.

## What was added / changed

- Decompiler: `StructReader.ReadSemanticVertexData` (+ `--semantic-mesh` threaded through `AssetDecompiler` and both
  `bab-decompile` verbs). Reuses `RenderFloat` and the asset accessors; adds no duplicate renderer.
- Compiler: `W3DMeshProcessor.BuildVertexDeclaration_Windows` — `last.Usage += 1` → `last.Type += 1` for extra
  blend weights (the one-line rule fix the gate exposed).
- Tools: `tools/mesh-repack-gate.sh` + `tools/mesh-repack-gate.py` (stratified seeded gate; reuses
  `compare-stream.py`). No schema file edited; no comparator weakened.

## Scope / honesty

The sample is a stratified seeded draw over `static_common` (the only sampled stream) — strong positive evidence,
not a whole-corpus or cross-stream guarantee (`--all` gates the full corpus; other streams and the Xenon path are
unmeasured). The gate is byte-decidable **only** on shipped meshes; it says nothing about new geometry, which stays
stated-tier. The vertex-colour omission is the single lossy decode: a shipped all-white mesh re-packs exactly but
its "true" authored sub-quantised colour (if any) is unrecoverable — correct for bytes and for a viewer, honest
about the loss.
