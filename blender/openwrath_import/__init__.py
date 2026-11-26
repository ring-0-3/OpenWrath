"""OpenWrath model importer — a read-only Blender front-end to the OpenWrath CLI.

Imports a shipped Kane's Wrath model (``W3DContainer`` + its ``W3DHierarchy`` and
``W3DMesh`` assets) into Blender. All byte/format work is delegated to
``bab-decompile``; this add-on only translates its XML <-> Blender datablocks
(``docs/design/blender-integration.md``). Read-only; no exporter in this milestone.

v1 limitations (stated, not byte-exact): no animation, placeholder materials,
no textures, no export. See ``blender/README.md``.
"""

bl_info = {
    "name": "OpenWrath Model Importer/Exporter (Kane's Wrath)",
    "author": "OpenWrath",
    "version": (0, 2, 0),
    "blender": (4, 1, 0),
    "location": "File > Import / Export > OpenWrath (.xml)",
    "description": "Import and export Kane's Wrath W3D models. Unmodified round-trips are "
                   "byte-exact vs shipped (finding 0028); edited geometry is stated-tier.",
    "category": "Import-Export",
}

import importlib
import os
import tempfile

# w3x_xml and cli are pure-Python (no bpy) so they import anywhere, incl. headless
# tests. scene_builder imports bpy and is pulled in lazily (see _sb()) so the parser
# is usable outside Blender.
if "w3x_xml" in locals():  # support Blender's "Reload Scripts"
    importlib.reload(w3x_xml)  # noqa: F821
    importlib.reload(cli)      # noqa: F821
    importlib.reload(dds)      # noqa: F821
else:
    from . import w3x_xml, cli, dds


def _sb():
    """Lazy-import the bpy-dependent scene builder (and reload under Blender)."""
    from . import scene_builder
    importlib.reload(scene_builder)
    return scene_builder


def _sr():
    """Lazy-import the bpy-dependent scene reader / exporter (and reload under Blender)."""
    from . import scene_reader
    importlib.reload(scene_reader)
    return scene_reader


# --------------------------------------------------------------------------- #
# Reference resolution: sibling .xml first, CLI decompile on demand
# --------------------------------------------------------------------------- #

class AssetResolver:
    def __init__(self, base_dir, cfg=None, cache_dir=None, semantic_mesh=True):
        self.base_dir = base_dir
        self.cfg = cfg
        self.cache_dir = cache_dir
        self.semantic_mesh = semantic_mesh

    def resolve(self, asset_name, type_hint=None):
        """Locate a referenced asset's XML next to the import file.

        Handles both output naming conventions: ``decompile --only`` writes
        ``<name>.xml``, while ``decompile-stream`` writes the type-qualified
        ``<TypeName>.<name>.xml`` (because instance names are unique only per type).
        Falls back to a glob, then to on-demand CLI decompile if configured.
        """
        import glob

        candidates = [asset_name + ".xml"]
        if type_hint:
            candidates.append(f"{type_hint}.{asset_name}.xml")
        for c in candidates:
            p = os.path.join(self.base_dir, c)
            if os.path.isfile(p):
                return p

        hits = sorted(glob.glob(os.path.join(self.base_dir, f"*.{asset_name}.xml")))
        if type_hint:
            typed = [h for h in hits if os.path.basename(h).startswith(type_hint + ".")]
            if typed:
                return typed[0]
        if len(hits) == 1:
            return hits[0]

        if self.cfg is not None:
            outdir = self.cache_dir or tempfile.mkdtemp(prefix="openwrath_dec_")
            self.cache_dir = outdir
            return cli.decompile_asset(self.cfg, asset_name, outdir,
                                       semantic_mesh=self.semantic_mesh)
        raise cli.DecompileError(
            f"referenced asset '{asset_name}' not found next to the import file "
            f"(tried {candidates} and *.{asset_name}.xml in {self.base_dir}) and no "
            f"CLI manifest was configured to decompile it on demand."
        )


# --------------------------------------------------------------------------- #
# Base-color texture resolution (finding 0024 pass-through + the DDS decidable anchor)
# --------------------------------------------------------------------------- #

def _resolve_texture(resolver, name):
    """Resolve a texture asset NAME to a parsed :class:`w3x_xml.TextureAsset`, or None.

    One ``resolver.resolve`` call finds whichever record type exists next to the import
    file — ``Texture.<name>.xml`` directly, or ``OnDemandTexture.<name>.xml`` via the
    resolver's ``*.<name>.xml`` glob — and :func:`w3x_xml.parse_texture` detects which it
    is. Never raises: a missing/undecodable texture returns None (→ placeholder + report),
    so one bad slot never aborts the import."""
    try:
        path = resolver.resolve(name, type_hint="Texture")
    except Exception:
        return None
    try:
        return w3x_xml.parse_texture(path)
    except Exception:
        return None


