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

def _bone_name_for(bone_id: int, bone_names: Optional[dict[int, str]]) -> str:
    if bone_names and bone_id in bone_names:
        return bone_names[bone_id]
    return f"bone_{bone_id}"


def build_mesh(mesh: wx.MeshGeometry,
               collection: Optional[bpy.types.Collection] = None,
               bone_names: Optional[dict[int, str]] = None) -> bpy.types.Object:
    """Build a Blender object from decoded geometry. Returns the object (unlinked
    scene-side if ``collection`` is None — caller links it)."""
    me = bpy.data.meshes.new(mesh.name)
    me.from_pydata([list(p) for p in mesh.positions], [], [list(t) for t in mesh.triangles])
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
    if mesh.normals:
        me.normals_split_custom_set_from_vertices([Vector(n) for n in mesh.normals])

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
    # vertex share its custom normal).
    normals = None
    try:
        cn = me.corner_normals  # Blender 4.1+/5.x
        per_vertex = [None] * len(me.vertices)
        for loop in me.loops:
            per_vertex[loop.vertex_index] = tuple(cn[loop.index].vector)
        if all(n is not None for n in per_vertex):
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
                   ) -> tuple[bpy.types.Object, dict[int, str]]:
    """Build an armature from the hierarchy. Returns (object, {pivot_index: bone_name}).

    Bone names are the pivot names (deduped on collision) so mesh vertex groups
    and the Armature modifier bind by name.
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

    return obj, bone_names


# --------------------------------------------------------------------------- #
# Container (HLod) — ties meshes to the armature
# --------------------------------------------------------------------------- #

def bind_mesh_to_armature(mesh_obj: bpy.types.Object,
                          arm_obj: bpy.types.Object,
                          sub: wx.SubObject,
                          bone_names: dict[int, str]) -> None:
    """Bind an imported mesh to the skeleton per its SubObject.

    Skinned meshes (have vertex groups) get an Armature modifier; rigid meshes
    (none) are parented to their single bone via ``BoneIndex``.
    """
    if mesh_obj.vertex_groups:
        mesh_obj.parent = arm_obj
        mod = mesh_obj.modifiers.new(name="Armature", type="ARMATURE")
        mod.object = arm_obj
    else:
        mesh_obj.parent = arm_obj
        bone = bone_names.get(sub.bone_index)
        if bone:
            mesh_obj.parent_type = "BONE"
            mesh_obj.parent_bone = bone


def build_collision_box(sub: wx.SubObject,
                        collection: Optional[bpy.types.Collection] = None
                        ) -> bpy.types.Object:
    """Collision boxes are not render geometry — represent as a wire empty, kept
    clearly separate from imported meshes."""
    empty = bpy.data.objects.new(f"COLLISION_{sub.render_name or sub.sub_object_id}", None)
    empty.empty_display_type = "CUBE"
    (collection or bpy.context.scene.collection).objects.link(empty)
    return empty
