# 0018 — W3DMesh round-trips byte-exact via a runtime VertexData pass-through (+ two latent compiler/decompiler bugs it uncovered)

**Status:** Verified · 2026-11-25

> About **our own tools** (the W3X compiler marshaler, the decompiler's struct-walker, and the in-code schema
> augmentation). The direct mesh analogue of [0014](0014-runtime-w3danimation-dispatch-depends-on-schema-stamped-typeid.md)
> (W3DAnimation runtime pass-through). Adds `W3DMesh` to the byte-exact art pipeline and closes two pre-existing
> bugs that only surfaced once a mesh could reach recompilation for the first time.

## Context

A Kane's Wrath `W3DMesh` (TypeId `0xC2B1A262`, TypeHash `0xC9D7E778`) ships in its compiled **runtime** form: its
vertex data is a **packed** `W3DMeshVertexData` — an interleaved vertex buffer, a D3D vertex declaration, and a
per-mesh bone-remap table — produced at build time by `W3DMeshProcessor.BuildVertexData` from the authoring
`<Vertices>`/`<Normals>`/`<TexCoords>`/... tags. That packer is **lossy and order-sensitive** (float→`D3DCOLOR`
vertex colours; a default-white colour synthesised when none is authored; bone-index remapping; a deterministic
declaration layout), so decompress-then-re-pack cannot reproduce the shipped bytes — exactly the situation
`W3DAnimation`'s compressed channels were in. The `W3DMesh` C# struct reaches the packed block through a typeless
`void* VertexData` hook on `W3DMeshMarshalerHelper`, which the generic decompiler walker could not follow (it
emitted an empty `<VertexData/>` and lost every vertex, in both directions).

## Finding — runtime pass-through, mirroring W3DAnimation

The vertex data is carried straight through, never re-packed:

- **Decompiler** (`StructReader.ReadRuntimeVertexData`): the `W3DMeshMarshalerHelper.VertexData` `void*` is
  special-cased to read the packed `W3DMeshVertexData` block verbatim and emit a runtime `<VertexData>` element —
  `NumVertices`, `VertexStride`, base64 `VertexElementData` / `VertexDeclaration`, and a `Bones` ushort list. A
  null pointer (a mesh with no vertex data) emits nothing.
- **Compiler** (`Marshaler.W3DMeshRuntime` + a branch in `Marshal(…, W3DMeshMarshalerHelper*)`): when the mesh is
  in the runtime form (has `<VertexData>`, or has no authoring `<Vertices>`), the packed buffers are written
  straight into the `W3DMeshVertexData` layout — reproducing `BuildVertexData`'s exact Push order
  (VertexElementData → VertexDeclaration → Bones) and alignments — with no re-packing. The asset element stays
  `<W3DMesh>`, so TypeId / TypeHash are reproduced.
- **Schema (in code)** (`SchemaSet.AugmentRuntimeMeshVertexData`): EA's authoring schema declares only the source
  vertex tags, not the packed output. We add — in code, before `Compile()`, never editing a bring-your-own schema
  file (invariant 1) — an optional `<VertexData>` element at the front of the `W3DMesh` sequence and relax
  `<Vertices>` to `minOccurs=0`, so both forms validate. Guarded, idempotent, and self-tested
  (`source/schema-selftest` now asserts both the animation and the mesh binding, each with a negative control).

**The `VertexElementData.Count` quirk (do not "fix").** `BuildVertexData` stores the per-vertex **stride** in
`VertexElementData.Count`, not a byte count; the buffer is `NumVertices * stride` bytes. The decompiler carries the
stride explicitly (`VertexStride`) so a zero-vertex block still round-trips its `Count` exactly.

## Two latent bugs this uncovered (never hit before, because no mesh had ever recompiled)