def _base_color_material_for(sb, mesh, resolver, out_dir, report):
    """Return ``(material_or_None, status)`` for a mesh's **base-color** texture slot.

    The slot is chosen by :data:`w3x_xml.BASE_COLOR_SLOTS` precedence (``DiffuseTexture``
    for object shaders, ``Texture_0`` for the effect/muzzle shaders) — never a per-shader
    special-case. ``status`` is one of ``textured`` / ``no_shader`` (no ``<FXShader>`` at
    all) / ``no_basemap`` (an ``<FXShader>`` whose constants expose no base-color slot —
    correctly left on the placeholder) / ``ondemand`` / ``unresolved`` /
    ``invalid`` — the honest bucket, reported and counted, never a silent drop. The DDS
    payload is byte-exact (finding 0024), so "decodes to a valid DDS" is a byte-DECIDABLE
    gate (:mod:`openwrath_import.dds`); only a slot that passes it gets a real material.
    """
    import os

    sh = getattr(mesh, "shader", None)
    if not sh:
        return None, "no_shader"
    slot, name = sh.base_color()
    if not name:
        # Has an <FXShader> but no base-color slot (its constants expose only numeric params
        # / non-base-color maps). Textureless BY DESIGN, not a miss — keep the placeholder,
        # report accurately. (Shader name is NOT a proxy for this: a DefaultW3D.fx mesh may
        # or may not carry a Texture_0 base map — decided per mesh by base_color(), not by .fx.)
        report(f"note: shader '{sh.shader_name}' has no base-color texture slot "
               f"(base-color slots: {', '.join(w3x_xml.BASE_COLOR_SLOTS)}) — using placeholder.")
        return None, "no_basemap"

    tex = _resolve_texture(resolver, name)
    if tex is None:
        report(f"note: base-color texture '{name}' (<{slot}>) did not resolve in the sampled "
               f"stream — using placeholder.")
        return None, "unresolved"
    if tex.is_ondemand or not tex.payload_b64:
        report(f"note: base-color texture '{name}' (<{slot}>) is an OnDemandTexture (pixels "
               f"streamed on demand / loose file — no payload in the stream) — using placeholder.")
        return None, "ondemand"

    data, info = dds.decode_and_probe(tex.payload_b64)
    if data is None or not info.valid:
        report(f"WARNING: base-color texture '{name}' (<{slot}>) payload is not a valid DDS "
               f"({info.reason}) — using placeholder.")
        return None, "invalid"

    dds_path = os.path.join(out_dir, name + ".dds")
    try:
        with open(dds_path, "wb") as fh:
            fh.write(data)
    except OSError as e:
        report(f"WARNING: could not write decoded DDS for '{name}' ({e}) — using placeholder.")
        return None, "invalid"

    fmt = info.fourcc or (f"{info.bit_count}bpp" if info.uncompressed else "?")
    report(f"textured: '{name}' via <{slot}> ({info.width}x{info.height} {fmt}, "
           f"{info.mip_count} mip(s)) -> Base Color.")
    return sb.image_material(name, dds_path), "textured"


# --------------------------------------------------------------------------- #
# Orchestration (pure; no bpy operator state)
# --------------------------------------------------------------------------- #

def import_file(filepath, *, resolver=None, import_collision=False, report=print):
    """Import an asset XML into the current scene. Dispatches on asset type.

    Returns a short human summary string.
    """
    sb = _sb()  # lazy bpy import — keeps this module importable headless

    atype = w3x_xml.asset_type(filepath)
    base_dir = os.path.dirname(os.path.abspath(filepath))
    if resolver is None:
        resolver = AssetResolver(base_dir)

    if atype == "W3DMesh":
        mesh = w3x_xml.parse_mesh(filepath)
        cap = w3x_xml.capture_asset(filepath)
        mat, status = _base_color_material_for(sb, mesh, resolver, resolver.base_dir, report)
        sb.build_mesh(mesh, material=mat, capture=cap)
        tex_note = "textured" if status == "textured" else f"untextured ({status})"
        return (f"Imported W3DMesh '{mesh.name}' ({mesh.vertex_count} verts, "
                f"{len(mesh.triangles)} tris) — {tex_note}.")

    if atype == "W3DHierarchy":
        hier = w3x_xml.parse_hierarchy(filepath)
        sb.build_armature(hier, capture=w3x_xml.capture_asset(filepath))
        return f"Imported W3DHierarchy '{hier.name}' ({len(hier.pivots)} bones)."

    if atype == "W3DCollisionBox":
        box = w3x_xml.parse_collision_box(filepath)
        sub = w3x_xml.SubObject(bone_index=0, sub_object_id=box.name,
                                render_kind="CollisionBox", render_name=box.name)
        sb.build_collision_box(sub, box=box, capture=w3x_xml.capture_asset(filepath))
        return f"Imported W3DCollisionBox '{box.name}'."

    if atype == "W3DContainer":
        return _import_container(filepath, resolver, import_collision, report)

    raise ValueError(f"Unsupported asset type for import: {atype}")


