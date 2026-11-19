#!/usr/bin/env python3
"""compare-stream.py — external-oracle byte comparator for the OpenWrath toolchain.

Compare a freshly RECOMPILED split-form asset directory against the ORIGINAL bytes
of a compiled LINKED stream (EA's shipped data, or any mod's static_mod stream),
bucketed per TypeId. This answers: does our compiler losslessly reproduce real
shipped/mod bytes from the XML our decompiler emitted for that same stream?

Usage:
    compare-stream.py <recompiled-new-dir> <original-stream-manifest>
                      [--only NAME] [--type HEX]
                      [--bin PATH] [--relo PATH] [--imp PATH]
                      [--quiet]

  <recompiled-new-dir>        directory tree containing per-asset *.asset files
                              (BinaryAssetBuilder -od output; globbed recursively)
  <original-stream-manifest>  the linked stream's .manifest; its sibling .bin/.relo
                              /.imp (same basename) hold the original bytes unless
                              overridden with --bin/--relo/--imp. These siblings
                              must be DECOMPRESSED (RefPack-expanded) streams.
  --only NAME   compare only the asset whose instance name == NAME (the part after
                the last ':' in the manifest's "Type:Instance" name), matched
                case-insensitively — same selector bab-decompile --only uses.
  --type HEX    compare only assets whose TypeId == HEX (e.g. 942fff2d or 0x942fff2d).
  --bin/--relo/--imp PATH   explicit sub-stream paths (default: manifest siblings).
  --quiet       suppress per-asset detail lines; print bucket tallies only.

Stream layout (authoritative; see source/BinaryAssetBuilder.Decompiler/Containers/
Manifest.cs). The manifest stores SIZES, not offsets. Each sub-stream (.bin/.relo/
.imp) begins with a 4-byte prefix; asset i's bytes live at (4 + cumOffset) for
`size` bytes, where cumOffset is the running sum of all PRIOR entries' sizes.

Buckets (per TypeId and total):
  BYTEEXACT          inst+relo+imp all byte-identical to the original stream
  SIZEOK_VALDIFF     all three sizes match but some bytes differ
  SIZEDIFF           at least one size differs (prints ea-vs-new sizes + first diff)
  RECOMPILE-MISSING  no recompiled .asset found for this (TypeId, InstanceId)

Exit status: 0 if every compared asset is BYTEEXACT, else 1.
"""
import sys
import os
import struct
import glob
import argparse

HEADER_SIZE = 48   # 4 (flags/version) + 11 * 4
ENTRY_SIZE = 44    # 11 * uint32 (VERSION5)


def read_cstring(buf, off):
    if off is None or off < 0 or off >= len(buf):
        return None
    end = buf.find(b"\x00", off)
    if end < 0:
        end = len(buf)
    return buf[off:end].decode("ascii", "replace")


def parse_manifest(path):
    """Parse a v5 asset manifest into a list of per-asset dicts, in stream order.

    Each dict: idx, tid, iid, th, ih, ids (inst size), rds (relo size),
    imps (imp size), cb/cr/ci (cumulative bin/relo/imp offsets), name.
    """
    with open(path, "rb") as f:
        b = f.read()
    if b[0] != 0:
        raise SystemExit("compare-stream: big-endian (Xbox360) manifests unsupported")
    # header: flags/version word then 11 uint32; h[2]=AssetCount, h[7]=AssetRefBufSize,
    # h[8]=RefManifestNameBufSize, h[9]=AssetNameBufSize.
    h = struct.unpack_from("<11I", b, 4)
    n = h[2]
    asset_ref_buf_size = h[7]
    ref_man_name_buf_size = h[8]
    asset_name_buf_size = h[9]

    asset_ref_off = HEADER_SIZE + n * ENTRY_SIZE
    ref_man_name_off = asset_ref_off + asset_ref_buf_size
    asset_name_off = ref_man_name_off + ref_man_name_buf_size
    src_name_off = asset_name_off + asset_name_buf_size

    entries = []
    cb = cr = ci = 0
    for i in range(n):
        o = HEADER_SIZE + i * ENTRY_SIZE
        tid, iid, th, ih = struct.unpack_from("<4I", b, o + 0)
        name_offset = struct.unpack_from("<i", b, o + 24)[0]
        src_offset = struct.unpack_from("<i", b, o + 28)[0]
        ids, rds, imps = struct.unpack_from("<3I", b, o + 32)
        name = read_cstring(b, asset_name_off + name_offset) if name_offset >= 0 else None
        source = read_cstring(b, src_name_off + src_offset) if src_offset >= 0 else None
        entries.append({
            "idx": i, "tid": tid, "iid": iid, "th": th, "ih": ih,
            "ids": ids, "rds": rds, "imps": imps,
            "cb": cb, "cr": cr, "ci": ci,
            "name": name, "source": source,
        })
        cb += ids
        cr += rds
        ci += imps
    return entries


def sibling(manifest_path, ext):
    base = manifest_path
    if base.lower().endswith(".manifest"):
        base = base[: -len(".manifest")]
    return base + ext


def index_newdir(d):
    """Map (TypeId, InstanceId) -> recompiled .asset path, from filenames
    `{tid:08x}.{th:08x}.{iid:08x}.{ih:08x}.asset` (TypeHash/InstanceHash wildcarded)."""
    idx = {}
    for p in glob.glob(os.path.join(d, "**", "*.asset"), recursive=True):
        parts = os.path.basename(p).split(".")
        if len(parts) != 5 or parts[4] != "asset":
            continue
        try:
            tid = int(parts[0], 16)
            iid = int(parts[2], 16)
        except ValueError:
            continue
        idx[(tid, iid)] = p
    return idx


