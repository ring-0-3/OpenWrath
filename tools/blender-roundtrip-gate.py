#!/usr/bin/env python3
"""blender-roundtrip-gate.py — selection + job-building for the Blender exporter round-trip
gate (finding 0028). Driven by tools/blender-roundtrip-gate.sh.

This is the 0025 re-pack gate WITH BLENDER IN THE LOOP. It deliberately REUSES, never
reimplements, the existing oracle machinery (CLAUDE.md invariant 3):

  * tools/mesh-repack-gate.py  — its `select` (stratified, seeded, every vertex-declaration
    layout forced in) and `compare` (byte-bucketed vs the shipped stream) are imported and
    called as-is. The gate does not re-draw the sample or re-write the comparator.
  * tools/compare-stream.py    — the single source of truth for the stream format (used by
    the above, and by the shell for the graph types via `compare-stream.py --type`).

Verbs:
  select-mesh   stdout = the stratified mesh sample (delegates to mesh-repack-gate.select).
  select-type   stdout = a reproducible seeded sample of a graph type's decoded XML files
                (env DECDIR/STREAM_MF/TID/SAMPLE/SEED).
  make-jobs     write the Blender import-save and load-export job files (env SAMPLE_LIST/
                DECDIR/BLENDDIR/EXPDIR/IMP_JSON/EXP_JSON/COLLISION).
  compare-mesh  delegates to mesh-repack-gate.compare (byte-compare recompiled-from-export
                to the shipped stream).
"""
import os
import sys
import json
import random
import importlib.util

_here = os.path.dirname(os.path.abspath(__file__))


