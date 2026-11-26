#!/usr/bin/env python3
"""The DECIDABLE self-consistency gate — run INSIDE Blender:

    blender --background --python blender/tests/test_self_consistency.py

What it proves (verification-blind-spots §4, "decidable"): the importer
reconstructs the CLI's decompiled XML *faithfully* — it parses a mesh XML, builds
the Blender mesh, reads the Blender datablock back, and asserts it equals the XML
values bit-for-bit where a bit-exact comparison is meaningful (vertex count, every
position, UVs, vertex colours, per-vertex bone index+weight) and within a tight
tolerance for normals (Blender normalises custom normals — documented, STATED).

Green ⇒ the import is a faithful reconstruction of what OpenWrath DECODED. It does
NOT prove fidelity to the game's render (that is the manual, stated-tier visual
acceptance step in README.md — it needs the GUI + your own model).

Fixtures: by default the committed synthetic cube (zero EA content). Point it at
your own locally-decompiled mesh with:
    OW_MESH_FIXTURE=/path/to/yourmesh.xml blender -b --python this.py
A container fixture (structural check) can likewise be set via OW_CONTAINER_FIXTURE.
Set OW_SKIP_IF_NO_FIXTURE=1 to skip (exit 0) instead of failing when absent.
"""

import os
import struct
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
ADDON_ROOT = os.path.dirname(THIS)        # blender/
FIXDIR = os.path.join(THIS, "fixtures")
sys.path.insert(0, ADDON_ROOT)

import bpy  # noqa: E402

import openwrath_import  # noqa: E402  (ensures the package is importable as installed)
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


def f32(x):
    """Pack a value as little-endian float32 for bit-exact comparison.

    XML attribute strings are the shortest round-trip of a float32 read from the
    shipped buffer; Blender stores float32 too. So float(str) rounded to float32
    equals Blender's stored value exactly — comparing the float32 bit patterns is
    a true exact-match, immune to float64 printing noise.
    """
    return struct.pack("<f", float(x))


def vec_f32(v):
    return tuple(f32(c) for c in v)


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


# --------------------------------------------------------------------------- #
# Core gate: mesh XML  ==  built Blender mesh
# --------------------------------------------------------------------------- #

def gate_mesh(xml_path):
    print(f"[mesh gate] {xml_path}")
    reset_scene()
    mesh = wx.parse_mesh(xml_path)
    obj = sb.build_mesh(mesh)
    rb = sb.readback_mesh(obj)

    # vertex count
    check(rb["vertex_count"] == mesh.vertex_count,
          f"vertex count ({rb['vertex_count']} == {mesh.vertex_count})")

    # positions — bit-exact float32
    pos_ok = len(rb["positions"]) == len(mesh.positions)
    for a, b in zip(rb["positions"], mesh.positions):
        if vec_f32(a) != vec_f32(b):
            pos_ok = False
            break
    check(pos_ok, "every position bit-exact (float32)")

    # UVs — bit-exact float32 (Y already un-flipped by the decoder)
    if mesh.uvs:
        uv_ok = rb["uvs"] is not None and len(rb["uvs"]) == len(mesh.uvs)
        if uv_ok:
            for a, b in zip(rb["uvs"], mesh.uvs):
                if (f32(a[0]), f32(a[1])) != (f32(b[0]), f32(b[1])):
                    uv_ok = False
                    break
        check(uv_ok, "every UV bit-exact (float32), 1 channel")
    else:
        check(rb["uvs"] is None, "no UVs expected")

    # vertex colours — bit-exact float32 RGBA
    if mesh.colors:
        col_ok = rb["colors"] is not None and len(rb["colors"]) == len(mesh.colors)
        if col_ok:
            for a, b in zip(rb["colors"], mesh.colors):
                if vec_f32(a[:4]) != vec_f32(b[:4]):
                    col_ok = False
                    break
        check(col_ok, "every vertex colour bit-exact (float32 RGBA)")
    else:
        check(rb["colors"] is None, "no vertex colours expected (all-white omitted)")

    # per-vertex bone index + weight — bit-exact weights, exact bone-ID set.
    # We recover the bone ID back OUT of Blender's vertex-group name ("bone_<id>",
    # produced by the standalone build) and compare it to the XML's raw Bone="<id>".
    # That compares ground-truth XML ids against what round-tripped through Blender —
    # not importer-naming against importer-naming.
    if any(mesh.influences):
        inf_ok = True
        for v in range(mesh.vertex_count):
            expected = mesh.nonzero_influences(v)                     # {bone_id: weight} from XML
            got = {}
            for name, w in rb["influences"][v].items():
                if name.startswith("bone_"):
                    got[int(name.split("_", 1)[1])] = w
                else:
                    got[name] = w                                     # (named rig; keep as-is)
            if set(got.keys()) != set(expected.keys()):
                inf_ok = False
                break
            for k in expected:
                if f32(got[k]) != f32(expected[k]):
                    inf_ok = False
                    break
            if not inf_ok:
                break
        check(inf_ok, "every vertex bone id+weight exact (id recovered from Blender groups)")
    else:
        check(not any(rb["influences"]), "no bone influences expected")

    # triangles — exact index sets (triangulation preserves our already-tri faces)
    tri_ok = len(rb["triangles"]) == len(mesh.triangles)
    if tri_ok:
        got = sorted(tuple(sorted(t)) for t in rb["triangles"])
        exp = sorted(tuple(sorted(t)) for t in mesh.triangles)
        tri_ok = got == exp
    check(tri_ok, f"triangle count+indices exact ({len(rb['triangles'])} tris)")

    # normals — STATED tier, NOT bit-exact. Blender cannot store normals bit-exact:
    # custom split normals are kept as int16-encoded directions (CustomLoopNormal),
    # so a shipped float32 normal round-trips only to ~1e-4. This is Blender's storage
    # quantisation, not an importer defect — so we bucket it honestly (invariant 5)
    # rather than claim exactness. The importer feeds the exact decoded normals in;
    # the tolerance covers only Blender's encode.
    NORMAL_TOL = 2e-4  # int16 custom-normal quantisation headroom
    if mesh.normals:
        if rb["normals"] is None:
            check(False, "custom normals read back (API available)")
        else:
            n_ok = len(rb["normals"]) == len(mesh.normals)
            maxerr = 0.0
            for a, b in zip(rb["normals"], mesh.normals):
                for ca, cb in zip(a, b):
                    maxerr = max(maxerr, abs(ca - cb))
            n_ok = n_ok and maxerr < NORMAL_TOL
            check(n_ok, f"normals faithful within Blender's int16 storage "
                        f"(max err {maxerr:.2e} < {NORMAL_TOL:.0e}) [STATED, not bit-exact]")


