# OpenWrath Model Importer (Blender) — milestone 1: read-only viewer

A Blender add-on that opens a shipped **Kane's Wrath** model (a `W3DContainer` with its
`W3DHierarchy` and `W3DMesh` assets) in Blender: meshes with correct geometry, an armature
from the hierarchy, and each mesh parented/skinned to the right bone.

It is a **thin front-end to the OpenWrath CLI.** It reimplements **no** W3D format logic —
every byte⇄XML conversion goes through `bab-decompile`; the add-on only translates that XML
into Blender datablocks. This is deliberate: a second format parser inside a plugin would
drift from the verified toolchain (see `docs/design/blender-integration.md` and CLAUDE.md
invariant 3). **Read-only — no exporter in this milestone.**

## Architecture

```
shipped .bin/stream ──bab-decompile --semantic-mesh──▶ W3X XML ──add-on──▶ Blender scene
```

| module | responsibility |
|---|---|
| `openwrath_import/w3x_xml.py`     | parse decompiled XML → dataclasses. **The one source of format knowledge.** Pure stdlib (no `bpy`). |
| `openwrath_import/cli.py`         | shell out to `bab-decompile`. Knows only how to *invoke* it. |
| `openwrath_import/scene_builder.py` | dataclasses → Blender mesh / armature / bindings (the only `bpy` module). |
| `openwrath_import/__init__.py`    | the `File > Import` operator + orchestration. |

## Install

Requires **Blender 4.1+** (developed and tested on 5.2 LTS).

1. Zip the add-on package (the folder, not its contents):
   ```bash
   cd blender && zip -r openwrath_import.zip openwrath_import
   ```
2. Blender → *Edit > Preferences > Add-ons > Install…* → pick `openwrath_import.zip`.
3. Enable **"OpenWrath Model Importer (Kane's Wrath)"**.

(For development you can instead symlink `blender/openwrath_import` into your Blender
`scripts/addons/` and use *Reload Scripts*.)

## Import workflow

`File > Import > OpenWrath Model (.xml)` and pick a **decompiled** asset XML:

- a `W3DContainer` → imports the whole model (hierarchy + all referenced meshes, bound);
- a `W3DHierarchy` → imports just the armature;
- a `W3DMesh` → imports just that mesh.

**Resolving a container's referenced assets.** Two options:
- *Pre-decompile a whole model into one folder* (recommended). Decompile the container, its
  hierarchy, and every mesh into the same directory; the importer finds siblings by name. It
  accepts **both** output conventions: `<name>.xml` (from `decompile --only`) and the
  type-qualified `<TypeName>.<name>.xml` (from `decompile-stream`). Zero extra config.
- *On-demand decompile.* In the import dialog set the **Stream manifest** (and, if needed,
  the **bab-decompile command**, **Schema**, **Reference manifests**, **String hashes**);
  the add-on will run `bab-decompile --semantic-mesh` for any referenced asset not already
  present as a sibling XML.

> **Meshes must be decompiled with `--semantic-mesh`.** Without it `bab-decompile` emits the
> packed `<VertexData>` base64 pass-through (correct for byte-exact re-pack, but *not* editable
> geometry). The importer detects this and tells you to re-decompile.

Example (one model, pre-decompiled):

```bash
D=/tmp/ow_model
for A in <CONTAINER> <HIERARCHY> <MESH1> <MESH2> ...; do
  dotnet Debug/bab-decompile.dll decompile <stream.manifest> \
    --only "$A" --outdir "$D" --semantic-mesh \
    --rm "<ref1.manifest;ref2.manifest>" --schema schemas/kw/xsd/CnC3Types.xsd
done
# then File > Import > OpenWrath Model → $D/<CONTAINER>.xml
```

## Tests

```bash
blender/tests/run_tests.sh
```

Two tiers (kept distinct — `docs/design/verification-blind-spots.md` §4):

