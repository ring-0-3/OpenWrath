#!/usr/bin/env python3
# Build ONE proper BAB-style SPARSE differential overlay stream (finding 0017 — the verified recipe for a
# loadable mod that overrides base KW gameplay on retail 1.3).
#
# Given a BASE stream (e.g. static_common_2 extracted from the recipient's own Core/1.2/patch2.big) and the
# user's compiled override .asset(s), produce an overlay that:
#   - carries the COMPLETE entry list of the base (every asset), with INSTANCE DATA only for the edited
#     asset(s); every other entry is DEFERRED (zero-size) and resolved from the base at load,
#   - retargets the RefManNameBuffer base-reference to `\x02<base_ref_name>\x00` (ONLY the \x02 record; the
#     base's \x01 ref-manifest records are stripped, matching the working "Kane's Wrath Classic" overlay),
#   - KEEPS the base's Max{Binary,Relocation,Imports}ChunkSize header (hdr[4..6]) — NOT recomputed from the
#     sparse entries: the engine sizes its per-asset load buffer from these and must fit the largest chunk it
#     reads from the DEFERRED base (~1.4MB); recomputing to our tiny data under-allocates and crashes at load,
#   - stamps a unique, content-derived StreamChecksum (hdr[0] + the 4-byte prefix of .bin/.relo/.imp).
#
# Activation (NOT done here — see finding 0017 / the mod-package command): ship this stream + its low-LOD twin
# (`<fam>_l_mod`, all-deferred, \x02 -> `<fam>_mod.manifest`, hdr[3] = the high-LOD's) + the WorldBuilder
# companion (`worldbuilder_mod`, all-deferred, \x02 -> `worldbuilder_2.manifest`), plus the THREE `.version`
# redirect files (`data\static.version`, `data\static_l.version`, `data\worldbuilder.version`, each = b"_mod\n").
#
# usage: build_overlay.py <base_prefix> <asset1.asset[,asset2.asset,...] | NONE> <base_ref_name> <out_dir> <out_stem>
#   <base_prefix> resolves <base_prefix>.{manifest,bin,relo,imp} (may be RefPack-compressed).
#   NONE  -> an all-deferred shell (for the low-LOD twin / worldbuilder companion).
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refpack, retag_checksum

EO, ES = 48, 44   # v5 linked-manifest header size, entry size


def _load(p):
    d = open(p, "rb").read()
    return refpack.decompress(d)[0] if refpack.is_refpack(d) else d


def main():
    base_prefix, assets_arg, base_ref_name, out_dir, out_stem = sys.argv[1:6]
    man = bytearray(_load(base_prefix + ".manifest"))
    binf = _load(base_prefix + ".bin"); relof = _load(base_prefix + ".relo"); impf = _load(base_prefix + ".imp")
    hdr = list(struct.unpack_from("<11I", man, 4)); ac = hdr[2]
    arsz, rmsz, ansz, snsz = hdr[7], hdr[8], hdr[9], hdr[10]
    E = [list(struct.unpack_from("<4I7i", man, EO + i * ES)) for i in range(ac)]

    def slices(buf, idx):
        off = 4; out = []
        for e in E:
            out.append(buf[off:off + e[idx]]); off += e[idx]
        return out
    binC = slices(binf, 8); reloC = slices(relof, 9); impC = slices(impf, 10)

    # load the edited asset(s); key each by its own (TypeId,InstanceId) from the .asset header
    # (.asset = 32B header: tid,iid,th,ih,instSize,reloSize,impSize,zero  then inst+relo+imp).
    edits = {}
    if assets_arg != "NONE":
        for path in assets_arg.split(","):
            a = open(path, "rb").read()
            at, ai, ath, aih, aids, ards, aimps, _z = struct.unpack_from("<8I", a, 0)
            edits[(at, ai)] = (aih, a[32:32 + aids], a[32 + aids:32 + aids + ards], a[32 + aids + ards:])

    # DEFER every entry; splice real data for the edited ones.
    spliced = 0
    for i, e in enumerate(E):
        key = (e[0], e[1])
        if key in edits:
            aih, inst, relo, imp = edits[key]
            e[3] = aih; e[8] = len(inst); e[9] = len(relo); e[10] = len(imp)
            binC[i] = inst; reloC[i] = relo; impC[i] = imp
            spliced += 1
        else:
            e[8] = e[9] = e[10] = 0
            binC[i] = reloC[i] = impC[i] = b""
    missing = set(edits) - {(e[0], e[1]) for e in E}
    if missing:
        sys.exit(f"error: edited asset(s) not present in base {base_prefix}: "
                 + ", ".join(f"0x{t:08x}:0x{i:08x}" for t, i in missing))

    # Keep AssetRefBuf + Asset/SourceName buffers verbatim (refs are absolute (tid,iid); names unchanged).
    aro = EO + ac * ES
    refbuf = man[aro:aro + arsz]
    namebufs = man[aro + arsz + rmsz:]                               # assetNameBuf + srcNameBuf
    assert len(namebufs) == ansz + snsz, (len(namebufs), ansz + snsz)
    new_refman = b"\x02" + base_ref_name.encode("ascii") + b"\x00"   # ONLY the \x02 base-ref (strip \x01 records)

    hdr[3] = sum(e[8] for e in E)                                    # TotalInstanceDataSize = OUR own data
    # hdr[4..6] (max chunk sizes): KEEP the base's values (do NOT recompute) — the load-buffer sizing fix.
    hdr[8] = len(new_refman)

    entry_block = b"".join(struct.pack("<4I7i", e[0] & 0xffffffff, e[1] & 0xffffffff, e[2] & 0xffffffff,
                                       e[3] & 0xffffffff, e[4], e[5], e[6], e[7], e[8], e[9], e[10]) for e in E)
    tmp = bytearray(man[0:4]) + struct.pack("<11I", *[h & 0xffffffff for h in hdr]) + entry_block
    checksum = retag_checksum.compute_checksum(bytes(tmp))
    hdr[0] = checksum
    prefix = struct.pack("<I", checksum)

    out = bytearray(man[0:4]) + struct.pack("<11I", *[h & 0xffffffff for h in hdr]) + entry_block
    out += refbuf + new_refman + namebufs

    os.makedirs(out_dir, exist_ok=True)
    open(os.path.join(out_dir, out_stem + ".manifest"), "wb").write(out)
    open(os.path.join(out_dir, out_stem + ".bin"), "wb").write(prefix + b"".join(binC))
    open(os.path.join(out_dir, out_stem + ".relo"), "wb").write(prefix + b"".join(reloC))
    open(os.path.join(out_dir, out_stem + ".imp"), "wb").write(prefix + b"".join(impC))
    print(f"built {out_stem}: {ac} entries, {spliced} with data (deferred: {ac - spliced}); "
          f"base-ref=\\x02{base_ref_name}  StreamChecksum=0x{checksum:08x}  maxchunk(hdr[4..6])={tuple(hdr[4:7])}")


if __name__ == "__main__":
    main()
