"""Scene reading: Blender datablocks -> OpenWrath authoring XML (the exporter).

The mirror of :mod:`scene_builder`. It reads the lossless authoring **stash** that the
importer wrote onto the Blender datablocks (``scene_builder.stash_capture``) and turns a
scene back into W3X authoring XML for the compiler. Like the rest of the add-on it holds
**no** W3D byte/format logic — the stash came from, and the emitted XML goes back through,
the OpenWrath CLI (CLAUDE.md invariant 3 / ``docs/design/blender-integration.md`` §3).

Two tiers, kept honest (``docs/design/verification-blind-spots.md`` §4):

* **byte-exact (unmodified):** the live Blender mesh still equals the stashed authoring
  geometry (verified by :func:`compare_mesh_geometry`), so the exporter re-emits the
  verbatim capture → recompiles to the shipped bytes (the 0025 re-pack result, now with
  Blender in the loop — the round-trip gate). The stash was read back from a possibly
  reloaded ``.blend`` (not the decoded XML), so a green proves Blender preserved it.
* **stated ("loads + renders"):** the mesh was edited, so the exporter rebuilds the
  geometry nodes from Blender's live mesh (:func:`live_mesh_geometry` +
  :func:`w3x_xml.rewrite_mesh_geometry`). Derived structures (AABTree / tangents /
  binormals) are dropped. This is **never** reported as byte-exact.
"""

from __future__ import annotations

import struct
from typing import Optional

import bpy

from . import w3x_xml as wx
from . import scene_builder as sb


# --------------------------------------------------------------------------- #
# Reading the stash back off a datablock
# --------------------------------------------------------------------------- #

def read_capture(idblock) -> Optional[wx.AssetCapture]:
    """Read the verbatim :class:`w3x_xml.AssetCapture` stashed on a Blender ID datablock,
    or ``None`` if it carries none."""
    js = idblock.get(sb.STASH_KEY) if idblock is not None else None
    if not js:
        return None
    return wx.capture_from_json(js)


# --------------------------------------------------------------------------- #
# The decidable coupling: does the live mesh still equal the stashed geometry?
# --------------------------------------------------------------------------- #

def _f32(x) -> bytes:
    """float32 bit pattern — the same exact-match basis the self-consistency gate uses."""
    return struct.pack("<f", float(x))


def _expected_positions(obj: bpy.types.Object, geo: wx.MeshGeometry):
    """The positions the importer PUT INTO Blender for this mesh.

    For a standalone import that is the decoded geometry verbatim. For a mesh imported as
    part of a full model the importer baked bind-pose assembly into the verts, so here we
    reproduce that EXACT transform (same :func:`scene_builder._assemble`, same world matrices
    rebuilt from the parent armature's stashed hierarchy) — so an unmodified assembled mesh
    still compares bit-exact, while a genuine edit still shows up. Returns the position list,
    or ``geo.positions`` when the mesh was not assembled / the armature can't be found."""
    if not obj.get(sb.ASSEMBLED_KEY):
        return geo.positions
    arm = obj.parent if (obj.parent is not None and obj.parent.type == "ARMATURE") else None
    hcap = read_capture(arm.data) if arm is not None else None
    if hcap is None or hcap.asset_type != "W3DHierarchy":
        return geo.positions  # can't reproduce assembly → fall back (may read as edited)
    worlds = sb._pivot_world_matrices(wx.hierarchy_from_capture(hcap))
    bone_index = int(obj.get(sb.BONE_INDEX_KEY, 0))
    positions, _ = sb._assemble(geo, worlds, bone_index)
    return [tuple(p) for p in positions]


def _group_name_to_bone_id(obj: bpy.types.Object) -> dict:
    """Map each vertex-group NAME back to its bone id, exactly as the importer named them.

    A standalone mesh import names groups ``bone_<id>`` (parsed directly). A full-model import
    names them after the armature's pivots (``scene_builder.bone_name_map``), so we rebuild that
    same map from the parent armature's stashed hierarchy and invert it. Reusing the ONE naming
    function means the inversion can't drift from how the groups were created."""
    out: dict = {}
    arm = obj.parent if (obj.parent is not None and obj.parent.type == "ARMATURE") else None
    hcap = read_capture(arm.data) if arm is not None else None
    if hcap is not None and hcap.asset_type == "W3DHierarchy":
        for idx, name in sb.bone_name_map(wx.hierarchy_from_capture(hcap)).items():
            out[name] = idx
    return out