1. **Decompiler — scalar lists in anonymous inline complexTypes emitted as attributes.** `AABTree`'s
   `<PolyIndices>` holds a repeated scalar child element `<P>`, but its schema type is **anonymous** (an inline
   `<xs:complexType>` under the element), so a lookup keyed by the C# struct name `TreePolyIndices` found nothing
   and the walker defaulted the `List<uint>` to a whitespace-joined **attribute** → `The 'P' attribute is not
   declared`. Fix: `SchemaIndex` now also indexes anonymous inline complexTypes under a synthetic `@elem:<name>`
   key, and `StructReader` falls back to the **element name** (the field name it recurses through) when the type
   name is not a named schema type. The fallback is applied **only** to the child-element-name lookup (the
   scalar-list element-vs-attribute decision), **not** to attribute filtering or sequence reordering: inline
   element names are not globally unique (two different `Upgrade` / `Heuristic` inline shapes exist), and
   first-wins on those keys would be wrong for attributes (could drop a real one like `Upgrade/Cost`) or ordering.
   For anonymous types `attrSet` therefore stays null (every field emitted, as before — byte-safe) and no reorder
   is attempted (their struct order already matches the sequence).

2. **Compiler — `AABTree` `**`-marshalers pushed a stack address.** `Marshal(…, AABTree** )`,
   `NodeChild**`, and `NodePoly**` called `state.Push((void**)&objT, …)` — the address of the **local parameter**
   (a stack address) — instead of `(void**)objT` (the real field slot), unlike every other correct `**` marshaler
   (`Tangent**`, `Binormal**`, `CompressionSetting**`). This recorded a stack address as a relocation source and
   never wrote the field pointer, throwing `NullReferenceException` during relocation. A copy-error that lay dormant
   because the AABTree compile path had never been exercised.

## Verification (oracle-backed, 2026-11-25)

`tools/roundtrip.sh --from-binary` / `compare-stream.py --type c2b1a262` against the shipped `static_common`
stream (`~/cnc-kw-godmod/ea-roundtrip/eastream/static_common.manifest`), **3420** `W3DMesh` instances, all
decompiling cleanly (`ok=3420, raw=0`). A reproducible random sample of **300** (seed 7) recompiles **300/300
BYTEEXACT** (`sizeok_valdiff=0, sizediff=0, 0 errors`), spanning plain meshes, skinned meshes (bone-remap tables),
and collision meshes with `AABTree`s (rocks / tiberium / trees). **No regression:** closed-loop `Armor.xml`
**207/207** and `Weapon.xml` **456/456** byte-exact; ground-truth `W3DAnimation` `ABBHIVE_D2AN` / `ABBHIVEDR_CLS`
still byte-exact; `schema-selftest` passes both guards.

## What was added / changed

- Decompiler: `StructReader.ReadRuntimeVertexData` (+ the `@elem:` anonymous-type element-name fallback);
  `SchemaIndex` inline-type indexing.
- Compiler: `Marshaler.W3DMeshRuntime.cs` (runtime pass-through writer) + a runtime branch in
  `Marshaler.W3D.cs`; fixed the three `AABTree` `**`-marshaler `&objT`→`objT` bugs.
- Core: `SchemaSet.AugmentRuntimeMeshVertexData` (in-code schema binding) + `source/schema-selftest` mesh guard.
- **No bring-your-own schema file was modified.** Like 0014, this is the **prototype** binding; it migrates into
  the schema-overlay registry once that exists (ROADMAP).

## Scope / honesty

"300/300 byte-exact (seed 7)" is a ~9% random sample of the `static_common` `W3DMesh` corpus — strong positive
evidence for the model, not a whole-corpus guarantee. `static_common` is the only sampled stream; other streams'
meshes (and the big-endian / Xenon vertex path, which is `NotImplementedException` in `W3DMeshProcessor` and
untouched here) are unmeasured. Widening is ongoing.

**Edge branches.** The pass-through has three boundary cases; their coverage, measured against the stream, is
honest about what the oracle can and cannot prove:

- **Zero bones (non-skinned mesh → empty `Bones`): verified.** 2736 of the 3420 `static_common` meshes emit an
  empty `<Bones>`, so the seed-7 sample exercises this branch heavily and round-trips byte-exact.
- **Null `VertexData` pointer, and `NumVertices=0`: unexercised by the oracle.** No shipped `static_common` mesh
  has either (0 of 3420 — every mesh allocates a vertex block with ≥1 vertex). The decompiler (emit nothing) and
  compiler (write a null pointer) branches are therefore **defensive**, not oracle-verified: a byte-exact test
  needs a shipped instance to compare against, and none exists. If such a mesh appears in another stream, this is
  the branch to re-check first.
