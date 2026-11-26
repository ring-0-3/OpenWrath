# Design — Blender integration (viewer → importer → exporter)

**Status:** Proposed (design sketch) · 2026-11-25 · depends on the W3D art pillar
([0018](../findings/0018-w3dmesh-byte-exact-via-runtime-vertexdata-passthrough.md) and the W3DContainer/
W3DHierarchy/W3DCollisionBox milestone)

> How OpenWrath can let an artist edit Kane's Wrath models in Blender **without ever forking format knowledge
> into a plugin** — Blender stays a front-end to the W3X authoring XML; OpenWrath stays the single source of
> format truth. The hard part is not Blender; it is the tier the integration lives on, and keeping a *decidable*
> gate on a frontier where byte-exact stops being the right question.

## The one distinction that governs everything: round-trip tier vs. authoring tier

OpenWrath's verified capability today is the **round-trip tier**: byte-exact decompile ↔ recompile of the bytes
the game *ships*. For `W3DMesh` this is reached by **pass-through** — the decompiler emits the packed
`W3DMeshVertexData` (interleaved vertex buffer + D3D declaration + bone-remap table) as **base64**, it does *not*
decode it into semantic geometry (finding 0018). That is exactly right for "modify an existing asset and repack,"
but:

> **A base64 packed vertex blob is not editable geometry.** Blender can do nothing meaningful with it.

Blender editing requires crossing into the **authoring / semantic tier**:

- **Import:** decode the packed buffer → semantic per-vertex attributes (position, normal, UV(s), bone
  index/weight) → build a Blender mesh + armature.
- **Export:** Blender mesh/armature → W3X **authoring** XML (`<Vertices>`/`<Normals>`/`<TexCoords>`/
  `<BoneInfluences>`/…) → the compiler's existing `W3DMeshProcessor.BuildVertexData` packs it into the runtime
  form the game loads.

The export packer **already exists** in the W3X compiler (it is the re-pack path that pass-through deliberately
bypassed). So the compiler side is largely present; the missing pieces are the *semantic decode* (import) and —
the real catch — *proving the packer is trustworthy* (below).

## The frontier caveat, stated honestly

A mesh authored or edited in Blender has, for its new/edited geometry, **no shipped ground truth to compare
against.** So "byte-exact vs EA" is not the acceptance bar for authored content, *by definition*. The bar becomes
**"the game loads it and renders it correctly"** — a weaker, **stated** tier (verification-blind-spots §4). The
project rule holds: never report that tier as byte-exact to keep a checkmark green.

### Keeping a decidable gate anyway — the re-pack equality test

The frontier does **not** mean "no oracle." There is a decidable check that validates the authoring path on real
ground truth, and it is the key prerequisite milestone:

> Take a **shipped** mesh. Decode its packed buffer → semantic attributes → **re-pack** via `W3DMeshProcessor` →
> **byte-compare to the shipped packed buffer.** If it matches, the *semantic-decode + packer pair* is proven a
> faithful EA reimplementation, on EA's actual bytes.

Passing this gate is what makes Blender-authored geometry **trustworthy** instead of hopeful. It also closes a
current gap: `W3DMeshProcessor` is today **unverified** as a byte-exact EA reimplementation — only the *pass-through*
is oracle-checked. The processor has dead half-float paths, a `NotImplementedException` Xenon path, and a
`// TODO` `CompressNormalizedDirection` stub; the re-pack gate is precisely the test that would exercise and
validate (or expose) all of it. **Build this gate before trusting any Blender exporter.**

## Architecture — Blender as a front-end to the CLI, never a second parser

```
  shipped .bin / stream  ──openwrath decompile──▶  W3X XML (+ semantic geometry)  ──add-on import──▶  Blender scene
  Blender scene  ──add-on export──▶  W3X authoring XML  ──openwrath compile──▶  packed runtime .bin
```

- The integration is a **Blender Python add-on that shells out to the OpenWrath CLI** for all format work.
- **No W3D packing/parsing is reimplemented inside Blender.** Doing so would fork format knowledge into a plugin
  that drifts from the toolchain — the §3 duplication trap at ecosystem scale (verification-blind-spots §3). The
  add-on's only job is scene ⇄ XML translation; bytes are OpenWrath's alone.
