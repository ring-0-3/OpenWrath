"""OpenWrath W3X authoring-XML parser — the add-on's ONE source of format knowledge.

This module translates the XML that ``bab-decompile`` emits into plain Python
dataclasses. It is deliberately the *only* place in the add-on that knows the
shape of a decompiled asset. It contains **no byte/format logic whatsoever** — all
packing/unpacking lives in the OpenWrath CLI (CLAUDE.md invariant 3 / the §3
duplication trap that ``docs/design/blender-integration.md`` exists to prevent).

It is pure-stdlib (``xml.etree``) so it can be unit-tested outside Blender.

Shapes handled (confirmed against the producers, do-not-guess):
  * ``W3DMesh`` semantic geometry  — ``StructReader.ReadSemanticVertexData``
    (``source/BinaryAssetBuilder.Decompiler/StructReader.cs`` ~L738-950) and the
    ``<Triangles>`` list (``schemas/kw/xsd/AssetTypeW3D.xsd`` L339-342).
  * ``W3DHierarchy`` pivots         — ``Marshaler.W3D.cs`` L504-525.
  * ``W3DContainer`` (HLod)         — ``Marshaler.W3D.cs`` L453-478.

Every asset document is::

    <AssetDeclaration xmlns="uri:ea.com:eala:asset">
      <W3DMesh id="..."> ... </W3DMesh>      (or W3DHierarchy / W3DContainer)
    </AssetDeclaration>
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

ASSET_NS = "uri:ea.com:eala:asset"


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #

Vec3 = tuple[float, float, float]


# Ordered base-color texture slots, highest precedence first. ONLY these feed Base Color:
# standard object shaders name their albedo `DiffuseTexture`; the effect/muzzle shaders
# (MuzzleFlash.fx family) carry their base map in `Texture_0` instead. NormalMap / SpecMap /
# ScrollingMaskTexture / Bump* are NOT colour maps and must never land on Base Color — they
# are deliberately absent from this list. Extending the viewer to a new base-color slot is a
# one-line addition here, keeping the precedence auditable in a single named place.
BASE_COLOR_SLOTS = ("DiffuseTexture", "Texture_0")


@dataclass
class ShaderTextures:
    """The texture-slot references out of a mesh's ``<FXShader>`` block.

    ``textures`` maps the slot name exactly as authored (``"DiffuseTexture"``,
    ``"Texture_0"``, ``"NormalMap"``, ``"SpecMap"``, ``"ScrollingMaskTexture"``, …) to the
    referenced ``Texture`` / ``OnDemandTexture`` **asset name** — NOT a file. Resolving that
    name to an actual asset (and its DDS payload) is the CLI's job; this is pure XML shape.
    """

    shader_name: str = ""
    textures: dict[str, str] = field(default_factory=dict)

    def base_color(self) -> tuple[Optional[str], Optional[str]]:
        """``(slot_name, texture_asset_name)`` for the first base-color slot this shader
        actually has, by :data:`BASE_COLOR_SLOTS` precedence; ``(None, None)`` if none.

        ``(None, None)`` is the legitimate textureless case (a shader whose constants expose
        no base-color map) — the caller keeps the placeholder for it. Note the base-color slot
        is decided by the constants present, NOT by shader name: a ``DefaultW3D.fx`` mesh may
        still carry a ``Texture_0`` base map (and is textured), so never gate on the ``.fx``."""
        for slot in BASE_COLOR_SLOTS:
            name = self.textures.get(slot)
            if name:
                return slot, name
        return None, None

    @property
    def diffuse(self) -> Optional[str]:
        """The ``DiffuseTexture`` slot specifically (standard object shaders). For picking
        the material's base colour across shader families, prefer :meth:`base_color`."""
        return self.textures.get("DiffuseTexture")

    @property
    def normal(self) -> Optional[str]:
        return self.textures.get("NormalMap")

    @property
    def spec(self) -> Optional[str]:
        return self.textures.get("SpecMap")


