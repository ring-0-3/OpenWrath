#!/usr/bin/env python3
"""Pure-Python parser tests — run OUTSIDE Blender (no bpy needed).

    python3 blender/tests/test_parser.py

Validates that :mod:`openwrath_import.w3x_xml` parses the committed synthetic
fixtures into the expected structure. This guards the add-on's one source of
format knowledge independently of Blender. The Blender-side faithful-reconstruction
gate is ``test_self_consistency.py``.
"""

import os
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
ADDON_ROOT = os.path.dirname(THIS)       # blender/
FIX = os.path.join(THIS, "fixtures")
sys.path.insert(0, ADDON_ROOT)

from openwrath_import import w3x_xml as wx  # noqa: E402

_fail = []


def check(cond, msg):
    if not cond:
        _fail.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok: {msg}")


def test_mesh():
    print("[mesh] ow_test_cube.xml")
    m = wx.parse_mesh(os.path.join(FIX, "ow_test_cube.xml"))
    check(m.name == "ow_test_cube", "name")
    check(m.vertex_count == 8, "vertex count == 8")
    check(len(m.positions) == 8, "8 positions")
    check(m.positions[1] == (1.0, -1.0, -1.0), "position[1] value")
    check(len(m.normals) == 8, "8 normals")
    check(len(m.uvs) == 8, "8 uvs")
    check(m.colors is not None and len(m.colors) == 8, "8 vertex colours (non-white present)")
    check(len(m.triangles) == 12, "12 triangles")
    check(m.triangles[0] == (0, 1, 2), "triangle[0] indices")
    check(len(m.influences[0]) == 2, "vertex 0 has 2 influence channels")
    check(m.nonzero_influences(0) == {0: 0.75, 1: 0.25}, "vertex 0 nonzero influences")


def test_hierarchy():
    print("[hierarchy] ow_test_skel.xml")
    h = wx.parse_hierarchy(os.path.join(FIX, "ow_test_skel.xml"))
    check(h.name == "ow_test_skel", "name")
    check(len(h.pivots) == 2, "2 pivots")
    check(h.pivots[0].parent == -1, "root parent == -1")
    check(h.pivots[1].parent == 0, "child parent == 0")
    check(h.pivots[1].translation == (0.0, 2.0, 0.0), "child translation")
    check(h.pivots[1].rotation == (0.0, 0.0, 0.0, 1.0), "child rotation (identity XYZW)")


def test_container():
    print("[container] ow_test_model.xml")
    c = wx.parse_container(os.path.join(FIX, "ow_test_model.xml"))
    check(c.name == "ow_test_model", "name")
    check(c.hierarchy == "ow_test_skel", "hierarchy ref")
    check(len(c.sub_objects) == 2, "2 sub-objects")
    s0, s1 = c.sub_objects
    check(s0.render_kind == "Mesh" and s0.render_name == "ow_test_cube", "subobj0 mesh ref")
    check(s0.bone_index == 0, "subobj0 bone index")
    check(s1.render_kind == "CollisionBox" and s1.render_name == "ow_test_box", "subobj1 collision ref")


def test_passthrough_rejected(tmpname="/tmp/_ow_passthrough.xml"):
    print("[guard] rejects packed-passthrough mesh (no --semantic-mesh)")
    with open(tmpname, "w") as fh:
        fh.write('<AssetDeclaration xmlns="uri:ea.com:eala:asset">'
                 '<W3DMesh id="x"><VertexData NumVertices="0" VertexStride="0"/>'
                 '</W3DMesh></AssetDeclaration>')
    try:
        wx.parse_mesh(tmpname)
        check(False, "should have raised on packed <VertexData>")
    except ValueError as e:
        check("--semantic-mesh" in str(e), "error names --semantic-mesh")
    finally:
        os.remove(tmpname)


def test_schemaless_triangles(tmpname="/tmp/_ow_schemaless_tris.xml"):
    # Without --schema, the generic walker emits a Triangle's V list as a space-list
    # attribute (V="a b c") instead of <V>n</V> children. The parser must accept both.
    print("[robustness] schemaless triangle attribute form V=\"a b c\"")
    with open(tmpname, "w") as fh:
        fh.write(
            '<AssetDeclaration xmlns="uri:ea.com:eala:asset"><W3DMesh id="x">'
            '<Vertices><V X="0" Y="0" Z="0"/><V X="1" Y="0" Z="0"/><V X="0" Y="1" Z="0"/></Vertices>'
            '<Triangles><T V="0 1 2"/></Triangles>'
            '</W3DMesh></AssetDeclaration>'
        )
    try:
        m = wx.parse_mesh(tmpname)
        check(m.triangles == [(0, 1, 2)], "schemaless triangle parsed from attribute")
    finally:
        os.remove(tmpname)


def main():
    test_mesh()
    test_hierarchy()
    test_container()
    test_passthrough_rejected()
    test_schemaless_triangles()
    print()
    if _fail:
        print(f"PARSER TESTS FAILED ({len(_fail)} failure(s))")
        return 1
    print("PARSER TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
