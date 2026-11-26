"""Scene building: OpenWrath dataclasses -> Blender datablocks.

This is the only module that touches ``bpy``. It translates the parsed geometry /
hierarchy / container (from :mod:`w3x_xml`) into Blender meshes, an armature, and
the mesh↔bone bindings. It performs **no** format/byte logic.

It also exposes :func:`readback_mesh`, which reads a built Blender mesh back into
the same plain-Python shape — the basis of the decidable self-consistency gate
(``tests/test_self_consistency.py``): *XML values == Blender datablock values*.
"""

from __future__ import annotations

from typing import Optional

import bpy
from mathutils import Matrix, Quaternion, Vector

from . import w3x_xml as wx


# --------------------------------------------------------------------------- #
# Mesh
# --------------------------------------------------------------------------- #

_PLACEHOLDER_MAT = "OpenWrath_Untextured"


def _placeholder_material() -> bpy.types.Material:
    """One shared, neutral mid-grey material for all imported meshes. It does NOT
    attempt to reproduce the game's real textures (v1 has none) — it only makes the
    untextured state unambiguous and gives faces a lit surface instead of flat shading.
    A single shared material keeps the no-material limitation obvious."""
    mat = bpy.data.materials.get(_PLACEHOLDER_MAT)
    if mat is None:
        mat = bpy.data.materials.new(_PLACEHOLDER_MAT)
        mat.diffuse_color = (0.5, 0.5, 0.5, 1.0)
    return mat


def image_material(tex_name: str, image_path: str) -> bpy.types.Material:
    """A node material with ``image_path`` (a decoded DDS) on Base Color, UV-mapped.

    **Blender's native loader decodes the DDS** (``bpy.data.images.load``) — no pixel
    decoder is forked into the add-on (``docs/design/blender-integration.md`` / invariant 3
    at ecosystem scale). The Image Texture node samples the mesh's active UV map (already
    built in :func:`build_mesh`), so the diffuse lands UV-mapped without an explicit UV node.

    Keyed on the *texture asset name* (``OW_<name>``) and ``check_existing`` on the image, so
    meshes sharing a texture (common — a unit's parts all use one atlas) share one material
    and one image datablock instead of re-loading per mesh. This is pure scene assembly over
    an already-decoded DDS; no byte/format logic."""
    matname = f"OW_{tex_name}"
    existing = bpy.data.materials.get(matname)
    if existing is not None and existing.use_nodes:
        return existing

    mat = bpy.data.materials.new(matname)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf is None:
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)

    img = bpy.data.images.load(image_path, check_existing=True)
    tex_node = nt.nodes.new("ShaderNodeTexImage")
    tex_node.image = img
    tex_node.label = tex_name
    tex_node.location = (-400.0, 300.0)
    if bsdf is not None:
        nt.links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def _bone_name_for(bone_id: int, bone_names: Optional[dict[int, str]]) -> str:
    if bone_names and bone_id in bone_names:
        return bone_names[bone_id]
    return f"bone_{bone_id}"


def reference_bone(mesh: wx.MeshGeometry, vi: int, default: int) -> int:
    """The bone a skinned vertex's position is stored RELATIVE TO: its CHANNEL-0 influence
    (the first ``<BoneInfluences>`` slot), regardless of weight.

    A W3D skinned vertex position is authored in ONE bone's local frame — slot 0 — and the
    influence weights drive *deformation* away from the bind pose, not the bind position.
    So at the bind pose the vertex sits rigidly at ``worlds[channel0] @ v`` and does NOT
    move with the weights.

    This is NOT the max-weight bone. On the Redeemer, leg-1 foot vertices like
    ``[(87, 0.0), (88, 1.0)]`` store their position in slot-0 bone **87** (weight 0 — the
    deform happens via bone 88), so the max-weight rule placed them in bone 88's frame and
    tore the 87↔88 seam (11.96u) while the symmetric legs 2–4 stayed clean (5.31u). Reading
    the position from channel 0 drops that seam to 4.89u and restores 4-fold symmetry — the
    decidable proof the model was authored symmetric. (Verified: worst parent-child foot
    seam symmetric across all four legs; see tests. Falls back to ``default`` when unbound.)
    """
    infl = mesh.influences[vi]
    if infl:
        return infl[0][0]
    return default