def _load(modname, filename):
    spec = importlib.util.spec_from_file_location(modname, os.path.join(_here, filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mrg = _load("mesh_repack_gate", "mesh-repack-gate.py")   # reuse select/compare
cs = _load("compare_stream", "compare-stream.py")         # manifest parser / stream format


def _type_and_id(dec_filename):
    """`W3DMesh.NUREDEEMER_SKN.FX_LAZERGLOW.xml` -> ("W3DMesh", "NUREDEEMER_SKN.FX_LAZERGLOW")."""
    base = dec_filename[:-4] if dec_filename.endswith(".xml") else dec_filename
    atype, _, aid = base.partition(".")
    return atype, aid


def type_tid():
    """Print the TypeId (hex, no 0x) of a type NAME, derived from the stream manifest — so
    the gate never hardcodes a TypeId (env STREAM_MF/TNAME). The manifest is the single
    source of truth for the (TypeName -> TypeId) mapping (CLAUDE.md invariant 3)."""
    stream_mf = os.environ["STREAM_MF"]
    tname = os.environ["TNAME"]
    for e in cs.parse_manifest(stream_mf):
        nm = e["name"] or ""
        if nm.split(":")[0] == tname:
            print(f"{e['tid']:08x}")
            return
    sys.stderr.write(f"      WARN: no instance of type '{tname}' in the stream\n")
    sys.exit(3)


def select_type():
    """A reproducible seeded sample of one graph type's decoded files (no stratification
    needed — these are plain structural types)."""
    decdir = os.environ["DECDIR"]
    stream_mf = os.environ["STREAM_MF"]
    tid = int(os.environ["TID"], 16)
    sample = int(os.environ.get("SAMPLE", "40"))
    seed = int(os.environ.get("SEED", "42"))
    do_all = os.environ.get("ALL", "0") == "1"

    ents = [e for e in cs.parse_manifest(stream_mf) if e["tid"] == tid and e["name"]]
    usable = []
    for e in ents:
        fn = e["name"].replace(":", ".") + ".xml"
        if os.path.exists(os.path.join(decdir, fn)):
            usable.append(fn)
    usable = sorted(set(usable))
    if do_all:
        chosen = usable
    else:
        rng = random.Random(seed)
        rng.shuffle(usable)
        chosen = sorted(usable[:sample])
    sys.stderr.write(f"      corpus: {len(usable)} decoded {os.environ.get('TNAME', hex(tid))}\n")
    for fn in chosen:
        print(fn)


def make_jobs():
    """Build the import-save + load-export job lists from a sample file list."""
    sample_list = os.environ["SAMPLE_LIST"]
    decdir = os.environ["DECDIR"]
    blenddir = os.environ["BLENDDIR"]
    expdir = os.environ["EXPDIR"]
    collision = os.environ.get("COLLISION", "0") == "1"

    with open(sample_list) as f:
        files = [ln.strip() for ln in f if ln.strip()]

    imp, exp = [], []
    for fn in files:
        atype, aid = _type_and_id(fn)
        inx = os.path.join(decdir, fn)
        blend = os.path.join(blenddir, fn[:-4] + ".blend")
        outx = os.path.join(expdir, fn)
        imp.append({"in": inx, "blend": blend, "collision": collision})
        exp.append({"blend": blend, "out": outx, "asset_id": aid, "asset_type": atype})

    with open(os.environ["IMP_JSON"], "w") as f:
        json.dump(imp, f)
    with open(os.environ["EXP_JSON"], "w") as f:
        json.dump(exp, f)
    sys.stderr.write(f"      built {len(imp)} import + {len(exp)} export job(s)\n")


def compare_selected():
    """Byte-compare ONLY the sampled instances' recompiled bytes to the shipped stream,
    bucketed honestly (env NEWDIR/SAMPLE_LIST/STREAM_MF). Used for the graph types.

    Reuses tools/compare-stream.py's manifest parser / stream loader / .asset reader (the
    single source of truth for the stream format) — it does NOT re-derive any of it, and it
    restricts the comparison to the sample (so the thousands of un-sampled same-type
    instances are not miscounted as RECOMPILE-MISSING; compare-stream.py --type compares the
    whole type)."""
    newdir = os.environ["NEWDIR"]
    sample_list = os.environ["SAMPLE_LIST"]
    stream_mf = os.environ["STREAM_MF"]

    with open(sample_list) as f:
        selected = [ln.strip() for ln in f if ln.strip()]

    # dec filename "Type.Instance.xml" -> manifest name "Type:Instance"
    by_name = {e["name"]: e for e in cs.parse_manifest(stream_mf) if e["name"]}
    binb = open(cs.sibling(stream_mf, ".bin"), "rb").read()
    relob = open(cs.sibling(stream_mf, ".relo"), "rb").read()
    impb = open(cs.sibling(stream_mf, ".imp"), "rb").read()
    newidx = cs.index_newdir(newdir)

    buckets = {"BYTEEXACT": [], "SIZEOK_VALDIFF": [], "SIZEDIFF": [], "RECOMPILE-MISSING": []}
    for fn in selected:
        atype, _, aid = (fn[:-4] if fn.endswith(".xml") else fn).partition(".")
        e = by_name.get(f"{atype}:{aid}")
        if e is None:
            buckets["RECOMPILE-MISSING"].append((fn, "not in manifest"))
            continue
        key = (e["tid"], e["iid"])
        if key not in newidx:
            buckets["RECOMPILE-MISSING"].append((fn, "no recompiled .asset"))
            continue
        ri, rr, rm_, _ = cs.read_asset(newidx[key])
        oi = binb[4 + e["cb"]: 4 + e["cb"] + e["ids"]]
        orl = relob[4 + e["cr"]: 4 + e["cr"] + e["rds"]]
        oim = impb[4 + e["ci"]: 4 + e["ci"] + e["imps"]]
        if (oi, orl, oim) == (ri, rr, rm_):
            buckets["BYTEEXACT"].append((fn, ""))
        elif len(oi) == len(ri) and len(orl) == len(rr) and len(oim) == len(rm_):
            buckets["SIZEOK_VALDIFF"].append((fn, "same size, bytes differ"))
        else:
            buckets["SIZEDIFF"].append(
                (fn, f"sizes ea(i{len(oi)} r{len(orl)} m{len(oim)}) new(i{len(ri)} r{len(rr)} m{len(rm_)})"))

    total = sum(len(v) for v in buckets.values())
    print(f"  compared={total}")
    for b in ("BYTEEXACT", "SIZEOK_VALDIFF", "SIZEDIFF", "RECOMPILE-MISSING"):
        print(f"    {b:18s} {len(buckets[b])}")
        for fn, why in buckets[b][:25]:
            if b != "BYTEEXACT":
                print(f"      {b}: {fn}  {why}")
    ok = (len(buckets["BYTEEXACT"]) == total and total > 0)
    print("  VERDICT:", "GREEN" if ok else "RED")
    return 0 if ok else 1


if __name__ == "__main__":
    verb = sys.argv[1] if len(sys.argv) > 1 else ""
    if verb == "type-tid":
        type_tid()
    elif verb == "select-mesh":
        mrg.select()
    elif verb == "select-type":
        select_type()
    elif verb == "make-jobs":
        make_jobs()
    elif verb == "compare-mesh":
        sys.exit(mrg.compare())
    elif verb == "compare-selected":
        sys.exit(compare_selected())
    else:
        sys.exit("usage: blender-roundtrip-gate.py "
                 "<type-tid|select-mesh|select-type|make-jobs|compare-mesh|compare-selected>")