def _import_container(filepath, resolver, import_collision, report):
    import bpy
    sb = _sb()

    cont = w3x_xml.parse_container(filepath)
    coll = bpy.data.collections.new(cont.name)
    bpy.context.scene.collection.children.link(coll)
    # Stash the container capture on the collection datablock (survives .blend reload).
    sb.stash_capture(coll, w3x_xml.capture_asset(filepath))

    arm_obj = None
    bone_names = {}
    worlds = None
    if cont.hierarchy:
        try:
            hpath = resolver.resolve(cont.hierarchy, type_hint="W3DHierarchy")
            hier = w3x_xml.parse_hierarchy(hpath)
            arm_obj, bone_names, worlds = sb.build_armature(
                hier, collection=coll, capture=w3x_xml.capture_asset(hpath))
        except Exception as e:  # hierarchy optional for a bare view
            report(f"WARNING: could not import hierarchy '{cont.hierarchy}': {e}")

    # Collision boxes live in their OWN child collection so they can be hidden in one click
    # and never clutter the model (they are limb-sized wire cubes once real extents are applied).
    box_coll = None
    n_mesh = n_box = n_box_sized = 0
    tex_status: dict[str, int] = {}
    for sub in cont.sub_objects:
        if sub.render_kind == "CollisionBox":
            if import_collision:
                if box_coll is None:
                    box_coll = bpy.data.collections.new(f"{cont.name}_Collision")
                    coll.children.link(box_coll)
                box = None
                box_cap = None
                if sub.render_name:
                    try:  # the box asset is a modeled type — resolve + decode like any ref
                        bpath = resolver.resolve(sub.render_name, type_hint="W3DCollisionBox")
                        box = w3x_xml.parse_collision_box(bpath)
                        box_cap = w3x_xml.capture_asset(bpath)
                        n_box_sized += 1
                    except Exception as e:
                        report(f"note: collision box '{sub.render_name}' extents unavailable "
                               f"(drawing unit cube): {e}")
                sb.build_collision_box(sub, box=box, arm_obj=arm_obj,
                                       worlds=worlds, collection=box_coll, capture=box_cap)
                n_box += 1
            continue
        if not sub.render_name:
            continue
        try:
            mpath = resolver.resolve(sub.render_name, type_hint="W3DMesh")
            mesh = w3x_xml.parse_mesh(mpath)
            mcap = w3x_xml.capture_asset(mpath)
            mat, status = _base_color_material_for(sb, mesh, resolver, resolver.base_dir, report)
            tex_status[status] = tex_status.get(status, 0) + 1
            mobj = sb.build_mesh(mesh, collection=coll, bone_names=bone_names,
                                 worlds=worlds, bone_index=sub.bone_index, material=mat,
                                 capture=mcap)
            if arm_obj is not None:
                sb.bind_mesh_to_armature(mobj, arm_obj, sub, bone_names, worlds)
            n_mesh += 1
        except Exception as e:
            report(f"WARNING: could not import mesh '{sub.render_name}': {e}")

    # Honest texture coverage: how many meshes got a real diffuse vs fell back, bucketed.
    n_tex = tex_status.get("textured", 0)
    n_placeholder = n_mesh - n_tex
    buckets = ", ".join(f"{k}={v}" for k, v in sorted(tex_status.items()) if k != "textured")
    report(f"textures: {n_tex}/{n_mesh} mesh(es) got a real base-color texture; "
           f"{n_placeholder} on the grey placeholder"
           + (f" ({buckets})" if buckets else "")
           + ". Material/scene display is stated-tier (no byte oracle); only the DDS payload "
             "validity is byte-decidable.")
    # Fingerprint the assembled container (membership + sub-object bindings) now that every
    # mesh/box is built, so the exporter can tell an unmodified reload (byte-exact) from an
    # edited (regrouped/rebound) container (stated).
    sb.stash_fingerprint(coll, "W3DContainer")

    box_note = f"{n_box} collision box(es)"
    if n_box:
        box_note += f" ({n_box_sized} with real extents)"
    return (f"Imported W3DContainer '{cont.name}': {n_mesh} mesh(es) "
            f"({n_tex} textured, {n_placeholder} placeholder), "
            f"{len(bone_names)} bone(s), {box_note}.")