def _assemble(mesh: wx.MeshGeometry, worlds: list, bone_index: int):
    """Transform decoded geometry from its authored (bone-local) space into MODEL space
    using the skeleton's bind pose. Returns (positions, normals) model-space lists.

    A W3D sub-mesh's vertices are NOT in model space — they are authored relative to a
    bone, and the engine assembles them with the bind pose:
      * RIGID  (no influences): v_model = worlds[bone_index] @ v.
      * SKINNED: v_model = worlds[channel-0 bone] @ v — the vertex's position-reference
        (slot-0) bone, placed rigidly. Reduces to the rigid case at one influence.

    Why not linear-blend skinning (Σ w_b worlds[b] @ v), and why channel-0 not max-weight?
    The stored vertex lives in ONE bone's local frame (slot 0). Blending it through *other*
    bones' matrices — or placing it by the max-weight bone when that differs from slot 0 —
    moves it out of its authored frame and tears shared edges at bone seams (the Redeemer
    foot-prong tears). At the BIND pose the weights do not move a vertex, so the rigid
    channel-0 placement is exact and seams stay continuous. (Live skeletal deformation,
    where the weights matter, is a later tier; v1 is the static bind pose.) This is scene
    assembly (bind-pose application), not format/byte logic — decode stays in the CLI.
    """
    def wm(b):
        return worlds[b] if 0 <= b < len(worlds) else None

    skinned = any(mesh.influences)
    positions, normals = [], ([] if mesh.normals else None)
    for vi in range(mesh.vertex_count):
        p = Vector(mesh.positions[vi])
        n = Vector(mesh.normals[vi]) if mesh.normals else None
        b = reference_bone(mesh, vi, bone_index) if skinned else bone_index
        m = wm(b)
        positions.append((m @ p) if m is not None else p)
        if n is not None:
            normals.append((m.to_3x3() @ n).normalized() if m is not None else n)
    return positions, normals


def build_mesh(mesh: wx.MeshGeometry,
               collection: Optional[bpy.types.Collection] = None,
               bone_names: Optional[dict[int, str]] = None,
               worlds: Optional[list] = None,
               bone_index: int = 0,
               material: Optional[bpy.types.Material] = None) -> bpy.types.Object:
    """Build a Blender object from decoded geometry. Returns the object (unlinked
    scene-side if ``collection`` is None — caller links it).

    When ``worlds`` (pivot bind matrices) is supplied, geometry is assembled into MODEL
    space via :func:`_assemble` (rigid → its bone; skinned → blended) so the sub-objects
    form the whole model. Without it (single-asset import / the geometry gate) positions
    stay exactly as decoded — bit-exact to the XML.

    ``material`` (e.g. from :func:`image_material`) is applied when given; otherwise the
    shared grey placeholder is used — the honest fallback for an OnDemand/unresolved slot."""
    if worlds is not None:
        positions, normals = _assemble(mesh, worlds, bone_index)
    else:
        positions, normals = mesh.positions, mesh.normals

    me = bpy.data.meshes.new(mesh.name)
    me.from_pydata([list(p) for p in positions], [], [list(t) for t in mesh.triangles])
    me.update()

    # --- UVs (channel 0; feed Y straight — the decoder already undid the V-flip) ---
    if mesh.uvs:
        uvl = me.uv_layers.new(name="UVMap")
        for loop in me.loops:
            uvl.data[loop.index].uv = mesh.uvs[loop.vertex_index]

    # --- vertex colours (per-vertex POINT domain) ---
    if mesh.colors:
        col = me.color_attributes.new(name="Col", type="FLOAT_COLOR", domain="POINT")
        for v, rgba in enumerate(mesh.colors):
            col.data[v].color = rgba

    # --- custom split normals (Blender normalises these) ---
    if normals:
        me.normals_split_custom_set_from_vertices([Vector(n) for n in normals])

    # --- material: the real diffuse image when resolved, else the grey placeholder ---
    me.materials.append(material or _placeholder_material())

    me.update()
    obj = bpy.data.objects.new(mesh.name, me)

    # --- bone influences -> vertex groups (named to match armature bones) ---
    if any(mesh.influences):
        groups: dict[int, bpy.types.VertexGroup] = {}
        for v in range(mesh.vertex_count):
            for bone, weight in mesh.nonzero_influences(v).items():
                g = groups.get(bone)
                if g is None:
                    g = obj.vertex_groups.new(name=_bone_name_for(bone, bone_names))
                    groups[bone] = g
                g.add([v], weight, "REPLACE")

    (collection or bpy.context.scene.collection).objects.link(obj)
    return obj