@dataclass
class TextureAsset:
    """A decompiled ``Texture`` / ``OnDemandTexture`` asset (finding 0024).

    A shipped ``Texture`` carries a ``<Payload>`` base64 element that is a *literal
    complete D3D9 .dds file* (``StructReader.ReadTexturePayload``); decoding it back to
    bytes is just a base64 decode — no DXT work lives here (CLAUDE.md invariant 3). An
    ``OnDemandTexture`` carries **no** payload (its pixels are streamed on demand / live
    as a loose file), so ``payload_b64`` is ``None`` and ``is_ondemand`` is ``True``.
    """

    name: str
    is_ondemand: bool
    payload_b64: Optional[str] = None


@dataclass
class MeshGeometry:
    """One shipped ``W3DMesh``, decoded to editable per-vertex attributes.

    Channel 0 is the one a viewer uses; extra channels (a 2nd position set,
    a 2nd UV set) are preserved verbatim so an exporter can round-trip them.
    ``vertex_count`` is authoritative — every channel has exactly that many
    entries, aligned by index.
    """

    name: str
    vertex_count: int
    # One list per channel. positions[0] is the primary geometry.
    position_channels: list[list[Vec3]] = field(default_factory=list)
    normal_channels: list[list[Vec3]] = field(default_factory=list)
    tangents: Optional[list[Vec3]] = None
    binormals: Optional[list[Vec3]] = None
    uv_channels: list[list[tuple[float, float]]] = field(default_factory=list)
    # Per-vertex RGBA floats 0..1; None when the mesh is all-white (omitted by design).
    colors: Optional[list[tuple[float, float, float, float]]] = None
    # influences[v] -> list of (bone_id, weight) across all BoneInfluences channels.
    # Weight==0 entries are the inert "ghost" channel (remap-table reproduction only).
    influences: list[list[tuple[int, float]]] = field(default_factory=list)
    # Triangle faces as (v0, v1, v2) indices into the primary position channel.
    triangles: list[tuple[int, int, int]] = field(default_factory=list)
    # The FXShader texture-slot references, or None when the mesh carries no <FXShader>.
    shader: Optional[ShaderTextures] = None

    @property
    def positions(self) -> list[Vec3]:
        return self.position_channels[0] if self.position_channels else []

    @property
    def normals(self) -> Optional[list[Vec3]]:
        return self.normal_channels[0] if self.normal_channels else None

    @property
    def uvs(self) -> Optional[list[tuple[float, float]]]:
        return self.uv_channels[0] if self.uv_channels else None

    def nonzero_influences(self, v: int) -> dict[int, float]:
        """Per-vertex {bone_id: weight} for weight>0 influences (ghost dropped).

        Weights for a repeated bone within one vertex are summed (standard
        skinning); in shipped meshes each channel references a distinct bone so
        no summation occurs in practice.
        """
        out: dict[int, float] = {}
        for bone, weight in self.influences[v]:
            if weight != 0.0:
                out[bone] = out.get(bone, 0.0) + weight
        return out


@dataclass
class Pivot:
    name: str
    parent: int                 # index of parent pivot; -1 for the root
    translation: Vec3
    rotation: tuple[float, float, float, float]   # X, Y, Z, W
    fixup: Optional[list[float]] = None           # 16 floats M00..M33 (row attrs), if present


@dataclass
class Hierarchy:
    name: str
    pivots: list[Pivot] = field(default_factory=list)


@dataclass
class SubObject:
    bone_index: int
    sub_object_id: str
    render_kind: str            # "Mesh" or "CollisionBox"
    render_name: str            # referenced asset name (already resolved by the decompiler)


@dataclass
class Container:
    name: str
    hierarchy: Optional[str]    # referenced W3DHierarchy asset name
    sub_objects: list[SubObject] = field(default_factory=list)


@dataclass
class CollisionBox:
    """A ``W3DCollisionBox`` asset (``AssetTypeW3D.xsd`` L570-581): an oriented box
    given by its centre and *half*-extents, both in the owning bone's local space."""
    name: str
    center: Vec3
    extent: Vec3                # half-extents (box spans centre ± extent)


# --------------------------------------------------------------------------- #
# XML helpers
# --------------------------------------------------------------------------- #

def _local(tag: str) -> str:
    """Strip an ``{ns}`` prefix from an ElementTree tag -> local name."""
    return tag.rsplit("}", 1)[-1]