def compare_mesh_geometry(obj: bpy.types.Object, geo: wx.MeshGeometry) -> tuple[bool, str]:
    """Return ``(unmodified, reason)``: is Blender's live mesh still bit-identical to the
    geometry the importer built from the stash, on every channel Blender stores losslessly?

    This is what makes the round-trip *coupled to the live mesh* rather than a blind stash
    dump: the exporter emits the verbatim capture ONLY when the editable Blender mesh still
    agrees with it (vertex count, every position, triangle set, UVs, colours, bone id+weight)
    — the exact comparison the self-consistency gate performs. Positions are compared against
    :func:`_expected_positions` (which reproduces any bind-pose assembly the importer applied).
    Normals/tangents/binormals are not compared here (Blender can't store them bit-exact; they
    ride verbatim in the stash)."""
    rb = sb.readback_mesh(obj)
    if rb["vertex_count"] != geo.vertex_count:
        return False, f"vertex count changed ({rb['vertex_count']} != {geo.vertex_count})"

    expected_pos = _expected_positions(obj, geo)
    for a, b in zip(rb["positions"], expected_pos):
        if tuple(_f32(c) for c in a) != tuple(_f32(c) for c in b):
            return False, "a vertex position changed"

    got_tris = sorted(tuple(sorted(t)) for t in rb["triangles"])
    exp_tris = sorted(tuple(sorted(t)) for t in geo.triangles)
    if got_tris != exp_tris:
        return False, "the triangle set changed"

    referenced = set()
    for t in geo.triangles:
        referenced.update(t)

    if geo.uvs:
        if rb["uvs"] is None:
            return False, "UV layer removed"
        for v in referenced:
            a, b = rb["uvs"][v], geo.uvs[v]
            if a is None or (_f32(a[0]), _f32(a[1])) != (_f32(b[0]), _f32(b[1])):
                return False, "a UV changed"

    if geo.colors:
        if rb["colors"] is None:
            return False, "vertex colours removed"
        for a, b in zip(rb["colors"], geo.colors):
            if tuple(_f32(c) for c in a[:4]) != tuple(_f32(c) for c in b[:4]):
                return False, "a vertex colour changed"

    if any(geo.influences):
        name_to_id = _group_name_to_bone_id(obj)
        for v in range(geo.vertex_count):
            expected = geo.nonzero_influences(v)
            got: dict = {}
            for name, w in rb["influences"][v].items():
                if name in name_to_id:
                    got[name_to_id[name]] = w
                elif name.startswith("bone_"):
                    got[int(name.split("_", 1)[1])] = w
                else:
                    got[name] = w
            if set(got.keys()) != set(expected.keys()):
                return False, "a vertex's bone set changed"
            for k in expected:
                if _f32(got[k]) != _f32(expected[k]):
                    return False, "a bone weight changed"

    return True, "unmodified"


# --------------------------------------------------------------------------- #
# Edited-path reconstruction (stated tier)
# --------------------------------------------------------------------------- #

def live_mesh_geometry(obj: bpy.types.Object) -> wx.MeshGeometry:
    """Build a :class:`w3x_xml.MeshGeometry` from Blender's LIVE mesh — the edited (stated)
    path. Normals come from Blender's corner normals (int16-quantised); bone ids are
    recovered from ``bone_<id>`` vertex-group names where present. Not byte-exact by
    construction; it only needs to load + render."""
    rb = sb.readback_mesh(obj)
    vcount = rb["vertex_count"]
    positions = [tuple(p) for p in rb["positions"]]
    normals = None
    if rb["normals"] is not None:
        normals = [tuple(n) if n is not None else (0.0, 0.0, 1.0) for n in rb["normals"]]
    uvs = None
    if rb["uvs"] is not None:
        uvs = [tuple(u) if u is not None else (0.0, 0.0) for u in rb["uvs"]]
    colors = rb["colors"]
    influences: list[list[tuple[int, float]]] = [[] for _ in range(vcount)]
    for v in range(vcount):
        for name, w in rb["influences"][v].items():
            bone = int(name.split("_", 1)[1]) if name.startswith("bone_") else 0
            influences[v].append((bone, w))
    return wx.MeshGeometry(
        name=obj.data.name,
        vertex_count=vcount,
        position_channels=[positions],
        normal_channels=[normals] if normals else [],
        uv_channels=[uvs] if uvs else [],
        colors=colors,
        influences=influences,
        triangles=[tuple(t) for t in rb["triangles"]],
    )