- This keeps the **decidable gate reachable from the ecosystem edge**: "import a shipped asset, export it, recompile
  — does it still load / still byte-match where the packer is deterministic?" is a test the add-on can run.

## Prerequisite dependency graph

| Blender concept | OpenWrath type | Status / needs |
|---|---|---|
| Armature (skeleton) | `W3DHierarchy` | **Next milestone** (plain struct). |
| Object / LOD grouping, mesh↔bone binding | `W3DContainer` (HLod) | **Next milestone** (plain struct). |
| Mesh geometry (editable) | `W3DMesh` semantic decode **+ the re-pack equality gate** | New milestone beyond pass-through; the gate above is the acceptance test. |
| Actions / keyframes | `W3DAnimation` semantic channel decode | Pass-through gives compressed channel *bytes*, not keyframes; needs a decode of the time-coded / adaptive-delta channels. |
| Materials | `FXShaderMaterial` | Partial fidelity at best; shader semantics won't map cleanly — stated-tier. |
| Textures | DDS | Can't bit-reproduce EA's compressor — stated weaker tier (§4). |

So the current trajectory (Container/Hierarchy) is **directly on the Blender path**, not a detour.

## Staging (lowest-risk first)

1. **Viewer / importer (read-only).** Shipped asset → Blender scene. Requires only the **semantic decode**
   (mesh geometry + hierarchy as armature + container grouping). Valuable on its own; no packer-trust risk. Ship
   this first.
2. **The re-pack equality gate.** Prove `semantic-decode ∘ W3DMeshProcessor == shipped bytes` on a sampled corpus.
   This both validates the processor and unlocks a trustworthy exporter.
3. **Exporter.** Blender scene → authoring XML → compile. Gated on (2). Authored geometry is the **stated** tier
   ("loads + renders"), never claimed byte-exact.

   **The exporter's acceptance gate (critical path, not a footnote): the Blender byte-exact roundtrip.** A round-trip
   of an *unmodified* imported asset — `decode ∘ Blender-scene ∘ export ∘ packer` — MUST byte-compare **byte-exact to
   shipped** (geometry *and* textures; shipped textures already pass through byte-exact, finding 0024). This reuses the
   (2) re-pack oracle (`tools/mesh-repack-gate.sh` / `compare-stream.py`) with **Blender now in the loop**, so it
   proves the one thing (2) cannot: that the Blender scene preserves every authoring attribute losslessly — vertex
   order/identity, normals/tangents/binormals, bone-influence channel order (incl. 0025's channel-0 reference bone and
   the weight-0 unreferenced-bone channel), vertex colours, the full `<FXShader>` block, hierarchy, and container.
   Without this gate an exporter is a *second packer path the oracle can't see* (§3 at ecosystem scale); with it, the
   byte-exact oracle reaches all the way to Blender. Realistic design: stash the raw decoded attributes on the Blender
   datablocks and round-trip an untouched mesh straight back out; edited meshes go through reconstruction (stated
   tier). The gate also **bounds what the exporter may emit** — the 0025-unverified packer paths (half-float, Xenon,
   >2 blend weights) are off-limits until a corpus exercises them.

## Boundaries / non-goals

- The add-on ships **no EA content** and **no format logic** — it is a thin CLI front-end (OpenWrath's BYO/zero-EA
  stance extends to the ecosystem).
- Do not reimplement W3D parsing/packing in Python; a drift between a Blender plugin and the verified toolchain
  would re-create the §3 class of bug where the oracle can't see it.
- Authored-content fidelity is a **stated tier**, not byte-exact; the byte-exact gate applies to *round-tripping
  shipped assets* and to the *re-pack equality* test, not to new geometry.

---

*Design sketch, written while the W3D pillar is in flight. The point of writing it now is to fix the tier
distinction and the re-pack decidable gate as durable targets before the authoring-tier work starts — so Blender
integration is pursued as "a front-end to a verified toolchain," not "a plugin that knows the format."*