def _children(el: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in el if _local(c.tag) == name]


def _child(el: ET.Element, name: str) -> Optional[ET.Element]:
    for c in el:
        if _local(c.tag) == name:
            return c
    return None


def _fattr(el: ET.Element, name: str, default: float = 0.0) -> float:
    v = el.get(name)
    return float(v) if v is not None else default


def _vec3(el: ET.Element) -> Vec3:
    return (_fattr(el, "X"), _fattr(el, "Y"), _fattr(el, "Z"))


def _asset_root(path: str) -> ET.Element:
    """Return the single asset element inside <AssetDeclaration>."""
    root = ET.parse(path).getroot()
    if _local(root.tag) != "AssetDeclaration":
        raise ValueError(
            f"{path}: expected <AssetDeclaration> root, got <{_local(root.tag)}>"
        )
    kids = list(root)
    if not kids:
        raise ValueError(f"{path}: <AssetDeclaration> has no asset element")
    return kids[0]


def asset_type(path: str) -> str:
    """Local name of the asset element — e.g. 'W3DMesh', 'W3DHierarchy', 'W3DContainer'."""
    return _local(_asset_root(path).tag)


# --------------------------------------------------------------------------- #
# Per-type parsers
# --------------------------------------------------------------------------- #

def parse_mesh(path: str) -> MeshGeometry:
    el = _asset_root(path)
    return _parse_mesh_el(el, where=path)


def _parse_mesh_el(el: ET.Element, where: str = "<element>") -> MeshGeometry:
    if _local(el.tag) != "W3DMesh":
        raise ValueError(f"{where}: not a W3DMesh (<{_local(el.tag)}>)")
    path = where

    name = el.get("id", "mesh")

    # Positions define the vertex count; refuse the packed-passthrough form early
    # (no <Vertices> means the file was decompiled WITHOUT --semantic-mesh).
    pos_els = _children(el, "Vertices")
    if not pos_els:
        if _child(el, "VertexData") is not None:
            raise ValueError(
                f"{path}: this W3DMesh was decompiled WITHOUT --semantic-mesh "
                f"(found packed <VertexData>, not editable <Vertices>). "
                f"Re-run bab-decompile with --semantic-mesh."
            )
        raise ValueError(f"{path}: W3DMesh has no <Vertices> geometry")

    position_channels = [[_vec3(v) for v in _children(p, "V")] for p in pos_els]
    vcount = len(position_channels[0])

    normal_channels = [[_vec3(n) for n in _children(ne, "N")] for ne in _children(el, "Normals")]

    tangents = None
    te = _child(el, "Tangents")
    if te is not None:
        tangents = [_vec3(t) for t in _children(te, "T")]
    binormals = None
    be = _child(el, "Binormals")
    if be is not None:
        binormals = [_vec3(b) for b in _children(be, "B")]

    uv_channels = []
    for tce in _children(el, "TexCoords"):
        uv_channels.append([(_fattr(t, "X"), _fattr(t, "Y")) for t in _children(tce, "T")])

    colors = None
    ce = _child(el, "VertexColors")
    if ce is not None:
        colors = [
            (_fattr(c, "R"), _fattr(c, "G"), _fattr(c, "B"), _fattr(c, "A"))
            for c in _children(ce, "C")
        ]

    # Each <BoneInfluences> is one channel; the v-th <I> is vertex v's influence in
    # that channel. Collect per-vertex across channels.
    influences: list[list[tuple[int, float]]] = [[] for _ in range(vcount)]
    for bi in _children(el, "BoneInfluences"):
        for v, inf in enumerate(_children(bi, "I")):
            if v < vcount:
                influences[v].append((int(inf.get("Bone", "0")), _fattr(inf, "Weight")))

    # Triangles have TWO authoring shapes, both produced by the generic walker's
    # scalar-list path (StructReader.cs L447-473): when the schema is passed to
    # bab-decompile, the Triangle's `V` list is emitted as repeated <V>n</V> child
    # elements; without a schema it falls back to a single V="a b c" attribute. Accept
    # both so a schemaless decompile doesn't silently drop every face.
    triangles: list[tuple[int, int, int]] = []
    tris_el = _child(el, "Triangles")
    if tris_el is not None:
        for t in _children(tris_el, "T"):
            v_els = _children(t, "V")
            if v_els:
                idx = [int((vv.text or "").strip()) for vv in v_els]
            else:
                vattr = t.get("V")
                idx = [int(x) for x in vattr.split()] if vattr else []
            if len(idx) == 3:
                triangles.append((idx[0], idx[1], idx[2]))

    # FXShader texture slots. Shape (confirmed against the decompiled producer):
    #   <FXShader ShaderName="ObjectsNOD.fx" ...>
    #     <Constants>
    #       <Texture Name="DiffuseTexture"><Value>NURedeemer</Value></Texture>
    #       <Texture Name="NormalMap"><Value>NURedeemer_NRM</Value></Texture>
    #       <Float .../> <Bool .../>            (non-texture constants: ignored here)
    #     </Constants>
    #   </FXShader>
    # Only <Texture> constants carry a texture-asset reference; an empty <Value> (an
    # unassigned slot) is dropped so a caller never resolves "".
    shader = None
    fx = _child(el, "FXShader")
    if fx is not None:
        tex_map: dict[str, str] = {}
        consts = _child(fx, "Constants")
        if consts is not None:
            for t in _children(consts, "Texture"):
                slot = t.get("Name")
                ve = _child(t, "Value")
                val = (ve.text or "").strip() if ve is not None else ""
                if slot and val:
                    tex_map[slot] = val
        shader = ShaderTextures(shader_name=fx.get("ShaderName", ""), textures=tex_map)

    return MeshGeometry(
        name=name,
        vertex_count=vcount,
        position_channels=position_channels,
        normal_channels=normal_channels,
        tangents=tangents,
        binormals=binormals,
        uv_channels=uv_channels,
        colors=colors,
        influences=influences,
        triangles=triangles,
        shader=shader,
    )


