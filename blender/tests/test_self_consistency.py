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

    # Vertices not referenced by any triangle carry no corner (loop), so Blender
    # stores no per-corner UV or custom normal for them — their readback entries are
    # None. That is physically correct, not a diff to hide: we compare the loop-derived
    # channels (UVs, normals) only over REFERENCED vertices and report how many were
    # skipped (honest coverage, invariant 5). Positions / colours / influences are
    # per-vertex and cover every vertex, so they are compared in full.
    referenced = set()
    for t in mesh.triangles:
        referenced.update(t)
    n_unref = mesh.vertex_count - len(referenced)
    if n_unref:
        print(f"  note: {n_unref}/{mesh.vertex_count} vertices are unreferenced by any "
              f"triangle — their loop-derived UV/normal readback is skipped (no corner).")

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

    # UVs — bit-exact float32 (Y already un-flipped by the decoder), referenced verts only
    if mesh.uvs:
        uv_ok = rb["uvs"] is not None and len(rb["uvs"]) == len(mesh.uvs)
        if uv_ok:
            for v in referenced:
                a, b = rb["uvs"][v], mesh.uvs[v]
                if a is None or (f32(a[0]), f32(a[1])) != (f32(b[0]), f32(b[1])):
                    uv_ok = False
                    break
        check(uv_ok, "every UV bit-exact (float32), 1 channel [referenced verts]")
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

    # normals — STATED tier, NOT bit-exact. Blender cannot store a normal bit-exact.
    #
    # Blender keeps custom split normals per-CORNER as `short[2]` (CD_CUSTOMLOOPNORMAL):
    # two int16 values encoding the normal as angular offsets (alpha, beta) within the
    # corner's "lnor space", whose pole is the auto-computed smooth normal
    # (BKE_lnor_space_custom_normal_to_data -> unit_float_to_short, 32767 steps per
    # angular range). Like any lat/long parameterisation the resolution is finest at the
    # pole (~1e-4, i.e. float32 noise, when the custom normal ~ the auto normal) and
    # coarsest far from it. So the worst-case round-trip error is a property of the int16
    # ENCODING, not of our data or the triangle shape.
    #
    # DERIVED BOUND (not fit to one mesh): characterising the encode over 262144
    # directions uniformly on the sphere, the worst-case error SATURATES at ~1.35e-2
    # (both |Δcomponent| and Δangle, in radians) and is independent of triangle shape
    # (right / sliver / obtuse / equilateral all ~1.35e-2) — the signature of a fixed-
    # resolution quantiser. (Only sub-millimetre degenerate triangles break it badly;
    # real geometry does not contain those.) We set the tolerance to 2.0e-2 — ~40%
    # headroom over the measured ceiling. Across 40 shipped KW meshes (4..2224
    # referenced verts, skinned + static) the worst observed is 3.78e-3, well inside it.
    # The importer feeds the EXACT decoded normals in (normals_split_custom_set_from_
    # vertices); this tolerance covers only Blender's storage encode. A real mesh that
    # EXCEEDS this bound would be a genuine importer issue, not a reason to widen it.
    NORMAL_TOL = 2.0e-2  # Blender int16 custom-normal storage ceiling (~1.35e-2) + headroom
    if mesh.normals:
        if rb["normals"] is None:
            check(False, "custom normals read back (API available)")
        else:
            n_ok = len(rb["normals"]) == len(mesh.normals)
            maxerr = 0.0
            for v in referenced:
                a, b = rb["normals"][v], mesh.normals[v]
                if a is None:          # referenced vert must have a corner normal
                    n_ok = False
                    continue
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
        # each mesh is bound to the armature (modifier for skinned, object-parent for rigid)
        bound = all(
            o.parent is not None and o.parent.type == "ARMATURE"
            for o in mesh_objs
        )
        check(bound, "every mesh bound to the armature")

        # PLACEMENT / ASSEMBLY (decidable) — the check that would have caught the
        # dis-assembled Redeemer (rigid parts scattered to bone tails; skinned legs/body
        # collapsed to the origin). Every sub-object's geometry is baked into MODEL space
        # by the importer; here we INDEPENDENTLY recompute each mesh's expected model-
        # space centroid from its raw decoded vertices + the bind pose, and assert the
        # built mesh's actual world centroid matches. A forgotten/incorrect bake (rigid
        # OR skinned) leaves the centroid at the raw/collapsed position and FAILS.
        # (Separate implementation from scene_builder — this verifies the build, it did
        # not write it.) Reuse the ONE world-matrix accumulator, never a re-derivation.
        base_dir = os.path.dirname(os.path.abspath(xml_path))
        resolver = openwrath_import.AssetResolver(base_dir)
        try:
            hpath = resolver.resolve(cont.hierarchy, type_hint="W3DHierarchy")
            hier = wx.parse_hierarchy(hpath)
            worlds = sb._pivot_world_matrices(hier)
        except Exception as e:
            check(False, f"hierarchy resolved for placement check ({e})")
            worlds = None

        def ref_bone(mesh, vi, default):
            # channel-0 (first influence slot) for skinned, else the sub-object's bone —
            # computed here independently of scene_builder to verify, not mirror, the build.
            infl = mesh.influences[vi]
            return infl[0][0] if infl else default

        def model_pos(mesh, vi, bone_index):
            from mathutils import Vector
            b = ref_bone(mesh, vi, bone_index) if any(mesh.influences) else bone_index
            p = Vector(mesh.positions[vi])
            return (worlds[b] @ p) if 0 <= b < len(worlds) else p

        def expected_centroid(mesh, bone_index):
            from mathutils import Vector
            acc = Vector((0.0, 0.0, 0.0))
            n = mesh.vertex_count or 1
            for vi in range(mesh.vertex_count):
                acc += model_pos(mesh, vi, bone_index)
            return acc / n

        def actual_centroid(obj):
            from mathutils import Vector
            vs = obj.data.vertices
            if not vs:
                return Vector((0.0, 0.0, 0.0))
            acc = Vector((0.0, 0.0, 0.0))
            for v in vs:
                acc += obj.matrix_world @ v.co
            return acc / len(vs)

        if worlds is not None:
            placement_ok = True
            n_checked = 0
            worst = 0.0
            worst_name = None
            for sub in cont.sub_objects:
                if sub.render_kind != "Mesh" or not sub.render_name:
                    continue
                obj = bpy.data.objects.get(sub.render_name)
                if obj is None:
                    continue
                try:
                    mesh = wx.parse_mesh(resolver.resolve(sub.render_name, type_hint="W3DMesh"))
                except Exception:
                    continue
                n_checked += 1
                d = (expected_centroid(mesh, sub.bone_index) - actual_centroid(obj)).length
                if d > worst:
                    worst, worst_name = d, sub.render_name
                if d > 1e-3:
                    placement_ok = False
            check(placement_ok,
                  f"{n_checked} sub-object(s) assembled at their bind-pose centroid "
                  f"(worst {worst:.2e} on {worst_name})")

            # SEAM CONTINUITY (decidable) — the check that would have caught the Redeemer
            # foot tears a centroid check could not. A skinned vertex is placed by its
            # CHANNEL-0 (reference) bone; if a DIFFERENT one of its influencing bones would
            # put it much closer to its mesh-neighbours, the reference choice is wrong and
            # the seam tears (the max-weight rule flung leg-1 toe / buggy-tyre verts 11–15u
            # off their neighbours). We flag a vertex only when another influencing bone is
            # both substantially and absolutely better — so a genuinely pointy prong (no bone
            # helps) is NOT flagged, but a wrong-bone tear IS. Honest: worst gap reported.
            from mathutils import Vector as _V
            SEAM_ABS = 2.0      # ignore sub-2u offsets (fine detail / quantisation)
            SEAM_FACTOR = 3.0   # another bone must be >=3x closer to count a vertex as off-seam
            SEAM_FAIL = 5.0     # improvable gap above this = a GROSS wrong-bone tear -> FAIL.
            # Below it = a small residual (a genuine soft-blend vertex the rigid channel-0
            # bind can't place perfectly); bucketed + reported, not failed — skinned is
            # STATED-tier (static bind pose, no live deform). Do NOT widen SEAM_FAIL to hide
            # a gross tear; raising SEAM_ABS/FACTOR to silence a real tear is the same sin.
            n_skin = 0
            worst_seam = 0.0
            worst_seam_name = None
            n_residual = 0
            for sub in cont.sub_objects:
                if sub.render_kind != "Mesh" or not sub.render_name:
                    continue
                obj = bpy.data.objects.get(sub.render_name)
                if obj is None:
                    continue
                try:
                    mesh = wx.parse_mesh(resolver.resolve(sub.render_name, type_hint="W3DMesh"))
                except Exception:
                    continue
                if not any(mesh.influences):
                    continue
                n_skin += 1
                nbr = [set() for _ in range(mesh.vertex_count)]
                for t in mesh.triangles:
                    for a in t:
                        for b in t:
                            if a != b:
                                nbr[a].add(b)
                built = [obj.matrix_world @ v.co for v in obj.data.vertices]
                for vi in range(min(mesh.vertex_count, len(built))):
                    if not nbr[vi]:
                        continue
                    cen = _V((0.0, 0.0, 0.0))
                    for j in nbr[vi]:
                        if j < len(built):
                            cen += built[j]
                    cen /= len(nbr[vi])
                    chosen = (built[vi] - cen).length
                    if chosen <= SEAM_ABS:
                        continue
                    p = _V(mesh.positions[vi])
                    best_alt = chosen
                    for b, _w in mesh.influences[vi]:
                        if 0 <= b < len(worlds):
                            best_alt = min(best_alt, ((worlds[b] @ p) - cen).length)
                    if chosen > SEAM_FACTOR * best_alt:   # a different bone is far better → off-seam
                        gap = chosen - best_alt
                        if gap > worst_seam:
                            worst_seam, worst_seam_name = gap, sub.render_name
                        if gap <= SEAM_FAIL:
                            n_residual += 1
            if n_residual:
                print(f"   bucket (STATED): {n_residual} skinned vertex(es) with a small "
                      f"(<= {SEAM_FAIL:.0f}u) bind-pose seam residual — soft-blend verts the "
                      f"rigid bind can't place exactly; worst {worst_seam:.2f}u.")
            check(worst_seam <= SEAM_FAIL,
                  f"{n_skin} skinned mesh(es): no GROSS bone-seam tear "
                  f"(worst improvable gap {worst_seam:.2f} <= {SEAM_FAIL:.0f}u"
                  + (f", on {worst_seam_name}" if worst_seam > SEAM_ABS else "") + ")")


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
