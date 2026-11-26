"""blender_roundtrip_driver.py — run INSIDE Blender for the exporter round-trip gate.

    blender --background --python tools/blender_roundtrip_driver.py -- import-save <jobs.json>
    blender --background --python tools/blender_roundtrip_driver.py -- load-export <jobs.json>

The gate (tools/blender-roundtrip-gate.sh) runs these as TWO SEPARATE Blender processes so
the export process only ever sees the saved .blend files — never the decoded XML. That is
the anti-bypass property the gate rests on: a green proves Blender's own datablocks (saved
and reloaded) carried every authoring attribute, because that is the only channel between
import and export (docs/design/blender-integration.md, staging step 3).

  import-save  jobs = [{"in": decoded.xml, "blend": out.blend, "collision": bool}, ...]
               reset scene -> openwrath_import.import_file(in) -> save .blend.
  load-export  jobs = [{"blend": in.blend, "out": out.xml,
                        "asset_id": id, "asset_type": type}, ...]
               open .blend (a genuine reload) -> openwrath_import.export_file(out, ...).

Reuses the add-on's import_file / export_file (the one import/export path) — no second
copy of any scene<->XML logic.
"""
import json
import os
import sys

import bpy

# Make the add-on importable exactly as the tests do (blender/ on sys.path).
_HERE = os.path.dirname(os.path.abspath(__file__))
_ADDON_ROOT = os.path.join(os.path.dirname(_HERE), "blender")
sys.path.insert(0, _ADDON_ROOT)

import openwrath_import  # noqa: E402


def _argv_after_ddash():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def _reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_save(jobs):
    ok = 0
    for j in jobs:
        _reset()
        base_dir = os.path.dirname(os.path.abspath(j["in"]))
        resolver = openwrath_import.AssetResolver(base_dir)
        summary = openwrath_import.import_file(
            j["in"], resolver=resolver,
            import_collision=bool(j.get("collision", False)),
            report=lambda m: None,
        )
        # A real on-disk save; the export pass will open this file in a fresh process.
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(j["blend"]))
        print(f"  import-save: {os.path.basename(j['in'])} -> {os.path.basename(j['blend'])}  [{summary}]")
        ok += 1
    print(f"import-save done: {ok}/{len(jobs)}")


def load_export(jobs):
    ok = 0
    tiers = {}
    for j in jobs:
        bpy.ops.wm.open_mainfile(filepath=os.path.abspath(j["blend"]))  # genuine reload
        summary = openwrath_import.export_file(
            j["out"], asset_id=j.get("asset_id"), asset_type=j.get("asset_type"),
            report=lambda m: None,
        )
        tier = "stated" if "[stated]" in summary else ("byte-exact" if "[byte-exact]" in summary else "?")
        tiers[tier] = tiers.get(tier, 0) + 1
        print(f"  load-export: {os.path.basename(j['blend'])} -> {os.path.basename(j['out'])}  [{summary}]")
        ok += 1
    print(f"load-export done: {ok}/{len(jobs)}  tiers={tiers}")


def load_export_all(jobs):
    """Full-model export: open each .blend and write EVERY stashed asset to a directory
    (import a container → reload → export the whole model). jobs = [{"blend":, "outdir":}]."""
    for j in jobs:
        bpy.ops.wm.open_mainfile(filepath=os.path.abspath(j["blend"]))
        os.makedirs(j["outdir"], exist_ok=True)
        n, results = openwrath_import.export_all(j["outdir"], report=lambda m: None)
        tiers = {}
        for _ty, _id, tier in results:
            tiers[tier] = tiers.get(tier, 0) + 1
        print(f"  export-all: {os.path.basename(j['blend'])} -> {n} asset(s)  tiers={tiers}")


def main():
    args = _argv_after_ddash()
    if len(args) < 2:
        print("usage: ... -- <import-save|load-export> <jobs.json>")
        return 2
    mode, jobs_path = args[0], args[1]
    with open(jobs_path) as f:
        jobs = json.load(f)
    if mode == "import-save":
        import_save(jobs)
    elif mode == "load-export":
        load_export(jobs)
    elif mode == "load-export-all":
        load_export_all(jobs)
    else:
        print(f"unknown mode '{mode}'")
        return 2
    return 0


if __name__ == "__main__":
    rc = main()
    sys.stdout.flush()
    os._exit(rc)