def parse_texture(path: str) -> TextureAsset:
    """Parse a decompiled ``Texture`` / ``OnDemandTexture`` asset (finding 0024).

    The ``<Payload>`` text (when present) is a base64-encoded literal D3D9 .dds file;
    this returns it verbatim — base64 decoding + header validation live in
    :mod:`openwrath_import.dds` (no pixel decoder is forked into the add-on, invariant 3).
    """
    el = _asset_root(path)
    tag = _local(el.tag)
    if tag not in ("Texture", "OnDemandTexture"):
        raise ValueError(f"{path}: not a Texture/OnDemandTexture (<{tag}>)")
    payload = None
    pe = _child(el, "Payload")
    if pe is not None:
        payload = (pe.text or "").strip() or None
    return TextureAsset(
        name=el.get("id", "texture"),
        is_ondemand=(tag == "OnDemandTexture"),
        payload_b64=payload,
    )


_FIXUP_KEYS = [f"M{r}{c}" for r in range(4) for c in range(4)]  # M00,M01,..,M33


def parse_hierarchy(path: str) -> Hierarchy:
    return _parse_hierarchy_el(_asset_root(path), where=path)


def hierarchy_from_capture(cap: AssetCapture) -> Hierarchy:
    """Derive a :class:`Hierarchy` from a captured ``W3DHierarchy`` node (reuses the one
    reader) — used by the exporter to rebuild bind-pose world matrices for an assembled mesh."""
    if cap.asset_type != "W3DHierarchy":
        raise ValueError(f"capture is {cap.asset_type}, not W3DHierarchy")
    return _parse_hierarchy_el(_et_from_node(cap.node), where=f"capture:{cap.asset_id}")