# --------------------------------------------------------------------------- #
# Per-target export: datablock -> (capture, tier, note)
# --------------------------------------------------------------------------- #

def export_mesh_object(obj: bpy.types.Object) -> tuple[wx.AssetCapture, str, str]:
    """Export a Blender mesh object to a W3DMesh capture. Returns ``(capture, tier, note)``
    where ``tier`` is ``"byte-exact"`` (unmodified — verbatim stash) or ``"stated"`` (edited —
    reconstructed from live geometry)."""
    cap = read_capture(obj.data)
    if cap is None:
        raise ValueError(f"mesh '{obj.name}' has no OpenWrath stash — it was not imported "
                         f"by this add-on (nothing to export byte-exact).")
    geo = wx.mesh_geometry_from_capture(cap)
    unmodified, reason = compare_mesh_geometry(obj, geo)
    if unmodified:
        return cap, "byte-exact", "unmodified (verbatim authoring stash)"
    edited = wx.rewrite_mesh_geometry(cap, live_mesh_geometry(obj))
    return (edited, "stated",
            f"edited: {reason} — geometry rebuilt from live mesh (derived AABTree/tangents/"
            f"binormals dropped); NOT byte-exact.")


def readback_collision_box(empty: bpy.types.Object) -> tuple:
    """(center, extent) from a live collision-box empty — the edited path (stated). The importer
    placed a standalone box at ``matrix_world = Translation(center)`` with ``scale = extent``, so
    its local translation + scale read those straight back."""
    center = tuple(empty.matrix_basis.translation)
    extent = tuple(empty.matrix_basis.to_scale())
    return center, extent


def readback_hierarchy(arm_data, cap: wx.AssetCapture) -> list:
    """Live armature rest bones → ``list[w3x_xml.Pivot]`` aligned to the capture's pivot order
    (the edited path — stated, LOSSY). Each capture pivot index is matched to the live bone by the
    importer's ``bone_name_map`` name; a missing/renamed bone keeps the stashed pivot's values."""
    from mathutils import Matrix
    hier = wx.hierarchy_from_capture(cap)
    names = sb.bone_name_map(hier)  # pivot index -> bone name (as the importer created them)
    pivots = list(hier.pivots)      # defaults from the stash (carried through on any mismatch)
    for i, p in enumerate(pivots):
        bone = arm_data.bones.get(names.get(i, ""))
        if bone is None:
            continue
        parent = bone.parent
        local = (parent.matrix_local.inverted() @ bone.matrix_local) if parent else bone.matrix_local
        t = local.to_translation()
        q = local.to_quaternion()  # (w, x, y, z)
        pivots[i] = wx.Pivot(name=p.name, parent=p.parent,
                             translation=(t.x, t.y, t.z),
                             rotation=(q.x, q.y, q.z, q.w),
                             fixup=p.fixup)
    return pivots


def readback_container(coll, cap: wx.AssetCapture) -> list:
    """Live collection membership + bindings → ``list[w3x_xml.SubObject]`` (the edited path —
    stated). Only objects that carry an OpenWrath stash (an imported mesh/box) become sub-objects;
    their render kind comes from the stash type and the bone index from the importer's binding."""
    subs = []
    for o in coll.all_objects:
        sid = o.get(sb.STASH_ID)
        atype = o.get(sb.STASH_TYPE)
        if not sid or atype not in ("W3DMesh", "W3DCollisionBox"):
            continue
        kind = "Mesh" if atype == "W3DMesh" else "CollisionBox"
        bone_index = int(o.get(sb.BONE_INDEX_KEY, 0))
        # SubObjectID: the trailing segment of the asset id (e.g. "NU_BUGGY_SKN.EMP" -> "EMP").
        sub_id = sid.split(".", 1)[1] if "." in sid else sid
        subs.append(wx.SubObject(bone_index=bone_index, sub_object_id=sub_id,
                                 render_kind=kind, render_name=sid))
    return subs


