# OpenWrath Model Importer (Blender) — milestone 1: read-only viewer

A Blender add-on that opens a shipped **Kane's Wrath** model (a `W3DContainer` with its
`W3DHierarchy`, `W3DMesh` and `W3DCollisionBox` assets) in Blender: meshes with correct
geometry, an armature from the hierarchy, and every sub-object **assembled into the whole
model** via the skeleton's bind pose (rigid parts placed at their bone; skinned parts
blend-skinned) — plus collision boxes sized to their real extents.

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
| `openwrath_import/scene_builder.py` | dataclasses → Blender mesh / armature / bindings, incl. bind-pose assembly (rigid + blend-skin bake). The only `bpy` module. |
| `openwrath_import/__init__.py`    | the `File > Import` operator + orchestration. |

## Install

Requires **Blender 4.1+** (developed and tested on 5.2 LTS).

**Easiest — let the modkit do it** (reads your `~/.config/openwrath/config.toml`):

```bash
openwrath blender install          # symlinks the add-on into Blender's addons dir
# then enable it: Edit > Preferences > Add-ons > search "OpenWrath"
openwrath blender model <CONTAINER>   # decode a whole model (container+hierarchy+meshes+boxes)
openwrath blender view  <CONTAINER>   # …and launch Blender to import it in one step
```

`model`/`view` auto-fill `--semantic-mesh --schema --rm --stringhashes` from your config,
decode into the gitignored `blender/tests/fixtures/local/`, and print the exact
*File > Import* path. (`model` finds the base stream in your own install; nothing is shipped.)

**Manual install** (no modkit):

1. Zip the add-on package (the folder, not its contents):
   ```bash
   cd blender && zip -r openwrath_import.zip openwrath_import
   ```
2. Blender → *Edit > Preferences > Add-ons > Install…* → pick `openwrath_import.zip`.
3. Enable **"OpenWrath Model Importer (Kane's Wrath)"**.

(For development you can instead symlink `blender/openwrath_import` into your Blender
`scripts/addons/` and use *Reload Scripts* — this is exactly what `openwrath blender install` does.)

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
     per-corner as `short[2]` (two int16 angular offsets within the corner's lnor space).
     Resolution is finest near the reference normal (~1e-4) and coarsest far from it; the
     worst-case round-trip error **saturates at ~1.35e-2** (characterised over 262144
     directions, shape-independent — a property of the int16 encoding, not of our data).
     `NORMAL_TOL = 2.0e-2` (headroom over that ceiling). Across 41 shipped KW meshes
     (4..2224 verts, skinned+static) the worst observed is **3.78e-3**, well inside it. The
     importer feeds the exact decoded normals in; the tolerance covers only Blender's encode.
   - **Placement/assembly is tested** (container gate): each sub-object's built world-space
     centroid must match its independently-recomputed bind-pose centroid — so "assembled
     correctly" (rigid at its bone, skinned at its channel-0 bone) is a *decidable* property.
   - **Seam continuity is tested** (container gate): a centroid check cannot see a *local* tear,
     so the gate also flags any skinned vertex that a DIFFERENT one of its influencing bones
     would place much closer to its mesh-neighbours (a wrong-reference-bone tear). A **gross**
     tear (the max-weight-bone bug) FAILS; small soft-blend residuals are bucketed+reported,
     not silently passed. This is the check that would have caught the Redeemer foot tears.
   - Vertices unreferenced by any triangle have no corner, so their loop-derived UV/normal
     readback is skipped and counted (honest coverage) rather than treated as a diff.

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
   - [ ] **Textures**: in Material Preview / Rendered shading the unit shows its real diffuse
         skin (not flat grey); the import report lists how many meshes were textured vs fell
         back to the placeholder (OnDemand / unresolved slots).
   - [ ] **Assembly**: the whole model is coherent (rigid parts in place, skinned legs/body
         present and upright) — not scattered or collapsed to the origin.
   - [ ] **Collision boxes** (enable the import toggle — OFF by default) appear as wire-cube
         empties sized to the unit's real extents, in a separate hideable `<model>_Collision`
         collection, clearly not render geometry.
4. Record the result (unit name, patch version, screenshot) as a stated observation.

## v1 limitations (known, not half-built)

- **No animation — static BIND POSE only.** The model is assembled at its bind pose and bones
  carry the vertex groups for a future exporter / live-deform tier, but there is no live armature
  deform or keyframes yet. `W3DAnimation` is still a compressed-channel *byte* pass-through.
- **Rigid placement is byte-exact; skinned placement is STATED-tier.** Each sub-object's
  geometry is baked into model space via the bind pose. A **rigid** part is placed exactly at its
  bone (`worlds[bone] @ v`) — proven. A **skinned** vertex is placed rigidly by its **channel-0
  (reference) bone** — the slot its position is authored in; weights are deform-only (NOT the
  max-weight bone, which tore bone seams — the Redeemer foot/Buggy-tyre tears). This assembles
  the bind pose correctly (verified: the Redeemer's four legs come out symmetric; the seam gate
  below passes), but a handful of genuine soft-blend vertices still sit a few units off at a bone
  seam — a known **stated-tier residual**, reported (bucketed) by the gate, never called exact.
- **Base-color textures: mapped (milestone 2 + 1.5, finding 0027).** Each mesh's `<FXShader>`
  base-color slot — chosen by the ordered precedence `DiffuseTexture > Texture_0` (object shaders
  vs the effect/muzzle shaders' base map; a named constant, not a per-shader special-case) — is
  resolved to its `Texture` asset, whose `<Payload>` (a literal D3D9 DDS, finding 0024) is
  base64-decoded to a `.dds` and loaded with **Blender's native image loader** (no DDS/DXT decoder
  is forked into the add-on). It drives Base Color, UV-mapped, and the report names the slot used
  per mesh. A slot that is an `OnDemandTexture` (streamed, no payload), doesn't resolve, or a
  shader with no base-color slot falls back to the grey placeholder and is **reported** (never a
  crash, never fabricated pixels). The DDS payload's validity is **byte-decidable** (asserted in
  `tests/test_textures.py`); the material/scene *look* is **stated-tier** (no byte oracle).
  `NormalMap`/`SpecMap`/`Texture_1` and full `FXShaderMaterial` semantics are not wired yet;
  *encoding* new DDS is the frontier tier.
- **No exporter.** Read-only. Export is staging step 3, gated on the re-pack equality gate
  (`tools/mesh-repack-gate.sh`), a separate milestone.
- **Coordinate convention is passed through verbatim** (no axis remap applied). If models
  import rotated relative to Blender's Z-up, a documented global transform is the fix — left
  out of v1 so the self-consistency gate compares raw decoded values.
- **Lossy-on-decode cases are inherited from the CLI**, not introduced here: a mesh authored
  with more influence channels than the packer wrote keeps a weight-0 "ghost" influence
  (inert in the viewer); secondary dropped influences are a genuine decode loss (finding 0025).