def _parse_hierarchy_el(el: ET.Element, where: str = "<element>") -> Hierarchy:
    if _local(el.tag) != "W3DHierarchy":
        raise ValueError(f"{where}: not a W3DHierarchy (<{_local(el.tag)}>)")

    pivots: list[Pivot] = []
    for p in _children(el, "Pivot"):
        tr = _child(p, "Translation")
        ro = _child(p, "Rotation")
        fx = _child(p, "FixupMatrix")
        fixup = None
        if fx is not None:
            fixup = [_fattr(fx, k) for k in _FIXUP_KEYS]
        rotation = (
            _fattr(ro, "X"), _fattr(ro, "Y"), _fattr(ro, "Z"), _fattr(ro, "W")
        ) if ro is not None else (0.0, 0.0, 0.0, 1.0)
        pivots.append(
            Pivot(
                name=p.get("Name", ""),
                parent=int(p.get("Parent", "-1")),
                translation=_vec3(tr) if tr is not None else (0.0, 0.0, 0.0),
                rotation=rotation,
                fixup=fixup,
            )
        )
    return Hierarchy(name=el.get("id", "hierarchy"), pivots=pivots)


def parse_container(path: str) -> Container:
    el = _asset_root(path)
    if _local(el.tag) != "W3DContainer":
        raise ValueError(f"{path}: not a W3DContainer (<{_local(el.tag)}>)")

    subs: list[SubObject] = []
    for so in _children(el, "SubObject"):
        ro = _child(so, "RenderObject")
        kind, rname = "Mesh", ""
        if ro is not None:
            inner = next(iter(ro), None)       # <Mesh> or <CollisionBox>
            if inner is not None:
                kind = _local(inner.tag)
                # Decompiler emits the resolved asset name as the element text
                # (the "name\index" rewrite happens only on recompile).
                rname = (inner.text or "").split("\\", 1)[0].strip()
        subs.append(
            SubObject(
                bone_index=int(so.get("BoneIndex", "0")),
                sub_object_id=so.get("SubObjectID", ""),
                render_kind=kind,
                render_name=rname,
            )
        )
    # The Hierarchy reference is emitted as a plain resolved name (EmitReference ->
    # RenderReferenceName); the "name\index" rewrite happens only on recompile. Split
    # defensively anyway so an index-suffixed value (should it ever appear) still resolves.
    hierarchy = el.get("Hierarchy")
    if hierarchy:
        hierarchy = hierarchy.split("\\", 1)[0].strip()
    return Container(name=el.get("id", "container"), hierarchy=hierarchy, sub_objects=subs)


def parse_collision_box(path: str) -> CollisionBox:
    el = _asset_root(path)
    if _local(el.tag) != "W3DCollisionBox":
        raise ValueError(f"{path}: not a W3DCollisionBox (<{_local(el.tag)}>)")
    ce = _child(el, "Center")
    ex = _child(el, "Extent")
    return CollisionBox(
        name=el.get("id", "collisionbox"),
        center=_vec3(ce) if ce is not None else (0.0, 0.0, 0.0),
        extent=_vec3(ex) if ex is not None else (1.0, 1.0, 1.0),
    )


# --------------------------------------------------------------------------- #
# Generic, verbatim asset capture — the EXPORTER's lossless stash (milestone 2).
#
# This is deliberately a *dumb XML→tree copy*: it knows nothing about what a
# <Vertices> or <FXShader> MEANS. All W3D format/semantic knowledge still lives in
# the parse_* readers above (and in the OpenWrath CLI) — the capture carries NO second
# copy of it (CLAUDE.md invariant 3 / blender-integration.md §3). Its only job is to
# preserve the decoded authoring attributes exactly so an *unmodified* imported asset
# re-emits byte-for-byte what bab-decompile produced — which 0025 proved recompiles to
# the shipped bytes. The attribute/text VALUES are kept verbatim (as strings), so no
# float re-formatting can perturb the recompiled bytes.
#
# The capture is what the importer stashes on the Blender datablock (as JSON that
# survives a .blend save/reload); the exporter re-serialises it. For an EDITED mesh the
# exporter instead calls :func:`rewrite_mesh_geometry` to rebuild the geometry nodes from
# Blender's live mesh — the stated tier (never claimed byte-exact).
# --------------------------------------------------------------------------- #

# Child-element names of a <W3DMesh> that hold per-vertex / per-face GEOMETRY an exporter
# can reconstruct from a Blender mesh. The EDITED path rewrites exactly these from live
# geometry; everything else (BoundingBox/Sphere, FXShader, AABTree, header attrs) is
# carried through from the capture. (AABTree/Tangents/Binormals are DERIVED structures —
# an edited mesh drops them rather than inventing them; see rewrite_mesh_geometry.)
_MESH_GEOMETRY_TAGS = (
    "Vertices", "Normals", "Tangents", "Binormals", "TexCoords",
    "VertexColors", "BoneInfluences", "Triangles",
)