# --------------------------------------------------------------------------- #
# Export (scene -> W3X authoring XML). The mirror of import_file; headless-drivable
# by the round-trip gate via `blender --background --python`.
# --------------------------------------------------------------------------- #

def _select_target(targets, asset_id, asset_type, obj):
    if obj is not None:
        for t in targets:
            if t["obj"] is obj or t["idblock"] is getattr(obj, "data", None) or t["idblock"] is obj:
                return t
        raise ValueError(f"object '{getattr(obj, 'name', obj)}' carries no OpenWrath stash.")
    chosen = targets
    if asset_id is not None:
        chosen = [t for t in chosen if t["asset_id"] == asset_id]
    if asset_type is not None:
        chosen = [t for t in chosen if t["asset_type"] == asset_type]
    if not chosen:
        raise ValueError(f"no stashed asset matched asset_id={asset_id!r}, asset_type={asset_type!r}.")
    if len(chosen) > 1:
        # A full model import leaves many stashed assets; prefer the single container.
        conts = [t for t in chosen if t["kind"] == "container"]
        if len(conts) == 1:
            return conts[0]
        ids = ", ".join(sorted(t["asset_id"] for t in chosen))
        raise ValueError(f"{len(chosen)} stashed assets in the scene; disambiguate with "
                         f"asset_id=/asset_type= (found: {ids}).")
    return chosen[0]


def export_file(filepath, *, asset_id=None, asset_type=None, obj=None, report=print):
    """Export ONE stashed asset from the current scene to authoring XML at ``filepath``.

    Mirrors :func:`import_file`. Selects the target by ``obj`` (the active object), else by
    ``asset_id`` / ``asset_type``, else the unique stashed asset (or the single container of
    a full-model import). Returns a short summary string. The tier (``byte-exact`` for an
    unmodified mesh, ``stated`` for an edited one) is decided in :mod:`scene_reader` and
    reported — never silently claimed byte-exact."""
    sr = _sr()
    targets = sr.find_export_targets()
    if not targets:
        raise ValueError("no OpenWrath-imported asset found in the scene to export "
                         "(nothing carries the import stash — import a model first).")
    target = _select_target(targets, asset_id, asset_type, obj)
    cap, tier, note = sr.export_target(target)
    xml = w3x_xml.serialize_capture(cap)
    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write(xml)
    report(f"Exported {cap.asset_type} '{cap.asset_id}' [{tier}] {note}")
    return f"Exported {cap.asset_type} '{cap.asset_id}' -> {os.path.basename(filepath)} [{tier}]."


def export_all(dirpath, *, report=print):
    """Export EVERY stashed asset in the scene to ``dirpath`` as ``<Type>.<id>.xml`` (the
    decompile-stream naming). Used for a whole-model round-trip (import container → reload →
    export all → recompile → compare). Returns ``(count, [(type,id,tier), ...])``."""
    sr = _sr()
    targets = sr.find_export_targets()
    results = []
    for t in targets:
        cap, tier, note = sr.export_target(t)
        out = os.path.join(dirpath, f"{cap.asset_type}.{cap.asset_id}.xml")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(w3x_xml.serialize_capture(cap))
        report(f"  exported {cap.asset_type} '{cap.asset_id}' [{tier}]")
        results.append((cap.asset_type, cap.asset_id, tier))
    return len(results), results


# --------------------------------------------------------------------------- #
# Blender operator + menu
# --------------------------------------------------------------------------- #

