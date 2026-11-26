#!/usr/bin/env python3
"""The exporter's DECIDABLE Blender gate — run INSIDE Blender:

    blender --background --python blender/tests/test_export_roundtrip.py

Proves the exporter half of milestone 2 the way the round-trip gate relies on, but without
the compiler (that is tools/blender-roundtrip-gate.sh's job, byte-exact vs shipped):

  1. ANTI-BYPASS / lossless stash: import a mesh -> SAVE .blend -> RELOAD it -> export. The
     stash must survive the reload on the datablock, and the exported capture must be
     IDENTICAL to the original decoded capture (so the only channel between import and export
     was Blender itself). Tier == byte-exact.
  2. EDIT detection: move a vertex -> export. The coupling check must notice and drop to the
     STATED tier (never silently claim byte-exact), and the exported XML must still parse and
     reflect the edit.

Fixtures: the committed synthetic cube by default; OW_MESH_FIXTURE for a real local mesh.
Set OW_SKIP_IF_NO_FIXTURE=1 to skip instead of fail when absent.
"""
import os
import sys
import tempfile

THIS = os.path.dirname(os.path.abspath(__file__))
ADDON_ROOT = os.path.dirname(THIS)
FIXDIR = os.path.join(THIS, "fixtures")
sys.path.insert(0, ADDON_ROOT)

import bpy  # noqa: E402
import openwrath_import  # noqa: E402
from openwrath_import import w3x_xml as wx  # noqa: E402
from openwrath_import import scene_builder as sb  # noqa: E402

_fail = []
_checks = 0


def check(cond, msg):
    global _checks
    _checks += 1
    if not cond:
        _fail.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok: {msg}")


def nodes_equal(a, b):
    return (a.tag == b.tag and a.attrib == b.attrib and a.text == b.text
            and len(a.children) == len(b.children)
            and all(nodes_equal(x, y) for x, y in zip(a.children, b.children)))


