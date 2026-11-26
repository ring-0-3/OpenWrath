"""OpenWrath model importer — a read-only Blender front-end to the OpenWrath CLI.

Imports a shipped Kane's Wrath model (``W3DContainer`` + its ``W3DHierarchy`` and
``W3DMesh`` assets) into Blender. All byte/format work is delegated to
``bab-decompile``; this add-on only translates its XML <-> Blender datablocks
(``docs/design/blender-integration.md``). Read-only; no exporter in this milestone.

v1 limitations (stated, not byte-exact): no animation, placeholder materials,
no textures, no export. See ``blender/README.md``.
"""

bl_info = {
    "name": "OpenWrath Model Importer (Kane's Wrath)",
    "author": "OpenWrath",
    "version": (0, 1, 0),
    "blender": (4, 1, 0),
    "location": "File > Import > OpenWrath Model (.xml)",
    "description": "Import a decompiled Kane's Wrath W3D model (viewer / read-only).",
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
else:
    from . import w3x_xml, cli


def _sb():
    """Lazy-import the bpy-dependent scene builder (and reload under Blender)."""
    from . import scene_builder
    importlib.reload(scene_builder)
    return scene_builder


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
# Orchestration (pure; no bpy operator state)
# --------------------------------------------------------------------------- #

def import_file(filepath, *, resolver=None, import_collision=True, report=print):
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
        sb.build_mesh(mesh)
        return f"Imported W3DMesh '{mesh.name}' ({mesh.vertex_count} verts, {len(mesh.triangles)} tris)."

    if atype == "W3DHierarchy":
        hier = w3x_xml.parse_hierarchy(filepath)
        sb.build_armature(hier)
        return f"Imported W3DHierarchy '{hier.name}' ({len(hier.pivots)} bones)."

    if atype == "W3DContainer":
        return _import_container(filepath, resolver, import_collision, report)

    raise ValueError(f"Unsupported asset type for import: {atype}")


def _import_container(filepath, resolver, import_collision, report):
    import bpy
    sb = _sb()

    cont = w3x_xml.parse_container(filepath)
    coll = bpy.data.collections.new(cont.name)
    bpy.context.scene.collection.children.link(coll)

    arm_obj = None
    bone_names = {}
    if cont.hierarchy:
        try:
            hpath = resolver.resolve(cont.hierarchy, type_hint="W3DHierarchy")
            hier = w3x_xml.parse_hierarchy(hpath)
            arm_obj, bone_names = sb.build_armature(hier, collection=coll)
        except Exception as e:  # hierarchy optional for a bare view
            report(f"WARNING: could not import hierarchy '{cont.hierarchy}': {e}")

    n_mesh = n_box = 0
    for sub in cont.sub_objects:
        if sub.render_kind == "CollisionBox":
            if import_collision:
                sb.build_collision_box(sub, collection=coll)
                n_box += 1
            continue
        if not sub.render_name:
            continue
        try:
            mpath = resolver.resolve(sub.render_name, type_hint="W3DMesh")
            mesh = w3x_xml.parse_mesh(mpath)
            mobj = sb.build_mesh(mesh, collection=coll, bone_names=bone_names)
            if arm_obj is not None:
                sb.bind_mesh_to_armature(mobj, arm_obj, sub, bone_names)
            n_mesh += 1
        except Exception as e:
            report(f"WARNING: could not import mesh '{sub.render_name}': {e}")

    return (f"Imported W3DContainer '{cont.name}': {n_mesh} mesh(es), "
            f"{len(bone_names)} bone(s), {n_box} collision box(es).")


# --------------------------------------------------------------------------- #
# Blender operator + menu
# --------------------------------------------------------------------------- #

def _register_operator():
    import bpy
    from bpy.props import BoolProperty, StringProperty
    from bpy_extras.io_utils import ImportHelper

    class OPENWRATH_OT_import_model(bpy.types.Operator, ImportHelper):
        """Import a decompiled Kane's Wrath model (W3DContainer / Hierarchy / Mesh)"""
        bl_idname = "openwrath.import_model"
        bl_label = "Import OpenWrath Model"
        bl_options = {"REGISTER", "UNDO"}

        filename_ext = ".xml"
        filter_glob: StringProperty(default="*.xml", options={"HIDDEN"})

        import_collision: BoolProperty(
            name="Import collision boxes",
            description="Add collision boxes as wire empties (not render geometry)",
            default=True,
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

    def menu_func_import(self, context):
        self.layout.operator(OPENWRATH_OT_import_model.bl_idname,
                             text="OpenWrath Model (.xml)")

    return OPENWRATH_OT_import_model, menu_func_import


_classes = []
_menu_func = None


def register():
    import bpy
    global _classes, _menu_func
    op, _menu_func = _register_operator()
    _classes = [op]
    for c in _classes:
        bpy.utils.register_class(c)
    bpy.types.TOPBAR_MT_file_import.append(_menu_func)


def unregister():
    import bpy
    global _classes, _menu_func
    if _menu_func is not None:
        bpy.types.TOPBAR_MT_file_import.remove(_menu_func)
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
    _classes = []


if __name__ == "__main__":
    register()
