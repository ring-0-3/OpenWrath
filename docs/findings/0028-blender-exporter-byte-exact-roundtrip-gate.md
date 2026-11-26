# 0028 — Blender exporter + the byte-exact round-trip gate (Blender in the oracle loop)

**Status:** Verified · 2026-11-26 (milestone 2.1 — graph-type edit detection — added the same day,
closing the "v1 does not detect graph/skeleton edits" honesty gap)

> The exporter that closes the Blender round-trip tier, and — the reliability keystone — the
> **acceptance gate** that makes it decidable. [0025](0025-w3dmesh-repack-equality-gate.md)
> proved `decode ∘ W3DMeshProcessor == shipped` (300/300). An exporter adds a *second packer
> path the oracle can't see* unless its correctness is made decidable. This finding adds the
> exporter (Blender scene → W3X authoring XML → compile) **and** `tools/blender-roundtrip-gate.sh`,
> which proves the added delta — `decode ∘ Blender-scene ∘ export ∘ packer == shipped` — so the
> byte-exact oracle now reaches **all the way to Blender**. Still a thin front-end to the CLI:
> **no** W3D byte/format logic forked into Python (CLAUDE.md invariant 3 / the §3 ecosystem-scale
> drift `docs/design/blender-integration.md` exists to prevent). Extends the viewer
> ([0026](0026-blender-viewer-importer.md)/[0027](0027-blender-viewer-textured-diffuse.md)).

## The design keystone — why a naive exporter can never be byte-exact (do not re-derive)

Blender normalises geometry: it stores custom normals as **int16** (lossy — 0026 measured the
~1.3e-2 ceiling), has **no** native binormal, derives tangents from UVs, and a vertex no triangle
references carries **no loop** (so no per-corner UV/normal). So an exporter that reads Blender's
*live* mesh **cannot** reproduce the shipped bytes for an unmodified asset. The only way byte-exact
through Blender works:

> **The importer STASHES the verbatim decoded authoring attributes on the Blender datablock** (as
> a JSON ID-property that is saved into, and survives a reload of, the `.blend`). The exporter
> re-emits that stash for an *untouched* asset → byte-exact. An *edited* asset is reconstructed
> from Blender's live geometry → **stated tier** (never byte-exact).

The stash is a **generic, order-preserving element-tree capture** (`w3x_xml.capture_asset` →
`AssetCapture`) — deliberately a *dumb XML→tree copy* that knows nothing about what `<Vertices>`
or `<FXShader>` mean, so it carries **no second copy of format knowledge** (invariant 3; the
semantic readers `parse_*` remain the sole authority). Every attribute/text value is kept
**verbatim as a string**, so no float re-formatting can perturb the recompiled bytes. It
re-serialises (`serialize_capture`) to authoring XML that recompiles through the **real**
`W3DMeshProcessor.BuildVertexData` — the same packer 0025 validated, never a fork (a mesh with
`<Vertices>` and no `<VertexData>` has `IsRuntimeMesh==false`, so the compiler packs it).

### The coupling that keeps it honest (not a blind stash dump)

Storing data on a datablock and re-emitting it would pass a byte compare on its own — so the
exporter does **not** emit the stash blindly. For a mesh it first runs
`scene_reader.compare_mesh_geometry`: the **live Blender mesh must still bit-match** the stashed
authoring geometry on every channel Blender stores losslessly (vertex count, every position,
triangle set, UVs, colours, bone id+weight — the exact comparison the self-consistency gate uses).
Only then is the verbatim capture emitted (**byte-exact tier**); any mismatch means the user
edited the mesh → the geometry is rebuilt from the live mesh (**stated tier**), derived structures
(`AABTree`/`Tangents`/`Binormals`) dropped, and the tier is *reported*, never silently claimed
byte-exact. So an unmodified export is both byte-exact **and** provably coupled to the editable
Blender mesh; an edit is provably caught (`test_export_roundtrip.py` moves a vertex and asserts
the tier drops to stated).