def export_stash_datablock(idblock, kind: str) -> tuple[wx.AssetCapture, str, str]:
    """Export a non-mesh asset (W3DHierarchy / W3DContainer / W3DCollisionBox).

    Mirrors the mesh coupling: compare the datablock's import-time fingerprint to a fresh one.
    **Match ⇒ byte-exact** (re-emit the verbatim stash — the unmodified round-trip gate's case).
    **Differ ⇒ stated** (the datablock was edited): rebuild the authoring XML from the live
    datablock and NEVER report byte-exact (verification-blind-spots §4). The fingerprint is
    bit-exact by construction, so a clean import→save→reload stays byte-exact (no false edit)."""
    cap = read_capture(idblock)
    if cap is None:
        raise ValueError(f"{kind} datablock has no OpenWrath stash.")

    stored = idblock.get(sb.STASH_FINGERPRINT)
    live = sb.fingerprint_for(cap.asset_type, idblock)
    if stored is None or live is None or live == stored:
        return cap, "byte-exact", "unmodified (verbatim authoring stash)"

    # Edited — rebuild from the live datablock, stated tier (no byte oracle; never byte-exact).
    if cap.asset_type == "W3DCollisionBox":
        center, extent = readback_collision_box(idblock)
        return (wx.rewrite_collision_box(cap, center, extent), "stated",
                "edited collision box (center/extent from live empty) — NOT byte-exact")
    if cap.asset_type == "W3DHierarchy":
        return (wx.rewrite_hierarchy(cap, readback_hierarchy(idblock, cap)), "stated",
                "edited skeleton (rebuilt from live armature; LOSSY — the viewer armature is a "
                "reduced visualisation of the pivots) — NOT byte-exact")
    if cap.asset_type == "W3DContainer":
        return (wx.rewrite_container(cap, readback_container(idblock, cap)), "stated",
                "edited container (membership/bindings from live collection) — NOT byte-exact")
    return cap, "stated", "edited graph datablock — NOT byte-exact"


# --------------------------------------------------------------------------- #
# Scene discovery
# --------------------------------------------------------------------------- #

def find_export_targets() -> list[dict]:
    """Enumerate every datablock in the current .blend that carries an OpenWrath stash.

    Each entry: ``{kind, asset_type, asset_id, obj, idblock}`` where ``kind`` is
    ``"mesh"`` / ``"armature"`` / ``"collisionbox"`` / ``"container"``. ``obj`` is the Blender
    object to export from (needed for a mesh's live-geometry coupling); ``idblock`` is the ID
    the stash lives on."""
    targets: list[dict] = []
    for obj in bpy.data.objects:
        if obj.type == "MESH" and obj.data is not None and obj.data.get(sb.STASH_KEY):
            targets.append({"kind": "mesh", "asset_type": obj.data.get(sb.STASH_TYPE, "W3DMesh"),
                            "asset_id": obj.data.get(sb.STASH_ID, ""), "obj": obj, "idblock": obj.data})
        elif obj.type == "ARMATURE" and obj.data is not None and obj.data.get(sb.STASH_KEY):
            targets.append({"kind": "armature", "asset_type": obj.data.get(sb.STASH_TYPE, "W3DHierarchy"),
                            "asset_id": obj.data.get(sb.STASH_ID, ""), "obj": obj, "idblock": obj.data})
        elif obj.type == "EMPTY" and obj.get(sb.STASH_KEY):
            targets.append({"kind": "collisionbox", "asset_type": obj.get(sb.STASH_TYPE, "W3DCollisionBox"),
                            "asset_id": obj.get(sb.STASH_ID, ""), "obj": obj, "idblock": obj})
    for coll in bpy.data.collections:
        if coll.get(sb.STASH_KEY):
            targets.append({"kind": "container", "asset_type": coll.get(sb.STASH_TYPE, "W3DContainer"),
                            "asset_id": coll.get(sb.STASH_ID, ""), "obj": None, "idblock": coll})
    return targets


def export_target(target: dict) -> tuple[wx.AssetCapture, str, str]:
    """Produce the capture + tier + note for one discovered target."""
    if target["kind"] == "mesh":
        return export_mesh_object(target["obj"])
    return export_stash_datablock(target["idblock"], target["asset_type"])