@dataclass
class Node:
    """A minimal, order-preserving XML node (local tag names, namespace stripped).

    ``text`` is kept only for leaf elements (those with no child elements) — i.e. a
    value like ``<V>2</V>`` or ``<Dist>0.021343</Dist>``; the pretty-print whitespace
    between child elements is intentionally dropped (XML parsers ignore it, so it cannot
    affect the recompiled bytes)."""

    tag: str
    attrib: dict[str, str] = field(default_factory=dict)
    text: Optional[str] = None
    children: list["Node"] = field(default_factory=list)


@dataclass
class AssetCapture:
    """A verbatim capture of one decoded asset element (its ``<W3DMesh>`` / ``<W3DHierarchy>``
    / ``<W3DContainer>`` / ``<W3DCollisionBox>`` …), the exporter's lossless stash."""

    asset_type: str
    asset_id: str
    node: Node


def _node_from_et(el: ET.Element) -> Node:
    kids = list(el)
    text = None
    if not kids:  # leaf: keep its value verbatim
        text = el.text
    return Node(
        tag=_local(el.tag),
        attrib={_local(k): v for k, v in el.attrib.items()},
        text=text,
        children=[_node_from_et(c) for c in kids],
    )


def _et_from_node(node: Node) -> ET.Element:
    el = ET.Element(f"{{{ASSET_NS}}}{node.tag}")
    for k, v in node.attrib.items():
        el.set(k, v)
    if node.children:
        for c in node.children:
            el.append(_et_from_node(c))
    elif node.text is not None:
        el.text = node.text
    return el


def capture_asset(path: str) -> AssetCapture:
    """Capture a decoded asset file verbatim (the exporter's stash). The returned tree
    re-serialises (via :func:`serialize_capture`) to XML that recompiles byte-identically
    to the input, because every value is preserved as its exact decoded string."""
    el = _asset_root(path)
    node = _node_from_et(el)
    return AssetCapture(asset_type=node.tag, asset_id=node.attrib.get("id", ""), node=node)


def capture_to_json(cap: AssetCapture) -> str:
    """Serialise a capture to a compact JSON string, for stashing on a Blender datablock.
    Compact keys keep large meshes small: ``t``=tag, ``a``=attrib, ``x``=text, ``c``=children."""
    import json

    def enc(n: Node):
        d = {"t": n.tag}
        if n.attrib:
            d["a"] = n.attrib
        if n.text is not None:
            d["x"] = n.text
        if n.children:
            d["c"] = [enc(c) for c in n.children]
        return d

    return json.dumps({"ty": cap.asset_type, "id": cap.asset_id, "n": enc(cap.node)},
                      separators=(",", ":"))


def capture_from_json(s: str) -> AssetCapture:
    import json

    def dec(d) -> Node:
        return Node(tag=d["t"], attrib=d.get("a", {}), text=d.get("x"),
                    children=[dec(c) for c in d.get("c", [])])

    o = json.loads(s)
    return AssetCapture(asset_type=o["ty"], asset_id=o["id"], node=dec(o["n"]))


def serialize_capture(cap: AssetCapture) -> str:
    """Render a capture back to a full authoring-XML document (``<AssetDeclaration>`` +
    the asset element), ready for the compiler. Whitespace/indentation is cosmetic and
    does not affect the recompiled bytes; the element/attribute VALUES are verbatim."""
    ET.register_namespace("", ASSET_NS)
    root = ET.Element(f"{{{ASSET_NS}}}AssetDeclaration")
    root.append(_et_from_node(cap.node))
    try:
        ET.indent(root, space="  ")  # py3.9+: pretty-print, purely cosmetic
    except AttributeError:
        pass
    body = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="utf-8"?>\n' + body + "\n"