def readback_mesh(obj: bpy.types.Object) -> dict:
    """Read a built mesh back into plain Python, for the self-consistency gate.

    Returns per-vertex positions / normals / uvs / colors / influences and the
    triangle list, exactly as the importer represented them in Blender.
    """
    me = obj.data
    positions = [tuple(v.co) for v in me.vertices]

    # normals: per-corner custom normals, collapsed to per-vertex (all corners of a
    # vertex share its custom normal). A vertex not referenced by any face has no
    # corner and therefore no stored custom normal — its entry stays None. We keep
    # those Nones in the list (rather than discarding the whole readback) so the gate
    # can compare only the vertices that actually carry a normal and report the rest
    # honestly. ``normals is None`` is reserved for "the corner-normal API is
    # unavailable" (old Blender) — a different, real failure.
    normals = None
    try:
        cn = me.corner_normals  # Blender 4.1+/5.x
        per_vertex = [None] * len(me.vertices)
        for loop in me.loops:
            per_vertex[loop.vertex_index] = tuple(cn[loop.index].vector)
        normals = per_vertex
    except (AttributeError, RuntimeError):
        normals = None

    uvs = None
    if me.uv_layers:
        uvl = me.uv_layers[0]
        per_vertex = [None] * len(me.vertices)
        for loop in me.loops:
            per_vertex[loop.vertex_index] = tuple(uvl.data[loop.index].uv)
        uvs = per_vertex

    colors = None
    if me.color_attributes:
        ca = me.color_attributes[0]
        colors = [tuple(ca.data[v].color) for v in range(len(me.vertices))]

    # influences: vertex group index -> name; gather per vertex {name: weight}
    gname = {g.index: g.name for g in obj.vertex_groups}
    influences = []
    for v in me.vertices:
        influences.append({gname[ge.group]: ge.weight for ge in v.groups})

    triangles = []
    for poly in me.polygons:
        vi = list(poly.vertices)
        if len(vi) == 3:
            triangles.append(tuple(vi))

    return {
        "vertex_count": len(me.vertices),
        "positions": positions,
        "normals": normals,
        "uvs": uvs,
        "colors": colors,
        "influences": influences,   # per vertex: {group_name: weight}
        "triangles": triangles,
    }


# --------------------------------------------------------------------------- #
# Armature (W3DHierarchy)
# --------------------------------------------------------------------------- #

_BONE_LEN = 0.05  # display length for leaf/standalone bones (viewer cosmetics only)


def _pivot_world_matrices(hier: wx.Hierarchy) -> list[Matrix]:
    """Accumulate each pivot's local (translation, rotation) into world matrices.
    Pivots are stored parent-before-child (parent index < own index), so a single
    forward pass suffices."""
    world: list[Matrix] = []
    for i, p in enumerate(hier.pivots):
        x, y, z, w = p.rotation
        local = Matrix.Translation(Vector(p.translation)) @ Quaternion((w, x, y, z)).to_matrix().to_4x4()
        if p.parent < 0 or p.parent >= i:
            world.append(local)
        else:
            world.append(world[p.parent] @ local)
    return world


