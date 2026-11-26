# Test fixtures

These three `.xml` files are **hand-authored synthetic assets — zero EA content.**
They are a trivial unit cube skinned to a two-bone skeleton, written in the exact
W3X authoring-XML shape that `bab-decompile --semantic-mesh` emits. They exist so the
tests run out-of-the-box without any game data.

| file | asset | what it is |
|---|---|---|
| `ow_test_cube.xml`  | `W3DMesh`      | 8-vert cube: positions, normals, 1 UV channel, non-white vertex colours, 2 bone-influence channels, 12 triangles. |
| `ow_test_skel.xml`  | `W3DHierarchy` | 2 pivots (`root`, `arm` offset +2 on Y). |
| `ow_test_model.xml` | `W3DContainer` | binds the cube to bone 0, plus one `CollisionBox` sub-object. |

The container resolves its referenced assets by **filename = asset id + `.xml`** in this
same folder — exactly how `bab-decompile` names its output.

## The synthetic fixtures are a PROXY — close the loop with real CLI output

These committed fixtures are hand-authored from a careful reading of the decode producers
(`StructReader.ReadSemanticVertexData`, `Marshaler.W3D.cs`) and the schema. That makes the
gate certify *"the importer matches our believed XML shape"* — an informed proxy, **not**
proof it matches what `bab-decompile` actually emits. The one unverified link is
fixture==real-output. **Close it (maintainer, once, needs game data)** with the helper:

```bash
# one mesh:
blender/tests/make_fixture.sh mesh  <stream.manifest> <MESH_ASSET_NAME>
# a whole model (container + hierarchy + all referenced meshes):
blender/tests/make_fixture.sh model <stream.manifest> <CONTAINER_ASSET_NAME>
```

It decompiles **from the CLI** (always `--semantic-mesh` + `--schema`) into the gitignored
`local/` dir and prints the exact `OW_MESH_FIXTURE=… / OW_CONTAINER_FIXTURE=…` gate command.
Run the gate against that real output and reconcile any shape delta against the synthetic
fixtures. Regenerating the fixture *from* the CLI is what stops it silently drifting from
real output — it converts the gate from "vs belief" to "vs ground-truth-shaped input."

Commit **no** EA-derived XML — `local/` is gitignored for exactly this reason.

### Manual equivalent

```bash
dotnet Debug/bab-decompile.dll decompile-stream <stream.manifest> \
    --only <MESH_ASSET_NAME> --outdir blender/tests/fixtures/local --semantic-mesh \
    --rm "<ref1.manifest;ref2.manifest>" --schema schemas/kw/xsd/CnC3Types.xsd
# note: decompile-stream names files <TypeName>.<name>.xml (type-qualified).
OW_MESH_FIXTURE=blender/tests/fixtures/local/W3DMesh.<MESH_ASSET_NAME>.xml \
    blender --background --python ../test_self_consistency.py
```

The importer's reference resolver accepts **both** naming conventions — `<name>.xml`
(from `decompile --only`) and `<TypeName>.<name>.xml` (from `decompile-stream`) — so a
whole-stream decompile drops straight into the container import.
