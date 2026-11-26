#!/usr/bin/env python3
"""Exporter unit tests (system python, no Blender) — the capture / writer half of
milestone 2. Fast, dependency-free decidable anchors for the exporter's XML layer:

  * the verbatim capture round-trips through JSON losslessly (the stash form),
  * serialize_capture produces XML that re-captures IDENTICALLY (so an unmodified export is
    byte-stable before it ever reaches the compiler),
  * mesh_geometry_from_capture agrees with parse_mesh (the one reader feeds the coupling),
  * rewrite_mesh_geometry replaces geometry and drops the derived structures (edited path).

The *byte-exact-vs-shipped* proof is the gate (tools/blender-roundtrip-gate.sh); these tests
guard the pure-Python pieces it stands on. A real locally-decompiled mesh (with AABTree /
skin) is used when present via OW_MESH_FIXTURE, else the committed synthetic cube.
"""
import os
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(THIS))  # blender/
FIX = os.path.join(THIS, "fixtures")

from openwrath_import import w3x_xml as wx  # noqa: E402

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


def nodes_equal(a: wx.Node, b: wx.Node) -> bool:
    return (a.tag == b.tag and a.attrib == b.attrib and a.text == b.text
            and len(a.children) == len(b.children)
            and all(nodes_equal(x, y) for x, y in zip(a.children, b.children)))


def test_capture_json_roundtrip(path):
    print(f"[capture<->json] {os.path.basename(path)}")
    cap = wx.capture_asset(path)
    cap2 = wx.capture_from_json(wx.capture_to_json(cap))
    check(cap.asset_type == cap2.asset_type and cap.asset_id == cap2.asset_id,
          "asset type+id survive JSON")
    check(nodes_equal(cap.node, cap2.node), "node tree identical after JSON round-trip (verbatim)")


def test_serialize_recapture(path):
    print(f"[serialize->recapture] {os.path.basename(path)}")
    cap = wx.capture_asset(path)
    xml = wx.serialize_capture(cap)
    # Re-capture the serialised XML from a string (write to a temp-less ET parse).
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml)
    asset_el = list(root)[0]
    recap_node = wx._node_from_et(asset_el)
    check(nodes_equal(cap.node, recap_node),
          "serialize_capture re-captures to an IDENTICAL tree (byte-stable authoring XML)")


def test_geometry_from_capture_matches_parse(path):
    if wx.asset_type(path) != "W3DMesh":
        return
    print(f"[geometry_from_capture == parse_mesh] {os.path.basename(path)}")
    geo_direct = wx.parse_mesh(path)
    geo_cap = wx.mesh_geometry_from_capture(wx.capture_asset(path))
    check(geo_direct.vertex_count == geo_cap.vertex_count, "vertex count matches")
    check(geo_direct.positions == geo_cap.positions, "positions match")
    check(geo_direct.triangles == geo_cap.triangles, "triangles match")
    check(geo_direct.influences == geo_cap.influences, "influences match")


def test_rewrite_drops_derived(path):
    if wx.asset_type(path) != "W3DMesh":
        return
    print(f"[rewrite_mesh_geometry] {os.path.basename(path)}")
    cap = wx.capture_asset(path)
    geo = wx.mesh_geometry_from_capture(cap)
    edited = wx.rewrite_mesh_geometry(cap, geo)
    tags = [c.tag for c in edited.node.children]
    # Derived structures must be gone; non-geometry metadata must be kept.
    check("AABTree" not in tags, "edited capture drops AABTree (derived)")
    check("Tangents" not in tags and "Binormals" not in tags,
          "edited capture drops Tangents/Binormals (derived)")
    check("Vertices" in tags and "Triangles" in tags, "edited capture keeps rebuilt geometry")
    orig_tags = {c.tag for c in cap.node.children}
    for keep in ("BoundingBox", "BoundingSphere", "FXShader"):
        if keep in orig_tags:
            check(keep in tags, f"edited capture carries through {keep}")
    # And the rebuilt geometry still round-trips to the same MeshGeometry.
    geo2 = wx.mesh_geometry_from_capture(edited)
    check(geo2.positions == geo.positions, "rebuilt geometry positions preserved")
    check(geo2.triangles == geo.triangles, "rebuilt geometry triangles preserved")


def main():
    mesh_fix = os.environ.get("OW_MESH_FIXTURE", os.path.join(FIX, "ow_test_cube.xml"))
    graph_fixes = []
    # Opportunistically exercise real graph captures if a local decode is present.
    loc = os.path.join(FIX, "local")
    for name in ("W3DHierarchy.NU_BUGGY_SKL.xml", "W3DContainer.NU_BUGGY_SKN.xml",
                 "W3DCollisionBox.NU_BUGGY_SKN.OBBOX.xml"):
        p = os.path.join(loc, name)
        if os.path.isfile(p):
            graph_fixes.append(p)

    for p in [mesh_fix] + graph_fixes:
        if not os.path.isfile(p):
            print(f"note: fixture absent, skipping: {p}")
            continue
        test_capture_json_roundtrip(p)
        test_serialize_recapture(p)
        test_geometry_from_capture_matches_parse(p)
        test_rewrite_drops_derived(p)

    print()
    print(f"ran {_checks} checks")
    if _fail:
        print(f"EXPORT TESTS FAILED ({len(_fail)} failure(s))")
        return 1
    print("EXPORT TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