def build_armature(hier: wx.Hierarchy,
                   collection: Optional[bpy.types.Collection] = None
                   ) -> tuple[bpy.types.Object, dict[int, str], list[Matrix]]:
    """Build an armature from the hierarchy. Returns (object, {pivot_index: bone_name},
    pivot_world_matrices).

    Bone names are the pivot names (deduped on collision) so mesh vertex groups
    and the Armature modifier bind by name. The pivot world matrices are returned
    (not discarded) because a RIGID sub-object's geometry is authored in its bone's
    local space and must be drawn at that bone's WORLD matrix — the binder needs
    them to place rigid parts (otherwise every rigid part scatters to its bone tail).
    """
    arm = bpy.data.armatures.new(hier.name)
    obj = bpy.data.objects.new(hier.name, arm)
    (collection or bpy.context.scene.collection).objects.link(obj)

    worlds = _pivot_world_matrices(hier)

    bone_names: dict[int, str] = {}
    used: set[str] = set()
    for i, p in enumerate(hier.pivots):
        base = p.name or f"pivot_{i}"
        name = base
        n = 1
        while name in used:
            name = f"{base}.{n:03d}"
            n += 1
        used.add(name)
        bone_names[i] = name

    prev_active = bpy.context.view_layer.objects.active
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        ebs = arm.edit_bones
        created = []
        for i, p in enumerate(hier.pivots):
            eb = ebs.new(bone_names[i])
            head = worlds[i].translation
            # Orient the bone along its own local Y so rotation is visible.
            direction = worlds[i].to_3x3() @ Vector((0.0, 1.0, 0.0))
            if direction.length < 1e-8:
                direction = Vector((0.0, 1.0, 0.0))
            eb.head = head
            eb.tail = head + direction.normalized() * _BONE_LEN
            created.append(eb)
        for i, p in enumerate(hier.pivots):
            if 0 <= p.parent < len(created):
                created[i].parent = created[p.parent]
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.context.view_layer.objects.active = prev_active

    return obj, bone_names, worlds


# --------------------------------------------------------------------------- #
# Container (HLod) — ties meshes to the armature
# --------------------------------------------------------------------------- #

def bind_mesh_to_armature(mesh_obj: bpy.types.Object,
                          arm_obj: bpy.types.Object,
                          sub: wx.SubObject,
                          bone_names: dict[int, str],
                          worlds: Optional[list[Matrix]] = None) -> None:
    """Attach an already-assembled mesh to the armature for scene organisation.

    The mesh geometry is baked into MODEL space at build time (:func:`_assemble` —
    rigid at its bone, skinned blended), so the object sits at identity and needs no
    object/bone transform here; a simple OBJECT parent keeps the scene tidy. Vertex
    groups are preserved on skinned meshes for a future exporter / skeletal-deform tier
    (v1 shows the static bind pose — stated-tier, no animation)."""
    mesh_obj.parent = arm_obj


def build_collision_box(sub: wx.SubObject,
                        box: Optional[wx.CollisionBox] = None,
                        arm_obj: Optional[bpy.types.Object] = None,
                        worlds: Optional[list[Matrix]] = None,
                        collection: Optional[bpy.types.Collection] = None
                        ) -> bpy.types.Object:
    """Collision boxes are not render geometry — represent as a wire CUBE empty, kept
    clearly separate from imported meshes.

    When the referenced ``W3DCollisionBox`` asset is resolved (``box``), the empty is
    sized to its real half-extents and positioned at its centre, placed at the same
    bone world matrix as a rigid sub-object (``worlds[sub.bone_index]``) — so the box
    sits on the model instead of being a unit cube at the origin. Blender's CUBE empty
    draws edges at ±``empty_display_size`` per axis; with size 1 and object scale set to
    the half-extent, the wireframe spans ±extent exactly.
    """
    empty = bpy.data.objects.new(f"COLLISION_{sub.render_name or sub.sub_object_id}", None)
    empty.empty_display_type = "CUBE"
    empty.empty_display_size = 1.0
    (collection or bpy.context.scene.collection).objects.link(empty)
    if arm_obj is not None:
        empty.parent = arm_obj
    if box is not None:
        world = Matrix.Identity(4)
        if worlds is not None and 0 <= sub.bone_index < len(worlds):
            world = worlds[sub.bone_index]
        # centre is in the bone's local space; place, then scale to the half-extents.
        empty.matrix_world = world @ Matrix.Translation(Vector(box.center))
        empty.scale = Vector(box.extent)
    return empty