def _reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def gate_unmodified(xml_path, workdir):
    print(f"[unmodified round-trip, save+reload] {os.path.basename(xml_path)}")
    orig_cap = wx.capture_asset(xml_path)

    _reset()
    openwrath_import.import_file(xml_path, report=lambda m: None)
    blend = os.path.join(workdir, "rt.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)

    # Genuine reload — the scene now comes ONLY from the .blend (anti-bypass).
    bpy.ops.wm.open_mainfile(filepath=blend)

    # The stash must be present on the reloaded datablock.
    mesh_dbs = [m for m in bpy.data.meshes if m.get(sb.STASH_KEY)]
    check(len(mesh_dbs) >= 1, "stash survived the .blend save/reload on the mesh datablock")

    out_xml = os.path.join(workdir, "rt_out.xml")
    summary = openwrath_import.export_file(out_xml, report=lambda m: None)
    check("[byte-exact]" in summary, f"unmodified export is byte-exact tier ({summary!r})")

    # The exported XML must re-capture to the IDENTICAL tree as the original decode.
    exp_cap = wx.capture_asset(out_xml)
    check(nodes_equal(orig_cap.node, exp_cap.node),
          "exported capture is IDENTICAL to the decoded capture (Blender preserved every attr)")


def gate_edited(xml_path, workdir):
    print(f"[edited -> stated tier] {os.path.basename(xml_path)}")
    _reset()
    openwrath_import.import_file(xml_path, report=lambda m: None)
    blend = os.path.join(workdir, "ed.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    bpy.ops.wm.open_mainfile(filepath=blend)

    obj = next((o for o in bpy.data.objects if o.type == "MESH" and o.data.get(sb.STASH_KEY)), None)
    if obj is None:
        check(False, "a stashed mesh object to edit")
        return
    before = tuple(obj.data.vertices[0].co)
    obj.data.vertices[0].co[0] = before[0] + 5.0  # move a vertex — a real edit
    obj.data.update()

    out_xml = os.path.join(workdir, "ed_out.xml")
    summary = openwrath_import.export_file(out_xml, obj=obj, report=lambda m: None)
    check("[stated]" in summary,
          f"edited mesh exports as STATED tier, NOT byte-exact ({summary!r})")

    geo = wx.parse_mesh(out_xml)  # must still be valid authoring XML
    moved = geo.positions[0][0]
    check(abs(moved - (before[0] + 5.0)) < 1e-3,
          "edited export reflects the moved vertex (reconstructed from live mesh)")


def _import_reload(xml_path, workdir, name, import_collision=False, resolver=None):
    _reset()
    openwrath_import.import_file(xml_path, import_collision=import_collision,
                                resolver=resolver, report=lambda m: None)
    blend = os.path.join(workdir, name + ".blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    bpy.ops.wm.open_mainfile(filepath=blend)
    return blend


def gate_graph_edit(workdir):
    """Each graph type: an unmodified reload stays byte-exact; a real edit flips to STATED and
    is NEVER reported byte-exact (the Milestone-2.1 honesty fix). Uses committed synthetic
    fixtures (zero EA)."""
    import bpy

    # --- W3DCollisionBox: move + resize the empty -------------------------------------------
    box_fix = os.path.join(FIXDIR, "ow_test_box.xml")
    if os.path.isfile(box_fix):
        print("[graph edit: W3DCollisionBox]")
        _import_reload(box_fix, workdir, "box_u")
        s = openwrath_import.export_file(os.path.join(workdir, "box_u.xml"),
                                         asset_type="W3DCollisionBox", report=lambda m: None)
        check("[byte-exact]" in s, f"unmodified collision box byte-exact ({s!r})")
        _import_reload(box_fix, workdir, "box_e")
        empty = next(o for o in bpy.data.objects if o.type == "EMPTY" and o.get(sb.STASH_KEY))
        empty.location[0] += 7.0
        empty.scale[1] *= 2.0
        se = openwrath_import.export_file(os.path.join(workdir, "box_e.xml"),
                                          asset_type="W3DCollisionBox", report=lambda m: None)
        check("[stated]" in se and "[byte-exact]" not in se,
              f"edited collision box -> STATED, not byte-exact ({se!r})")
        cb = wx.parse_collision_box(os.path.join(workdir, "box_e.xml"))
        check(abs(cb.center[0] - (0.5 + 7.0)) < 1e-3, "edited box center reflects the move")

    # --- W3DHierarchy: move a bone in edit mode ---------------------------------------------
    skel_fix = os.path.join(FIXDIR, "ow_test_skel.xml")
    if os.path.isfile(skel_fix):
        print("[graph edit: W3DHierarchy]")
        _import_reload(skel_fix, workdir, "skel_u")
        s = openwrath_import.export_file(os.path.join(workdir, "skel_u.xml"),
                                         asset_type="W3DHierarchy", report=lambda m: None)
        check("[byte-exact]" in s, f"unmodified hierarchy byte-exact ({s!r})")
        _import_reload(skel_fix, workdir, "skel_e")
        arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode="EDIT")
        eb = arm.data.edit_bones[1]       # the non-root bone
        eb.head = (eb.head[0] + 4.0, eb.head[1], eb.head[2])
        eb.tail = (eb.tail[0] + 4.0, eb.tail[1], eb.tail[2])
        bpy.ops.object.mode_set(mode="OBJECT")
        se = openwrath_import.export_file(os.path.join(workdir, "skel_e.xml"),
                                          asset_type="W3DHierarchy", report=lambda m: None)
        check("[stated]" in se and "[byte-exact]" not in se,
              f"edited skeleton -> STATED, not byte-exact ({se!r})")
        wx.parse_hierarchy(os.path.join(workdir, "skel_e.xml"))  # still valid authoring XML

    # --- W3DContainer: change collection membership -----------------------------------------
    model_fix = os.path.join(FIXDIR, "ow_test_model.xml")
    if os.path.isfile(model_fix):
        print("[graph edit: W3DContainer]")
        resolver = openwrath_import.AssetResolver(FIXDIR)
        _import_reload(model_fix, workdir, "model_u", import_collision=True, resolver=resolver)
        s = openwrath_import.export_file(os.path.join(workdir, "model_u.xml"),
                                         asset_type="W3DContainer", report=lambda m: None)
        check("[byte-exact]" in s, f"unmodified container byte-exact ({s!r})")
        _import_reload(model_fix, workdir, "model_e", import_collision=True, resolver=resolver)
        mesh_obj = next((o for o in bpy.data.objects if o.type == "MESH" and o.data.get(sb.STASH_KEY)), None)
        if mesh_obj is not None:
            coll = next(c for c in bpy.data.collections if c.get(sb.STASH_KEY))
            for c in list(mesh_obj.users_collection):
                c.objects.unlink(mesh_obj)   # remove a sub-object from the model
            se = openwrath_import.export_file(os.path.join(workdir, "model_e.xml"),
                                              asset_type="W3DContainer", report=lambda m: None)
            check("[stated]" in se and "[byte-exact]" not in se,
                  f"edited container -> STATED, not byte-exact ({se!r})")
            wx.parse_container(os.path.join(workdir, "model_e.xml"))  # still valid


def main():
    skip_ok = os.environ.get("OW_SKIP_IF_NO_FIXTURE") == "1"
    mesh_fix = os.environ.get("OW_MESH_FIXTURE", os.path.join(FIXDIR, "ow_test_cube.xml"))
    if not os.path.isfile(mesh_fix):
        msg = f"mesh fixture not found: {mesh_fix}"
        if skip_ok:
            print(f"SKIP: {msg}")
            return 0
        print(f"ERROR: {msg} (set OW_MESH_FIXTURE or OW_SKIP_IF_NO_FIXTURE=1)")
        return 2

    with tempfile.TemporaryDirectory() as wd:
        gate_unmodified(mesh_fix, wd)
        gate_edited(mesh_fix, wd)
        gate_graph_edit(wd)

    print()
    print(f"ran {_checks} checks")
    if _fail:
        print(f"EXPORT ROUND-TRIP GATE FAILED ({len(_fail)} failure(s))")
        return 1
    print("EXPORT ROUND-TRIP GATE PASSED — unmodified byte-exact tier; edits -> stated tier.")
    return 0


if __name__ == "__main__":
    rc = main()
    sys.stdout.flush()
    os._exit(rc)