1. **Decidable self-consistency gate** (`tests/test_self_consistency.py`, under Blender).
   Parses a mesh XML, builds the Blender mesh, reads the datablock back, and asserts it
   equals the XML: **bit-exact (float32)** for vertex count, every position, UVs, vertex
   colours, and per-vertex bone index+weight; topology exact. Green ⇒ the import is a
   faithful reconstruction of **what OpenWrath decoded**. This is the viewer's analogue of
   the round-trip gate. It runs against the committed synthetic cube by default, or your own
   model via `OW_MESH_FIXTURE=…` (see `tests/fixtures/README.md`).
   - **Proxy caveat → close the loop.** The committed fixtures are hand-authored from the
     decode producers/schema, so by default the gate proves "importer matches our *believed*
     XML shape," not "matches real CLI output." Regenerate a fixture **from the CLI** with
     `tests/make_fixture.sh {mesh|model} <stream.manifest> <ASSET>` (maintainer, needs game
     data; writes to gitignored `tests/fixtures/local/`) and run the gate against it — that
     converts the gate from "vs belief" to "vs ground-truth-shaped input."
   - **Normals are a STATED tolerance, not bit-exact**: Blender stores custom split normals
     as int16-encoded directions, so a shipped float32 normal round-trips only to ~1e-4. The
     importer feeds the exact decoded normals in; the gate's ~2e-4 tolerance covers only
     Blender's own storage quantisation. We bucket this honestly rather than claim exactness.

2. **Parser tests** (`tests/test_parser.py`, plain `python3`, no Blender).

## Manual visual acceptance (STATED tier — maintainer-run, needs the GUI + your model)

The gate above proves faithful *decode reconstruction*; it does **not** prove the model looks
right on screen. That is a weaker, **stated** tier — never reported as byte-exact — and it
needs a Blender GUI and your own legally-owned model, so it cannot be automated here. Run it
by hand:

1. Pre-decompile a known unit's model (container + hierarchy + meshes) into one folder as above.
2. Launch Blender (GUI), install+enable the add-on, `File > Import > OpenWrath Model` → the
   container XML.
3. Verify, by eye:
   - [ ] **Geometry**: the mesh is the right shape; no collapsed/exploded/scrambled faces.
   - [ ] **Orientation**: model stands upright and faces a sensible axis (note: SAGE is
         Z-up; if it looks rotated, that is a known coordinate-convention limitation, below).
   - [ ] **Skeleton**: the armature's bones sit inside the mesh at plausible joints; the
         hierarchy (parenting) matches the unit's articulation.
   - [ ] **Grouping/binding**: sub-meshes are attached to the correct bones (move a bone in
         Pose mode — the right geometry follows).
   - [ ] **UVs**: open the UV editor — islands are laid out in 0..1, not flipped vertically
         (the decoder already un-flips V; verify the direction once against a textured ref).
   - [ ] **Collision boxes** appear as separate wire-cube empties, clearly not render geometry.
4. Record the result (unit name, patch version, screenshot) as a stated observation.

## v1 limitations (known, not half-built)

- **No animation.** `W3DAnimation` is still a compressed-channel *byte* pass-through, not
  keyframes; it needs a separate semantic channel decode. Only the rest pose is imported.
- **No materials.** `FXShaderMaterial` is not mapped; meshes get Blender's default material.
- **No textures.** DDS is not loaded. (DDS *display* could be added read-only later; DDS
  *encoding* is the frontier tier and out of scope.)
- **No exporter.** Read-only. Export is staging step 3, gated on the re-pack equality gate
  (`tools/mesh-repack-gate.sh`), a separate milestone.
- **Coordinate convention is passed through verbatim** (no axis remap applied). If models
  import rotated relative to Blender's Z-up, a documented global transform is the fix — left
  out of v1 so the self-consistency gate compares raw decoded values.
- **Lossy-on-decode cases are inherited from the CLI**, not introduced here: a mesh authored
  with more influence channels than the packer wrote keeps a weight-0 "ghost" influence
  (inert in the viewer); secondary dropped influences are a genuine decode loss (finding 0025).