def mesh_geometry_from_capture(cap: AssetCapture) -> MeshGeometry:
    """Derive the float-based :class:`MeshGeometry` from a captured ``W3DMesh`` node, reusing
    the one semantic reader (:func:`_parse_mesh_el`) — no second parse. Used by the exporter's
    live-mesh coupling check (does Blender's mesh still equal the stashed authoring geometry?)."""
    if cap.asset_type != "W3DMesh":
        raise ValueError(f"capture is {cap.asset_type}, not W3DMesh")
    return _parse_mesh_el(_et_from_node(cap.node), where=f"capture:{cap.asset_id}")


def _mesh_geometry_nodes(geo: "MeshGeometry") -> list[Node]:
    """Build the geometry child-nodes (<Vertices>/<Normals>/<TexCoords>/<VertexColors>/
    <BoneInfluences>/<Triangles>) from a MeshGeometry — the EDITED-path reconstruction.

    This is the ONE place the exporter encodes mesh-geometry XML shape (mirroring
    :func:`parse_mesh`'s element names). It is **stated tier** output: values come from
    Blender floats via :func:`_fnum`, so it is never claimed byte-exact. Tangents /
    Binormals / AABTree are DERIVED and are deliberately not synthesised here."""
    out: list[Node] = []
    for chan in geo.position_channels:
        out.append(Node("Vertices", children=[_vec3_node("V", v) for v in chan]))
    for chan in geo.normal_channels:
        out.append(Node("Normals", children=[_vec3_node("N", v) for v in chan]))
    for chan in geo.uv_channels:
        out.append(Node("TexCoords",
                        children=[Node("T", {"X": _fnum(u), "Y": _fnum(v)}) for (u, v) in chan]))
    if geo.colors:
        out.append(Node("VertexColors", children=[
            Node("C", {"R": _fnum(r), "G": _fnum(g), "B": _fnum(b), "A": _fnum(a)})
            for (r, g, b, a) in geo.colors]))
    # One <BoneInfluences> channel per influence slot (channel c = the c-th slot of each vertex).
    nchan = max((len(geo.influences[v]) for v in range(geo.vertex_count)), default=0)
    for c in range(nchan):
        inf_nodes = []
        for v in range(geo.vertex_count):
            slot = geo.influences[v]
            bone, weight = slot[c] if c < len(slot) else (0, 0.0)
            inf_nodes.append(Node("I", {"Weight": _fnum(weight), "Bone": str(bone)}))
        out.append(Node("BoneInfluences", children=inf_nodes))
    tri_nodes = []
    for (a, b, c) in geo.triangles:
        tri_nodes.append(Node("T", children=[Node("V", text=str(a)),
                                             Node("V", text=str(b)),
                                             Node("V", text=str(c))]))
    out.append(Node("Triangles", children=tri_nodes))
    return out


def rewrite_mesh_geometry(cap: AssetCapture, geo: "MeshGeometry") -> AssetCapture:
    """Return a new capture with the mesh geometry REPLACED by ``geo`` (the EDITED path).

    Non-geometry children (BoundingBox/Sphere, FXShader, header attrs) are carried through
    from the original capture. DERIVED structures the exporter cannot faithfully regenerate
    from an edited Blender mesh — ``AABTree``, ``Tangents``, ``Binormals`` — are DROPPED
    (the compiler rebuilds/omits them); this is why an edited mesh is stated-tier, never
    byte-exact. Order: keep the first geometry child's position, insert the rebuilt geometry
    there, keep every non-geometry child in place."""
    geo_nodes = _mesh_geometry_nodes(geo)
    new_children: list[Node] = []
    inserted = False
    for ch in cap.node.children:
        if ch.tag in _MESH_GEOMETRY_TAGS or ch.tag == "AABTree":
            if not inserted:
                new_children.extend(geo_nodes)
                inserted = True
            continue  # drop the original geometry/derived node
        new_children.append(ch)
    if not inserted:
        new_children.extend(geo_nodes)
    new_node = Node(tag=cap.node.tag, attrib=dict(cap.node.attrib),
                    text=cap.node.text, children=new_children)
    return AssetCapture(asset_type=cap.asset_type, asset_id=cap.asset_id, node=new_node)


def _node_child(node: Node, tag: str) -> Optional[Node]:
    for c in node.children:
        if c.tag == tag:
            return c
    return None


