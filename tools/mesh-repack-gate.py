#!/usr/bin/env python3
"""mesh-repack-gate.py — selection + comparison engine for the W3DMesh re-pack equality gate.

Driven by tools/mesh-repack-gate.sh (which does the dotnet decompile/compile). Two verbs:

  select   stdout = one decompiled-XML filename per line — a REPRODUCIBLE, STRATIFIED sample of the corpus:
           every distinct vertex-declaration LAYOUT forced in (coverage of the weird on purpose), then a
           seeded-random fill up to --sample (env SAMPLE/SEED/ALL/DECDIR/STREAM_MF).
  compare  byte-compares each selected mesh's recompiled bytes to the shipped stream and prints honest buckets
           + an exercised-vs-unexercised packer-path matrix (env NEWDIR/DECDIR/SAMPLE_LIST/STREAM_MF).

Reuses tools/compare-stream.py's manifest parser / stream loader (single source of truth for the stream format;
CLAUDE.md invariant 3). The stream is bring-your-own; .bin/.relo/.imp siblings must be decompressed.
"""
import os
import sys
import glob
import struct
import random
import importlib.util
import xml.etree.ElementTree as ET

NS = "{uri:ea.com:eala:asset}"
MESH_TID = 0xC2B1A262

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("compare_stream", os.path.join(_here, "compare-stream.py"))
cs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cs)


def dec_filename(qualified_name):
    """Manifest qualified name 'W3DMesh:INSTANCE' -> the decompile-stream output filename."""
    return qualified_name.replace(":", ".") + ".xml"


def mesh_entries(stream_mf):
    return [e for e in cs.parse_manifest(stream_mf) if e["tid"] == MESH_TID and e["name"]]


def parse_layout(path):
    """Structural signature of a semantic mesh XML (None if it is a <RawAsset> or unparsable).
    Captures exactly the variety that drives distinct packer code paths."""
    try:
        root = ET.parse(path).getroot()
    except Exception:
        return None
    if root.find(f"{NS}RawAsset") is not None or root.tag == f"{NS}RawAsset":
        return None
    mesh = root.find(f"{NS}W3DMesh")
    if mesh is None:
        return None
    def n(tag):
        return len(mesh.findall(f"{NS}{tag}"))
    tex = n("TexCoords")
    return {
        "pos": n("Vertices"),
        "norm": n("Normals"),
        "tan": n("Tangents"),
        "bin": n("Binormals"),
        "col": n("VertexColors"),       # present only when some vertex is non-white
        "tex": tex,
        "bone": n("BoneInfluences"),
    }


def sig_key(lay):
    return (lay["pos"], lay["norm"], lay["tan"], lay["bin"], lay["col"], lay["tex"], lay["bone"])


def select():
    decdir = os.environ["DECDIR"]
    stream_mf = os.environ["STREAM_MF"]
    sample = int(os.environ.get("SAMPLE", "300"))
    seed = int(os.environ.get("SEED", "42"))
    do_all = os.environ.get("ALL", "0") == "1"

    ents = mesh_entries(stream_mf)
    # name -> dec filename (only those that actually produced a semantically-decoded XML)
    usable = []
    groups = {}
    raw = 0
    for e in ents:
        fn = dec_filename(e["name"])
        p = os.path.join(decdir, fn)
        if not os.path.exists(p):
            continue
        lay = parse_layout(p)
        if lay is None:
            raw += 1
            continue
        usable.append(fn)
        groups.setdefault(sig_key(lay), []).append(fn)

    if do_all:
        chosen = sorted(usable)
    else:
        rng = random.Random(seed)
        forced = set()
        # one deterministic representative per distinct layout (coverage of the weird, invariant / blind-spot §1)
        for k in sorted(groups):
            forced.add(sorted(groups[k])[0])
        pool = sorted(set(usable) - forced)
        rng.shuffle(pool)
        need = max(0, sample - len(forced))
        chosen = sorted(forced) + pool[:need]
        chosen = sorted(set(chosen))

    sys.stderr.write(f"      corpus: {len(usable)} decodable, {raw} raw-fallback, {len(groups)} distinct layouts\n")
    for fn in chosen:
        print(fn)


