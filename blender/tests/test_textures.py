#!/usr/bin/env python3
"""Texture decidable-anchor tests — run OUTSIDE Blender (no bpy needed).

    python3 blender/tests/test_textures.py

Two byte-decidable sub-anchors for the textured-viewer milestone (finding 0027):

  1. **FXShader texture names parse deterministically** out of a mesh's ``<FXShader>``
     block (``w3x_xml.parse_mesh`` -> ``MeshGeometry.shader``). Asserted against the
     committed synthetic cube fixture; also run against the real local Redeemer mesh when
     present (gitignored) with the expected slot names from the milestone brief.

  2. **A Texture ``<Payload>`` base64-decodes to a VALID D3D9 DDS** (``dds.probe``). The
     payload is byte-exact (finding 0024), so this is a true/false check, not a judgement.
     Asserted on a committed synthetic DDS; the OnDemandTexture fixture must carry no
     payload; a corrupted header must FAIL. Real local ``Texture.*.xml`` payloads, when
     present, are validated and **bucketed + reported** (never silently dropped).

These guard the add-on's one format-shape surface independently of Blender; the in-GUI
material look is stated-tier and has no byte oracle (verification-blind-spots §4).
"""

import glob
import os
import sys

THIS = os.path.dirname(os.path.abspath(__file__))
ADDON_ROOT = os.path.dirname(THIS)       # blender/
FIX = os.path.join(THIS, "fixtures")
LOCAL = os.path.join(FIX, "local")       # gitignored; EA-derived decodes land here
sys.path.insert(0, ADDON_ROOT)

from openwrath_import import w3x_xml as wx  # noqa: E402
from openwrath_import import dds            # noqa: E402

_fail = []


def check(cond, msg):
    if not cond:
        _fail.append(msg)
        print(f"  FAIL: {msg}")
    else:
        print(f"  ok: {msg}")


# --------------------------------------------------------------------------- #
# Anchor 1 — FXShader texture names parse
# --------------------------------------------------------------------------- #

def test_shader_names_synthetic():
    print("[shader] FXShader names parse from ow_test_cube.xml")
    m = wx.parse_mesh(os.path.join(FIX, "ow_test_cube.xml"))
    check(m.shader is not None, "mesh carries a parsed <FXShader>")
    check(m.shader.shader_name == "ObjectsGDI.fx", "ShaderName attribute")
    check(m.shader.diffuse == "ow_test_texture", "DiffuseTexture name")
    check(m.shader.normal == "ow_test_texture_nrm", "NormalMap name")
    # An empty <Value> (unassigned slot) is dropped, not resolved as "".
    check(m.shader.spec is None, "empty SpecMap <Value> is dropped")
    check("EnvMult" not in m.shader.textures, "non-<Texture> constants ignored")


def _mesh_from_xml(xml: str, tmp="/tmp/_ow_tex_mesh.xml"):
    with open(tmp, "w") as fh:
        fh.write(xml)
    try:
        return wx.parse_mesh(tmp)
    finally:
        os.remove(tmp)


_NS = 'xmlns="uri:ea.com:eala:asset"'


def test_base_color_slot_precedence():
    # The ordered base-color precedence (DiffuseTexture > Texture_0); NEVER a per-shader
    # special-case. Effect shaders (MuzzleFlash.fx) carry the base map in Texture_0.
    print("[base-color] BASE_COLOR_SLOTS precedence")
    check(wx.BASE_COLOR_SLOTS == ("DiffuseTexture", "Texture_0"),
          "precedence constant is DiffuseTexture > Texture_0")

    # Object shader: DiffuseTexture.
    obj = _mesh_from_xml(
        f'<AssetDeclaration {_NS}><W3DMesh id="o"><Vertices><V X="0" Y="0" Z="0"/></Vertices>'
        '<FXShader ShaderName="ObjectsNOD.fx"><Constants>'
        '<Texture Name="DiffuseTexture"><Value>objmap</Value></Texture>'
        '</Constants></FXShader></W3DMesh></AssetDeclaration>')
    check(obj.shader.base_color() == ("DiffuseTexture", "objmap"), "object shader -> DiffuseTexture")

    # Effect shader: only Texture_0 (the review nit — FX_LAZERGLOW family).
    fx = _mesh_from_xml(
        f'<AssetDeclaration {_NS}><W3DMesh id="fx"><Vertices><V X="0" Y="0" Z="0"/></Vertices>'
        '<FXShader ShaderName="MuzzleFlash.fx"><Constants>'
        '<Float Name="Color"><Value>1</Value></Float>'
        '<Texture Name="Texture_0"><Value>fxmap</Value></Texture>'
        '</Constants></FXShader></W3DMesh></AssetDeclaration>')
    check(fx.shader.base_color() == ("Texture_0", "fxmap"), "effect shader -> Texture_0 fallback")

    # Both present -> DiffuseTexture wins (precedence, not insertion order).
    both = _mesh_from_xml(
        f'<AssetDeclaration {_NS}><W3DMesh id="b"><Vertices><V X="0" Y="0" Z="0"/></Vertices>'
        '<FXShader ShaderName="x.fx"><Constants>'
        '<Texture Name="Texture_0"><Value>t0</Value></Texture>'
        '<Texture Name="DiffuseTexture"><Value>diff</Value></Texture>'
        '</Constants></FXShader></W3DMesh></AssetDeclaration>')
    check(both.shader.base_color() == ("DiffuseTexture", "diff"), "DiffuseTexture precedence over Texture_0")

    # Non-colour slots are NEVER base colour.
    only_nrm = _mesh_from_xml(
        f'<AssetDeclaration {_NS}><W3DMesh id="n"><Vertices><V X="0" Y="0" Z="0"/></Vertices>'
        '<FXShader ShaderName="x.fx"><Constants>'
        '<Texture Name="NormalMap"><Value>nrm</Value></Texture>'
        '<Texture Name="SpecMap"><Value>spm</Value></Texture>'
        '</Constants></FXShader></W3DMesh></AssetDeclaration>')
    check(only_nrm.shader.base_color() == (None, None), "NormalMap/SpecMap never feed Base Color")

    # DefaultW3D.fx numeric-only: no base-color slot at all (correctly textureless).
    numeric = _mesh_from_xml(
        f'<AssetDeclaration {_NS}><W3DMesh id="d"><Vertices><V X="0" Y="0" Z="0"/></Vertices>'
        '<FXShader ShaderName="DefaultW3D.fx"><Constants>'
        '<Float Name="ColorDiffuse"><Value>0</Value></Float>'
        '</Constants></FXShader></W3DMesh></AssetDeclaration>')
    check(numeric.shader.base_color() == (None, None), "numeric-only shader has no base-color slot")