def _register_operator():
    import bpy
    from bpy.props import BoolProperty, StringProperty
    from bpy_extras.io_utils import ImportHelper, ExportHelper

    class OPENWRATH_OT_import_model(bpy.types.Operator, ImportHelper):
        """Import a decompiled Kane's Wrath model (W3DContainer / Hierarchy / Mesh)"""
        bl_idname = "openwrath.import_model"
        bl_label = "Import OpenWrath Model"
        bl_options = {"REGISTER", "UNDO"}

        filename_ext = ".xml"
        filter_glob: StringProperty(default="*.xml", options={"HIDDEN"})

        import_collision: BoolProperty(
            name="Import collision boxes",
            description="Add collision boxes (real extents) as wire empties in a separate, "
                        "hideable '<model>_Collision' collection. Off by default — they are "
                        "limb-sized and clutter the model; enable to inspect the hit volumes.",
            default=False,
        )
        # Optional on-demand decompile — only used when a referenced asset is not
        # already present as a sibling .xml next to the chosen file.
        bab_cmd: StringProperty(
            name="bab-decompile command",
            description="Launcher for bab-decompile (e.g. 'bab-decompile' or "
                        "'dotnet /path/Debug/bab-decompile.dll'). Blank = auto-detect.",
            default="",
        )
        manifest: StringProperty(
            name="Stream manifest",
            description="Stream .manifest to decompile referenced assets from "
                        "(only needed if they are not sibling .xml files)",
            default="", subtype="FILE_PATH",
        )
        schema: StringProperty(name="Schema (.xsd)", default="", subtype="FILE_PATH")
        ref_manifests: StringProperty(
            name="Reference manifests",
            description="';'-separated reference .manifest paths", default="",
        )
        stringhashes: StringProperty(name="String hashes (.xml)", default="", subtype="FILE_PATH")

        def execute(self, context):
            base_dir = os.path.dirname(os.path.abspath(self.filepath))
            cfg = None
            if self.manifest:
                bab = cli.resolve_bab_cmd(self.bab_cmd)
                cfg = cli.CliConfig.from_env_or_fields(
                    bab, self.manifest, self.schema, self.ref_manifests, self.stringhashes
                )
            resolver = AssetResolver(base_dir, cfg=cfg)
            try:
                summary = import_file(
                    self.filepath, resolver=resolver,
                    import_collision=self.import_collision,
                    report=lambda m: self.report({"WARNING"}, m),
                )
            except Exception as e:
                self.report({"ERROR"}, f"OpenWrath import failed: {e}")
                return {"CANCELLED"}
            self.report({"INFO"}, summary)
            return {"FINISHED"}

    class OPENWRATH_OT_export_model(bpy.types.Operator, ExportHelper):
        """Export the OpenWrath asset back to W3X authoring XML.

        An *unmodified* imported mesh round-trips BYTE-EXACT (the stash the importer wrote
        onto the datablock recompiles to the shipped bytes); an *edited* mesh is exported as
        a stated-tier ("loads + renders") reconstruction, never claimed byte-exact. The
        exporter reports which tier it used."""
        bl_idname = "openwrath.export_model"
        bl_label = "Export OpenWrath Asset"
        bl_options = {"REGISTER"}

        filename_ext = ".xml"
        filter_glob: StringProperty(default="*.xml", options={"HIDDEN"})

        use_active: BoolProperty(
            name="Export active object only",
            description="Export the asset of the active object (default). Off: export the "
                        "unique stashed asset, or the single container of a full-model import.",
            default=True,
        )

        def execute(self, context):
            obj = context.active_object if self.use_active else None
            try:
                summary = export_file(
                    self.filepath, obj=obj,
                    report=lambda m: self.report({"INFO"}, m),
                )
            except Exception as e:
                self.report({"ERROR"}, f"OpenWrath export failed: {e}")
                return {"CANCELLED"}
            self.report({"INFO"}, summary)
            return {"FINISHED"}

    def menu_func_import(self, context):
        self.layout.operator(OPENWRATH_OT_import_model.bl_idname,
                             text="OpenWrath Model (.xml)")

    def menu_func_export(self, context):
        self.layout.operator(OPENWRATH_OT_export_model.bl_idname,
                             text="OpenWrath Asset (.xml)")

    return (OPENWRATH_OT_import_model, menu_func_import,
            OPENWRATH_OT_export_model, menu_func_export)


_classes = []
_menu_func_import = None
_menu_func_export = None


def register():
    import bpy
    global _classes, _menu_func_import, _menu_func_export
    imp_op, _menu_func_import, exp_op, _menu_func_export = _register_operator()
    _classes = [imp_op, exp_op]
    for c in _classes:
        bpy.utils.register_class(c)
    bpy.types.TOPBAR_MT_file_import.append(_menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(_menu_func_export)


def unregister():
    import bpy
    global _classes, _menu_func_import, _menu_func_export
    if _menu_func_import is not None:
        bpy.types.TOPBAR_MT_file_import.remove(_menu_func_import)
    if _menu_func_export is not None:
        bpy.types.TOPBAR_MT_file_export.remove(_menu_func_export)
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
    _classes = []


if __name__ == "__main__":
    register()