**The graph types get the same discipline (Milestone 2.1).** `W3DHierarchy` / `W3DContainer` /
`W3DCollisionBox` carry no editable per-vertex geometry, so the mesh coupling doesn't apply —
instead the importer hashes each graph datablock's **canonical editable state** right after
building it (`scene_builder.fingerprint_*`, stored as an ID-property beside the capture):
armature bones (name + parent + rest `matrix_local`), the collision empty's local matrix, or the
container collection's membership + per-object bone binding. At export the fingerprint is
recomputed from the (reloaded) datablock: **match ⇒ byte-exact** (emit the verbatim stash),
**differ ⇒ stated** — the graph is rebuilt from the live datablock (`rewrite_hierarchy` /
`rewrite_collision_box` / `rewrite_container`) and **never** reported byte-exact. The fingerprint
is bit-exact by construction (the same function reads the same float32 properties at import and
export, which a `.blend` save/reload preserves exactly), so a clean reload cannot read as edited —
verified: the gate's unmodified graph round-trips stay byte-exact, and `test_export_roundtrip.py`
moves a bone / moves+resizes the box / changes collection membership and asserts each flips to
stated. This closes the earlier "v1 does not detect graph/skeleton edits" honesty gap.

**One subtlety — assembled meshes.** A mesh imported as part of a *full model* has bind-pose
assembly baked into its verts (0026), so the live mesh ≠ the raw decoded geometry. The coupling
reproduces the importer's **exact** assembly (same `scene_builder._assemble`, world matrices
rebuilt from the parent armature's stashed hierarchy, same `bone_name_map` inverted to recover
bone ids) before comparing — so an unmodified assembled mesh still reads byte-exact, while a real
edit still shows up. This was found by the full-Redeemer run (2 skinned meshes first mis-tiered as
"edited": the big skins' vertex groups are named after armature pivots, not `bone_<id>`, so the
bone-id inversion had to go through the one shared naming map).

## The anti-bypass property (the gate cannot be gamed)

`tools/blender-roundtrip-gate.sh` runs import→save and reload→export as **two separate Blender
processes** sharing only the `.blend` files on disk. The export process never sees the decoded XML
— so a "green" can only mean the Blender datablocks (saved + reloaded) carried every authoring
attribute. An export that secretly re-read the decoded file, or a sidecar keyed to the instance
id, or an in-memory global, would **not** survive the reload and could not pass. The comparator is
reused **unchanged** — no widened tolerance, no ignore-rule, no diff bucketed as expected.

## The gate (`tools/blender-roundtrip-gate.sh` + `.py`)

The 0025 re-pack flow with one inserted step. Per asset type: decompile all `--semantic-mesh` →
**select a reproducible sample** → **Blender import→save→RELOAD→export** (two processes) →
**recompile the *exported* XML** through the same packer → **byte-compare to the shipped stream**,
bucketed honestly. Reuse, never reimplement (invariant 3):

- `tools/mesh-repack-gate.py` — its `select` (stratified+seeded, every vertex-declaration layout
  forced in) and `compare` (byte buckets + packer-path matrix) are **imported and called as-is**.
- `tools/compare-stream.py` — the single source of truth for the stream format (manifest parser /
  stream loader / `.asset` reader), used by the above and by the graph-type comparison.
- `openwrath_import.cli.build_compile_argv` — the **one** compile invocation (added here,
  mirroring `build_decode_argv`), flags identical to the 0025 recompile step.
- TypeIds are **derived from the stream manifest** (`type-tid`), never hardcoded.

### Results (static_common, seed 42, 2026-11-26)

`tools/blender-roundtrip-gate.sh --from-binary <static_common.manifest> --sample 40 --graph-sample 20`:

```
  W3DMesh (geometry + FXShader)   compared=40  BYTEEXACT=40  (all 20 declaration layouts forced in)
  W3DHierarchy                    compared=20  BYTEEXACT=20
  W3DCollisionBox                 compared=20  BYTEEXACT=20
  W3DContainer                    compared=20  BYTEEXACT=20
  VERDICT: GREEN — Blender import→export→recompile BYTE-EXACT to shipped (mesh + 3 graph types)
```

The mesh sample forces **every one of the 20 distinct vertex-declaration layouts** the corpus
contains into the sample (inherited from the 0025 stratifier), so even a modest `--sample` exercises
single/double position, 0/1/2 normal + texcoord channels, tangent+binormal, non-white `D3DCOLOR`
vertex colours, and bones none/rigid-1/skinned-2 (FLOAT2 weights) — each surviving the full Blender
round-trip byte-exact, **including the `<FXShader>` block** (its texture references + typed
constants ride verbatim in the capture, inside the compared `W3DMesh` bytes).

**Full-model end-to-end:** the whole **NOD Redeemer** container (`W3DContainer.NUREDEEMER_SKN`:
1 container + 99-bone `W3DHierarchy` + 34 `W3DMesh` + 13 `W3DCollisionBox` = **49 assets**) imported
as one assembled model, saved, **reloaded in a fresh process**, exported (`export_all`), recompiled,
and byte-compared to shipped → **49/49 BYTEEXACT**.

## What was built / changed (all owned files; no BYO/EA file, no compiler/comparator/schema touched)

- **`blender/openwrath_import/w3x_xml.py`** — the **writer**, symmetric with the `parse_*` readers:
  `Node`/`AssetCapture`, `capture_asset`, `capture_to_json`/`capture_from_json` (the stash form),
  `serialize_capture`, `mesh_geometry_from_capture` / `hierarchy_from_capture` (derive dataclasses
  from a capture, reusing the one semantic reader — refactored `parse_mesh`/`parse_hierarchy` to
  expose an element-level entry, no second parse), and `rewrite_mesh_geometry` (the edited-path
  geometry rebuild). XML-shape knowledge stays only here.
- **`blender/openwrath_import/scene_builder.py`** — `stash_capture` + the `STASH_*`/`ASSEMBLED_*`/
  `STASH_FINGERPRINT` datablock keys; `build_mesh`/`build_armature`/`build_collision_box` now stash
  the capture (and record assembly params) and the graph **edit-detection fingerprints**
  (`fingerprint_hierarchy`/`fingerprint_collision_box`/`fingerprint_collection`/`fingerprint_for`/
  `stash_fingerprint`); `bone_name_map` extracted as the one bone-naming authority.
- **`blender/openwrath_import/scene_reader.py` (NEW)** — the `bpy` **export** module, mirror of
  `scene_builder`: `read_capture`, the mesh `compare_mesh_geometry` coupling (assembly-aware; bone-id
  inversion via the shared `bone_name_map`), `live_mesh_geometry` (edited path), the graph readbacks
  (`readback_hierarchy`/`readback_collision_box`/`readback_container`), and `export_mesh_object` /
  `export_stash_datablock` (fingerprint-coupled graph edit detection) → `(capture, tier, note)`.
- **`blender/openwrath_import/w3x_xml.py`** — plus the graph edited-path rewriters
  `rewrite_hierarchy` / `rewrite_collision_box` / `rewrite_container` (stated-tier, symmetric to the
  readers).
- **`blender/openwrath_import/__init__.py`** — `export_file` / `export_all` (headless-drivable,
  mirroring `import_file`) + the **File > Export** operator + `W3DCollisionBox` single-import; import
  paths now thread the capture to every build site.
- **`blender/openwrath_import/cli.py`** — `build_compile_argv` + `compile_asset` (the one compile
  invocation) + a `compile` CLI verb.
- **`tools/blender-roundtrip-gate.sh` + `tools/blender-roundtrip-gate.py`** — the gate, reusing
  mesh-repack-gate's select/compare and compare-stream's primitives; `tools/blender_roundtrip_driver.py`
  (runs inside Blender: `import-save` / `load-export` / `load-export-all`).