def test_material_status_buckets():
    # The honest bucket names from _base_color_material_for for the no-bpy early-return paths
    # (no resolver / sb needed for these — they return before touching Blender).
    print("[buckets] accurate status for no-FXShader vs textureless-FXShader")
    import openwrath_import as ow

    no_shader = _mesh_from_xml(
        f'<AssetDeclaration {_NS}><W3DMesh id="s"><Vertices><V X="0" Y="0" Z="0"/></Vertices>'
        '</W3DMesh></AssetDeclaration>')
    _m, st = ow._base_color_material_for(None, no_shader, None, "", report=lambda _m: None)
    check(st == "no_shader", "no <FXShader> -> 'no_shader'")

    numeric = _mesh_from_xml(
        f'<AssetDeclaration {_NS}><W3DMesh id="d"><Vertices><V X="0" Y="0" Z="0"/></Vertices>'
        '<FXShader ShaderName="DefaultW3D.fx"><Constants>'
        '<Float Name="ColorDiffuse"><Value>0</Value></Float>'
        '</Constants></FXShader></W3DMesh></AssetDeclaration>')
    _m2, st2 = ow._base_color_material_for(None, numeric, None, "", report=lambda _m: None)
    check(st2 == "no_basemap", "<FXShader> but no base-color slot -> 'no_basemap' (not 'no_shader')")


def test_fx_lazerglow_texture0_real():
    # The real effect sub-mesh the review flagged: FX_LAZERGLOW -> MuzzleFlash.fx -> Texture_0 ->
    # FXMuzzle, with a real committed-local DDS payload. Guarded on the local fixtures' presence.
    mp = os.path.join(LOCAL, "W3DMesh.NUREDEEMER_SKN.FX_LAZERGLOW.xml")
    tp = os.path.join(LOCAL, "Texture.FXMuzzle.xml")
    if not (os.path.isfile(mp) and os.path.isfile(tp)):
        print("[base-color] SKIP real FX_LAZERGLOW->FXMuzzle (local fixtures absent)")
        return
    print("[base-color] real FX_LAZERGLOW -> Texture_0 -> FXMuzzle (valid DDS)")
    m = wx.parse_mesh(mp)
    check(m.shader is not None and m.shader.diffuse is None, "FX mesh has no DiffuseTexture")
    check(m.shader.base_color() == ("Texture_0", "FXMuzzle"), "base_color resolves via Texture_0 -> FXMuzzle")
    t = wx.parse_texture(tp)
    check(not t.is_ondemand and t.payload_b64, "FXMuzzle is a Texture with a payload")
    _data, info = dds.decode_and_probe(t.payload_b64)
    check(info.valid, f"FXMuzzle payload is a valid DDS ({info.width}x{info.height} "
                      f"{info.fourcc or 'uncompressed'}; {info.reason or 'ok'})")