def read_asset(path):
    """Return (inst, relo, imp, (ids, rds, imps)) from a 32B-header .asset file."""
    with open(path, "rb") as f:
        d = f.read()
    h = struct.unpack_from("<8I", d, 0)  # tid, inst, th, ih, ids, rds, imps, pad
    ids, rds, imps = h[4], h[5], h[6]
    o = 32
    return d[o:o + ids], d[o + ids:o + ids + rds], d[o + ids + rds:o + ids + rds + imps], (ids, rds, imps)


def first_diff(a, b):
    for j in range(min(len(a), len(b))):
        if a[j] != b[j]:
            return j
    return min(len(a), len(b)) if len(a) != len(b) else -1


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("newdir")
    ap.add_argument("manifest")
    ap.add_argument("--only", default=None)
    ap.add_argument("--type", dest="typ", default=None)
    ap.add_argument("--bin", dest="binp", default=None)
    ap.add_argument("--relo", dest="relop", default=None)
    ap.add_argument("--imp", dest="impp", default=None)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    type_filter = None
    if a.typ is not None:
        type_filter = int(a.typ, 16)

    entries = parse_manifest(a.manifest)
    binp = a.binp or sibling(a.manifest, ".bin")
    relop = a.relop or sibling(a.manifest, ".relo")
    impp = a.impp or sibling(a.manifest, ".imp")
    for p in (binp, relop, impp):
        if not os.path.exists(p):
            raise SystemExit(f"compare-stream: missing stream file {p}")

    newidx = index_newdir(a.newdir)

    # Bucket tallies per TypeId and overall.
    BUCKETS = ("BYTEEXACT", "SIZEOK_VALDIFF", "SIZEDIFF", "RECOMPILE-MISSING")
    per_type = {}
    totals = {k: 0 for k in BUCKETS}

    def tally(tid, bucket):
        totals[bucket] += 1
        d = per_type.setdefault(tid, {k: 0 for k in BUCKETS})
        d[bucket] += 1

    binf = open(binp, "rb")
    relof = open(relop, "rb")
    impf = open(impp, "rb")
    compared = 0
    try:
        for e in entries:
            if type_filter is not None and e["tid"] != type_filter:
                continue
            if a.only is not None:
                inst_name = (e["name"] or "").split(":")[-1]
                if inst_name.lower() != a.only.lower():
                    continue
            compared += 1
            label = e["name"] or f"{e['tid']:08x}:{e['iid']:08x}"

            binf.seek(4 + e["cb"]); ea_inst = binf.read(e["ids"])
            relof.seek(4 + e["cr"]); ea_relo = relof.read(e["rds"])
            impf.seek(4 + e["ci"]); ea_imp = impf.read(e["imps"])

            np = newidx.get((e["tid"], e["iid"]))
            if np is None:
                tally(e["tid"], "RECOMPILE-MISSING")
                if not a.quiet:
                    print(f"  RECOMPILE-MISSING  {label}  (ea inst={e['ids']} relo={e['rds']} imp={e['imps']})")
                continue

            n_inst, n_relo, n_imp, (nids, nrds, nimps) = read_asset(np)
            size_ok = (nids == e["ids"] and nrds == e["rds"] and nimps == e["imps"])
            byte_ok = (n_inst == ea_inst and n_relo == ea_relo and n_imp == ea_imp)

            if byte_ok:
                tally(e["tid"], "BYTEEXACT")
                if not a.quiet:
                    print(f"  BYTEEXACT          {label}")
            elif size_ok:
                tally(e["tid"], "SIZEOK_VALDIFF")
                if not a.quiet:
                    det = f"inst={e['ids']}"
                    if n_inst != ea_inst:
                        det += f" | inst fd@{first_diff(ea_inst, n_inst)}"
                    if n_relo != ea_relo:
                        det += f" | relo fd@{first_diff(ea_relo, n_relo)}"
                    if n_imp != ea_imp:
                        det += f" | imp fd@{first_diff(ea_imp, n_imp)}"
                    print(f"  SIZEOK_VALDIFF     {label}  {det}")
            else:
                tally(e["tid"], "SIZEDIFF")
                if not a.quiet:
                    det = (f"inst ea={e['ids']}/new={nids} "
                           f"relo ea={e['rds']}/new={nrds} "
                           f"imp ea={e['imps']}/new={nimps}")
                    if n_inst != ea_inst:
                        det += f" | inst fd@{first_diff(ea_inst, n_inst)}"
                    if n_relo != ea_relo:
                        det += f" | relo fd@{first_diff(ea_relo, n_relo)}"
                    if n_imp != ea_imp:
                        det += f" | imp fd@{first_diff(ea_imp, n_imp)}"
                    print(f"  SIZEDIFF           {label}  {det}")
    finally:
        binf.close(); relof.close(); impf.close()

    print("---- per-type buckets (TypeId: exact/sizeok/sizediff/missing) ----")
    for tid in sorted(per_type, key=lambda t: -sum(per_type[t].values())):
        d = per_type[tid]
        print(f"  0x{tid:08x}  exact={d['BYTEEXACT']}  sizeok_valdiff={d['SIZEOK_VALDIFF']}"
              f"  sizediff={d['SIZEDIFF']}  missing={d['RECOMPILE-MISSING']}")
    print("---- totals ----")
    print(f"  compared={compared}  BYTEEXACT={totals['BYTEEXACT']}"
          f"  SIZEOK_VALDIFF={totals['SIZEOK_VALDIFF']}"
          f"  SIZEDIFF={totals['SIZEDIFF']}"
          f"  RECOMPILE-MISSING={totals['RECOMPILE-MISSING']}")

    if compared == 0:
        raise SystemExit("compare-stream: no assets matched the filter")
    sys.exit(0 if totals["BYTEEXACT"] == compared else 1)


if __name__ == "__main__":
    main()