- **Tests** — `blender/tests/test_export.py` (stdlib: capture↔JSON, serialize↔recapture identity,
  `mesh_geometry_from_capture == parse_mesh`, rewrite drops-derived) + `test_export_roundtrip.py`
  (Blender: unmodified save/reload/export → byte-exact tier + identical capture; a vertex edit →
  **stated** tier; and for **each graph type** an unmodified reload stays byte-exact while a real
  edit — moved bone / moved+resized box / changed container membership — flips to **stated**), both
  wired into `run_tests.sh`. New zero-EA fixture `ow_test_box.xml`.

## Evidence — decidable vs stated (honest tiers)

**Byte-exact-verified (the gate, oracle-backed on shipped bytes):** the **unmodified** round-trip
`decode ∘ Blender(save+reload) ∘ export ∘ packer == shipped` for **W3DMesh** (incl. `<FXShader>`)
and **W3DContainer / W3DHierarchy / W3DCollisionBox**, on a reproducible stratified seed-42 sample
of `static_common` (every mesh declaration layout), plus the full 49-asset Redeemer end to end.
The packed vertex bytes are part of the compared instance buffer, so a green is oracle-verified on
exactly the bytes that matter (unlike the TypeHash/InstanceHash the comparator wildcards).

**Stated tier (no byte oracle — never byte-exact):** an **edited** mesh (geometry rebuilt from the
live Blender mesh; the self-consistency gate shows Blender stores normals only to int16, so an
edited export is lossy by construction) and the in-Blender *look*. `test_export_roundtrip.py`
asserts an edit drops to the stated tier and is reported as such.

## Honest coverage gaps (reported, not hidden)

- **Only `static_common` sampled** (the one bring-your-own stream); other streams and the
  big-endian/Xenon path are unmeasured.
- **The 0025-unverified packer paths bound what the exporter may emit** — half-float (`FLOAT16_*`),
  Xenon/big-endian, `>2` blend weights. For an unmodified asset the exporter reproduces what was
  decoded (in-bounds by construction); it does not synthesise these.
- **Edited geometry is stated tier by definition** (no shipped ground truth). The edited path also
  drops `AABTree`/`Tangents`/`Binormals` (derived) and, for a mesh that was imported *assembled*
  into a full skinned model, un-assembly of edited verts is best-effort — editing-then-exporting a
  full-model skinned mesh is stated and may need the live-deform tier.
- **Edited graph types are stated and (for the skeleton) lossy.** Edits are now *detected* (the
  fingerprint) and correctly drop to stated, but the reconstruction is bounded: the collision-box
  rebuild (center/extent from the live empty) is faithful for a standalone box; the **skeleton
  rebuild is LOSSY** — the viewer armature is a reduced visualisation of the pivots (bones are
  oriented along local Y with a fixed length, so full pivot rotation isn't recoverable from a live
  bone), and `FixupMatrix` is carried through from the stash, not re-derived; the container rebuild
  reflects membership + bindings but not deeper structural edits. None of these is ever reported
  byte-exact. What the fingerprint *cannot* see: an edit that leaves the hashed canonical state
  bit-identical (e.g. a no-op move) — correctly treated as unmodified.
- **Stash size / decode speed** are perf gaps, not correctness: the capture JSON is a few MB for a
  large mesh, and the importer still spawns one `bab-decompile` per asset (0026's deferred
  optimisation). Correctness is unaffected.

## See also

- [0025](0025-w3dmesh-repack-equality-gate.md) — the re-pack equality gate this inserts Blender
  into; [0026](0026-blender-viewer-importer.md)/[0027](0027-blender-viewer-textured-diffuse.md) —
  the viewer this extends. `docs/design/blender-integration.md` (staging step 3, the acceptance
  gate); `docs/design/verification-blind-spots.md` §4 (stated vs byte-exact) and the comparator's
  blind spot.