def compare():
    newdir = os.environ["NEWDIR"]
    decdir = os.environ["DECDIR"]
    sample_list = os.environ["SAMPLE_LIST"]
    stream_mf = os.environ["STREAM_MF"]

    with open(sample_list) as f:
        selected = [ln.strip() for ln in f if ln.strip()]
    sel_set = set(selected)

    ents = mesh_entries(stream_mf)
    by_file = {dec_filename(e["name"]): e for e in ents}

    binb = open(cs.sibling(stream_mf, ".bin"), "rb").read()
    relob = open(cs.sibling(stream_mf, ".relo"), "rb").read()
    impb = open(cs.sibling(stream_mf, ".imp"), "rb").read()
    newidx = cs.index_newdir(newdir)

    buckets = {"BYTEEXACT": [], "SIZEOK_VALDIFF": [], "SIZEDIFF": [], "RECOMPILE-MISSING": [], "RAW-FALLBACK": []}
    # exercised-path tallies, from the SELECTED meshes' layouts (honest: what the sample actually hit)
    paths = {"single_pos": 0, "double_pos": 0, "tangent_binormal": 0, "tex0": 0, "tex1": 0, "tex2plus": 0,
             "nonwhite_color": 0, "rigid_1bone": 0, "skinned_2bone": 0, "no_bones": 0}

    for fn in selected:
        e = by_file.get(fn)
        if e is None:
            continue
        lay = parse_layout(os.path.join(decdir, fn))
        if lay is None:
            buckets["RAW-FALLBACK"].append((fn, "semantic decode produced <RawAsset>"))
            continue
        # tally exercised paths
        paths["double_pos" if lay["pos"] >= 2 else "single_pos"] += 1
        if lay["tan"] and lay["bin"]:
            paths["tangent_binormal"] += 1
        paths["tex0" if lay["tex"] == 0 else ("tex1" if lay["tex"] == 1 else "tex2plus")] += 1
        if lay["col"]:
            paths["nonwhite_color"] += 1
        if lay["bone"] == 0:
            paths["no_bones"] += 1
        elif lay["bone"] >= 2:
            paths["skinned_2bone"] += 1
        else:
            paths["rigid_1bone"] += 1

        key = (e["tid"], e["iid"])
        if key not in newidx:
            buckets["RECOMPILE-MISSING"].append((fn, "no recompiled .asset"))
            continue
        ri, rr, rm_, _ = cs.read_asset(newidx[key])  # inst, relo, imp bytes (recompiled)
        oi = binb[4 + e["cb"]: 4 + e["cb"] + e["ids"]]
        orl = relob[4 + e["cr"]: 4 + e["cr"] + e["rds"]]
        oim = impb[4 + e["ci"]: 4 + e["ci"] + e["imps"]]
        if (oi, orl, oim) == (ri, rr, rm_):
            buckets["BYTEEXACT"].append((fn, ""))
        elif len(oi) == len(ri) and len(orl) == len(rr) and len(oim) == len(rm_):
            why = _first_diff(oi, ri, "inst") or _first_diff(orl, rr, "relo") or _first_diff(oim, rm_, "imp")
            buckets["SIZEOK_VALDIFF"].append((fn, why))
        else:
            why = f"sizes ea(i{len(oi)} r{len(orl)} m{len(oim)}) new(i{len(ri)} r{len(rr)} m{len(rm_)})"
            buckets["SIZEDIFF"].append((fn, why))

    total = sum(len(v) for v in buckets.values())
    print("\n==================== RE-PACK EQUALITY GATE — RESULTS ====================")
    print(f"  compared={total}")
    for b in ("BYTEEXACT", "SIZEOK_VALDIFF", "SIZEDIFF", "RAW-FALLBACK", "RECOMPILE-MISSING"):
        print(f"    {b:18s} {len(buckets[b])}")
    for b in ("SIZEOK_VALDIFF", "SIZEDIFF", "RAW-FALLBACK", "RECOMPILE-MISSING"):
        for fn, why in buckets[b][:25]:
            print(f"      {b}: {fn}  {why}")

    print("\n  ---- packer paths EXERCISED by this sample (honest coverage) ----")
    print(f"    single position channel (1 vertex/vert) : {paths['single_pos']}")
    print(f"    double position channel (2-bone skin)   : {paths['double_pos']}")
    print(f"    tangent+binormal present                : {paths['tangent_binormal']}")
    print(f"    texcoords 0 / 1 / 2+                     : {paths['tex0']} / {paths['tex1']} / {paths['tex2plus']}")
    print(f"    non-white vertex colours (D3DCOLOR pack): {paths['nonwhite_color']}")
    print(f"    bones: none / rigid-1 / skinned-2(FLOAT2 weights): {paths['no_bones']} / {paths['rigid_1bone']} / {paths['skinned_2bone']}")
    print("\n  ---- packer paths NOT exercised (no shipped sample hits them; remain UNVERIFIED) ----")
    print("    half-float TexCoord/Normal (CompressTexCoord/Vector3ToHalf4/FloatToHalf): decl type never FLOAT16_* in sample")
    print("    Xenon/big-endian declaration (BuildVertexDeclaration_Xenon, throws)    : stream is little-endian")
    print("    CompressNormalizedDirection (sbyte DEC3N normals)                       : Windows packer copies FLOAT3 direct")
    print("    >2 blend weights (FLOAT3/FLOAT4 BLENDWEIGHT)                             : corpus max is 2 (FLOAT2)")
    print("    zero-vertex / null VertexData pointer                                   : 0 of corpus (defensive only)")

    ok = (len(buckets["SIZEOK_VALDIFF"]) == 0 and len(buckets["SIZEDIFF"]) == 0 and
          len(buckets["RAW-FALLBACK"]) == 0 and len(buckets["RECOMPILE-MISSING"]) == 0 and
          len(buckets["BYTEEXACT"]) == total and total > 0)
    print("\n  VERDICT:", "GREEN — decode∘packer byte-exact on the sample" if ok else "RED — see mismatches above")
    print("========================================================================")
    return 0 if ok else 1


def _first_diff(a, b, label):
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return f"{label} first-diff@{i} ea=0x{a[i]:02x} new=0x{b[i]:02x}"
    return None


if __name__ == "__main__":
    verb = sys.argv[1] if len(sys.argv) > 1 else ""
    if verb == "select":
        select()
    elif verb == "compare":
        sys.exit(compare())
    else:
        sys.exit("usage: mesh-repack-gate.py <select|compare>  (configured via environment; see mesh-repack-gate.sh)")