def rewrite_collision_box(cap: AssetCapture, center: "Vec3", extent: "Vec3") -> AssetCapture:
    """Return a capture with the box's ``<Center>``/``<Extent>`` set from a live empty (the
    edited path — stated tier). All other attributes (id, JoypadPickingOnly) are carried through."""
    new_children = []
    for c in cap.node.children:
        if c.tag == "Center":
            new_children.append(Node("Center", {"X": _fnum(center[0]), "Y": _fnum(center[1]),
                                                "Z": _fnum(center[2])}))
        elif c.tag == "Extent":
            new_children.append(Node("Extent", {"X": _fnum(extent[0]), "Y": _fnum(extent[1]),
                                                "Z": _fnum(extent[2])}))
        else:
            new_children.append(c)
    node = Node(cap.node.tag, dict(cap.node.attrib), cap.node.text, new_children)
    return AssetCapture(cap.asset_type, cap.asset_id, node)


def rewrite_hierarchy(cap: AssetCapture, pivots: list["Pivot"]) -> AssetCapture:
    """Return a capture with each ``<Pivot>``'s ``<Translation>``/``<Rotation>`` set from live
    armature bones (the edited path — stated tier, LOSSY: the viewer armature is a reduced
    visualisation of the pivots). Name / Parent / FixupMatrix are carried through from the stash;
    pivots are matched to ``<Pivot>`` nodes by order."""
    out_children = []
    idx = 0
    for c in cap.node.children:
        if c.tag == "Pivot" and idx < len(pivots):
            p = pivots[idx]
            idx += 1
            new_kids = []
            for sub in c.children:
                if sub.tag == "Translation":
                    new_kids.append(Node("Translation", {"X": _fnum(p.translation[0]),
                                                         "Y": _fnum(p.translation[1]),
                                                         "Z": _fnum(p.translation[2])}))
                elif sub.tag == "Rotation":
                    rx, ry, rz, rw = p.rotation
                    new_kids.append(Node("Rotation", {"X": _fnum(rx), "Y": _fnum(ry),
                                                      "Z": _fnum(rz), "W": _fnum(rw)}))
                else:
                    new_kids.append(sub)  # FixupMatrix et al. carried through
            out_children.append(Node("Pivot", dict(c.attrib), c.text, new_kids))
        else:
            out_children.append(c)
    node = Node(cap.node.tag, dict(cap.node.attrib), cap.node.text, out_children)
    return AssetCapture(cap.asset_type, cap.asset_id, node)


def rewrite_container(cap: AssetCapture, sub_objects: list["SubObject"]) -> AssetCapture:
    """Return a capture whose ``<SubObject>`` list is rebuilt from a live collection's membership
    + bindings (the edited path — stated tier). The W3DContainer attributes (id, Hierarchy) and
    any non-SubObject children are carried through from the stash."""
    rebuilt = []
    for so in sub_objects:
        wrap = "Mesh" if so.render_kind == "Mesh" else "CollisionBox"
        rebuilt.append(Node("SubObject",
                            {"BoneIndex": str(so.bone_index), "SubObjectID": so.sub_object_id},
                            None,
                            [Node("RenderObject", {}, None, [Node(wrap, {}, so.render_name, [])])]))
    out_children = [c for c in cap.node.children if c.tag != "SubObject"] + rebuilt
    node = Node(cap.node.tag, dict(cap.node.attrib), cap.node.text, out_children)
    return AssetCapture(cap.asset_type, cap.asset_id, node)


def _vec3_node(tag: str, v: "Vec3") -> Node:
    return Node(tag, {"X": _fnum(v[0]), "Y": _fnum(v[1]), "Z": _fnum(v[2])})


def _fnum(x: float) -> str:
    """Render a float for EDITED-path (stated-tier) authoring XML. ``repr`` round-trips a
    float64 exactly, and the compiler parses it to the nearest float32 — adequate for the
    "loads + renders" tier (this path is never byte-compared). ``-0.0`` keeps its sign."""
    f = float(x)
    if f == 0.0:
        import math
        return "-0" if math.copysign(1.0, f) < 0 else "0"
    return repr(f)