# --------------------------------------------------------------------------- #
# Structural check (stated tier): full container import builds the scene graph
# --------------------------------------------------------------------------- #

def check_container(xml_path):
    print(f"[container structure] {xml_path}")
    reset_scene()
    cont = wx.parse_container(xml_path)
    summary = openwrath_import.import_file(xml_path, import_collision=True,
                                           report=lambda m: print("   ", m))
    print("   ", summary)

    n_mesh = sum(1 for s in cont.sub_objects if s.render_kind == "Mesh" and s.render_name)
    mesh_objs = [o for o in bpy.data.objects if o.type == "MESH"]
    arm_objs = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    check(len(mesh_objs) == n_mesh, f"{n_mesh} mesh object(s) built")
    if cont.hierarchy:
        check(len(arm_objs) == 1, "armature built from hierarchy")
        # each mesh is bound to the armature (modifier or bone-parent)
        bound = all(
            (any(m.type == "ARMATURE" for m in o.modifiers) or o.parent_type == "BONE")
            and o.parent is not None and o.parent.type == "ARMATURE"
            for o in mesh_objs
        )
        check(bound, "every mesh bound to the armature")


# --------------------------------------------------------------------------- #

def main():
    skip_ok = os.environ.get("OW_SKIP_IF_NO_FIXTURE") == "1"

    mesh_fix = os.environ.get("OW_MESH_FIXTURE", os.path.join(FIXDIR, "ow_test_cube.xml"))
    cont_fix = os.environ.get("OW_CONTAINER_FIXTURE", os.path.join(FIXDIR, "ow_test_model.xml"))

    if not os.path.isfile(mesh_fix):
        msg = f"mesh fixture not found: {mesh_fix}"
        if skip_ok:
            print(f"SKIP: {msg}")
            return 0
        print(f"ERROR: {msg} (set OW_MESH_FIXTURE or OW_SKIP_IF_NO_FIXTURE=1)")
        return 2

    gate_mesh(mesh_fix)

    if os.path.isfile(cont_fix):
        check_container(cont_fix)
    else:
        print(f"note: container fixture absent ({cont_fix}) — skipping structural check")

    print()
    print(f"ran {_checks} checks")
    if _fail:
        print(f"SELF-CONSISTENCY GATE FAILED ({len(_fail)} failure(s))")
        return 1
    print("SELF-CONSISTENCY GATE PASSED — import faithfully reconstructs the decode.")
    return 0


if __name__ == "__main__":
    # Blender ignores a plain sys.exit code; signal via os._exit so CI sees it.
    rc = main()
    sys.stdout.flush()
    os._exit(rc)