def test_shader_names_real_redeemer():
    # The real decoded mesh is EA-derived (gitignored). Only runs if the user has decoded
    # it locally (openwrath blender model NUREDEEMER_SKN); otherwise honestly skipped.
    p = os.path.join(LOCAL, "W3DMesh.NUREDEEMER_SKN.REDEEMER_TOP.xml")
    if not os.path.isfile(p):
        print("[shader] SKIP real Redeemer mesh (local fixture absent)")
        return
    print("[shader] FXShader names parse from the real REDEEMER_TOP")
    m = wx.parse_mesh(p)
    check(m.shader is not None and m.shader.diffuse == "NURedeemer", "DiffuseTexture=NURedeemer")
    check(m.shader.normal == "NURedeemer_NRM", "NormalMap=NURedeemer_NRM")
    check(m.shader.spec == "NURedeemer_SPM", "SpecMap=NURedeemer_SPM")
    check(m.shader.textures.get("ScrollingMaskTexture") == "ScrollTest",
          "ScrollingMaskTexture=ScrollTest")


# --------------------------------------------------------------------------- #
# Anchor 2 — Texture payload is a valid DDS
# --------------------------------------------------------------------------- #

def test_payload_valid_dds_synthetic():
    print("[dds] synthetic ow_test_texture.xml payload is a valid DDS")
    t = wx.parse_texture(os.path.join(FIX, "ow_test_texture.xml"))
    check(not t.is_ondemand, "parsed as Texture (not OnDemand)")
    check(t.payload_b64 is not None, "carries a <Payload>")
    data, info = dds.decode_and_probe(t.payload_b64)
    check(data is not None and data[0:4] == b"DDS ", "base64 decodes to DDS magic")
    check(info.valid, f"probe: valid DDS ({info.reason or 'ok'})")
    check(info.fourcc == "DXT5", "FourCC == DXT5")
    check((info.width, info.height) == (4, 4), "dims 4x4")


def test_ondemand_has_no_payload():
    print("[dds] OnDemandTexture fixture carries no payload")
    t = wx.parse_texture(os.path.join(FIX, "ow_test_ondemand.xml"))
    check(t.is_ondemand, "parsed as OnDemandTexture")
    check(t.payload_b64 is None, "no <Payload> (pixels streamed on demand)")


def test_corrupt_dds_rejected():
    print("[dds] a corrupted DDS header FAILS the probe")
    import base64
    # Valid magic + dwSize but implausible dimensions -> must be rejected (not widened away).
    bad = bytearray(128)
    bad[0:4] = b"DDS "
    import struct
    struct.pack_into("<I", bad, 4, 124)
    struct.pack_into("<I", bad, 12, 0)        # height 0 -> implausible
    struct.pack_into("<I", bad, 16, 999999)   # width huge
    struct.pack_into("<I", bad, 76, 32)
    ok, reason = dds.is_valid(bytes(bad))
    check(not ok, f"implausible dims rejected ({reason})")
    # Garbage magic.
    ok2, _ = dds.is_valid(b"NOTDDS!!" + b"\x00" * 200)
    check(not ok2, "bad magic rejected")
    # Not even base64.
    d, info = dds.decode_and_probe("!!!not base64!!!")
    check(d is None and not info.valid, "invalid base64 rejected")


def test_real_texture_payloads_bucketed():
    # Validate every real local Texture.*.xml payload; bucket + report, never hide a failure.
    tex_xmls = sorted(glob.glob(os.path.join(LOCAL, "Texture.*.xml")))
    od_xmls = sorted(glob.glob(os.path.join(LOCAL, "OnDemandTexture.*.xml")))
    if not tex_xmls and not od_xmls:
        print("[dds] SKIP real texture payloads (no local Texture.*/OnDemandTexture.* present)")
        return
    print(f"[dds] validating {len(tex_xmls)} real Texture + {len(od_xmls)} OnDemandTexture payload(s)")
    valid = invalid = 0
    for p in tex_xmls:
        t = wx.parse_texture(p)
        if not t.payload_b64:
            print(f"  BUCKET no-payload: {os.path.basename(p)}")
            invalid += 1
            continue
        _d, info = dds.decode_and_probe(t.payload_b64)
        if info.valid:
            valid += 1
        else:
            invalid += 1
            print(f"  BUCKET invalid-dds: {os.path.basename(p)} ({info.reason})")
    for p in od_xmls:
        t = wx.parse_texture(p)
        check(t.is_ondemand and not t.payload_b64,
              f"{os.path.basename(p)} is OnDemand with no payload (placeholder bucket)")
    print(f"  real Texture payloads: {valid} valid DDS, {invalid} bucketed")
    # Every shipped Texture record is byte-exact (0024) and carries a real DDS; any invalid
    # one is a genuine defect, so a real payload failing the probe fails the test.
    check(invalid == 0, "all real Texture payloads are valid DDS")


def main():
    test_shader_names_synthetic()
    test_base_color_slot_precedence()
    test_material_status_buckets()
    test_fx_lazerglow_texture0_real()
    test_shader_names_real_redeemer()
    test_payload_valid_dds_synthetic()
    test_ondemand_has_no_payload()
    test_corrupt_dds_rejected()
    test_real_texture_payloads_bucketed()
    print()
    if _fail:
        print(f"TEXTURE TESTS FAILED ({len(_fail)} failure(s))")
        return 1
    print("TEXTURE TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
