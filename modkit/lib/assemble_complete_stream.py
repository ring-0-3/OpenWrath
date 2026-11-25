#!/usr/bin/env python3
# Assemble a COMPLETE linked static stream from the base + overlay CHAIN (finding 0016).
#
# The retail static family loads as base + overlay chain: the top overlay (the patch's Static_mod) carries a
# COMPLETE entry list (every asset, version-current TypeHashes) but INSTANCE DATA only for what it changed
# (~98% of entries are zero-size, deferred to the base by (TypeId,InstanceId)). A standalone MOD cannot defer
# that way — its static_mod must be COMPLETE (every asset real-data) so each asset's imports resolve to a
# real, local target. This tool reconstructs exactly what the engine loads at runtime: it takes the patch's
# manifest as the authoritative 1.3 entry list (names + per-type hashes + refs) and FILLS every deferred
# (zero-size) entry with its real instance/relo/imp bytes from the highest-precedence chain stream that has
# them (patch > ... > Core/1.0 static_common). Output is a complete, uncompressed, lowercase static_mod.*.
#
# usage: assemble_complete_stream.py <out_dir> <patch_prefix> <chain_prefix_hi..lo> ...
#   each <prefix> resolves <prefix>.{manifest,bin,relo,imp}; manifests/bins/relos may be RefPack-compressed.
#   priority order = patch first, then the chain prefixes as given (highest precedence to lowest).
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refpack

EO, ES = 48, 44   # header size, entry size (v5 linked manifest)


def _load(path):
    d = open(path, "rb").read()
    return refpack.decompress(d)[0] if refpack.is_refpack(d) else d


def _parse(prefix):
    man = _load(prefix + ".manifest")
    binf = _load(prefix + ".bin"); relof = _load(prefix + ".relo"); impf = _load(prefix + ".imp")
    hdr = list(struct.unpack_from("<11I", man, 4)); ac = hdr[2]
    E = [struct.unpack_from("<4I7i", man, EO + i * ES) for i in range(ac)]  # tid,iid,th,ih,refOff,refCnt,nameOff,srcOff,inst,relo,imp

    def slices(buf, idx):
        assert len(buf) == 4 + sum(e[idx] for e in E), (prefix, idx, len(buf), 4 + sum(e[idx] for e in E))
        off = 4; out = []
        for e in E:
            out.append(buf[off:off + e[idx]]); off += e[idx]
        return buf[:4], out

    bp, binC = slices(binf, 8)
    rp, reloC = slices(relof, 9)
    ip, impC = slices(impf, 10)
    idx = {(e[0], e[1]): i for i, e in enumerate(E)}
    return dict(man=man, hdr=hdr, E=E, binC=binC, reloC=reloC, impC=impC, idx=idx, bp=bp, rp=rp, ip=ip)


def main():
    out_dir = sys.argv[1]
    patch = _parse(sys.argv[2])
    sources = [_parse(p) for p in sys.argv[3:]]   # highest→lowest precedence (after patch)
    ac = patch["hdr"][2]

    outE = []; outBin = []; outRelo = []; outImp = []
    filled = 0; kept = 0; mismatch = 0
    for i, pe in enumerate(patch["E"]):
        if pe[8] > 0:                                  # patch already carries this asset's data
            inst, relo, imp = patch["binC"][i], patch["reloC"][i], patch["impC"][i]
            kept += 1
        else:                                          # deferred — fill from the highest-precedence chain stream
            key = (pe[0], pe[1])
            inst = relo = imp = None
            for s in sources:
                j = s["idx"].get(key)
                if j is not None and s["E"][j][8] > 0:
                    se = s["E"][j]
                    inst, relo, imp = s["binC"][j], s["reloC"][j], s["impC"][j]
                    # Safety: the patch's authoritative entry (th/ih/refcnt) must describe this data.
                    if se[2] != pe[2] or se[3] != pe[3] or se[5] != pe[5]:
                        mismatch += 1
                    break
            if inst is None:
                sys.exit(f"error: orphan asset 0x{pe[0]:08x}:0x{pe[1]:08x} — no chain stream has its data.")
            filled += 1
        e = list(pe); e[8] = len(inst); e[9] = len(relo); e[10] = len(imp)
        outE.append(e); outBin.append(inst); outRelo.append(relo); outImp.append(imp)

    # Keep the patch manifest's reference buffer + name buffers (refOff/refCnt/nameOff/srcOff are unchanged),
    # so references and authored names are preserved verbatim from the authoritative 1.3 manifest.
    arsz = patch["hdr"][7]
    aro = EO + ac * ES
    refbuf = patch["man"][aro:aro + arsz]
    namebufs = patch["man"][aro + arsz:]               # refManNameBuf + assetNameBuf + srcNameBuf

    hdr = list(patch["hdr"])
    hdr[3] = sum(e[8] for e in outE)                   # TotalInstanceDataSize
    hdr[4] = max(e[8] for e in outE)                   # MaxBinaryChunkSize
    hdr[5] = max(e[9] for e in outE)                   # MaxRelocationChunkSize
    hdr[6] = max(e[10] for e in outE)                  # MaxImportsChunkSize
    # hdr[7] (refbuf size), hdr[8..10] (name buf sizes) stay = patch's.
    # hdr[0] = StreamChecksum: the engine treats this as an OPAQUE stream IDENTITY, not an integrity
    # hash it recomputes (EA's own patch header != a from-manifest-order FastHash of its tuples). If we
    # keep the patch's h0, the engine confuses our complete stream with the patch's sparse Static_mod of
    # the same identity and never consults our gameplay data (the edit is ignored; see retag_checksum.py).
    # So compute our OWN identity from our final tuples -- unique, deterministic, zero-EA (computed, not
    # copied). Same FastHash that reproduces Core/1.0 static_common's stored checksum byte-for-byte.
    import retag_checksum
    man_for_sum = bytearray(patch["man"][0:4]) + struct.pack("<11I", *[h & 0xffffffff for h in hdr])
    for e in outE:
        man_for_sum += struct.pack("<4I7i", e[0], e[1], e[2], e[3], e[4], e[5], e[6], e[7], e[8], e[9], e[10])
    checksum = retag_checksum.compute_checksum(bytes(man_for_sum))
    hdr[0] = checksum
    prefix = struct.pack("<I", checksum)

    out = bytearray()
    out += patch["man"][0:4]                           # flags/version
    out += struct.pack("<11I", *[h & 0xffffffff for h in hdr])
    for e in outE:
        out += struct.pack("<4I7i", e[0], e[1], e[2], e[3], e[4], e[5], e[6], e[7], e[8], e[9], e[10])
    out += refbuf
    out += namebufs

    os.makedirs(out_dir, exist_ok=True)
    open(os.path.join(out_dir, "static_mod.manifest"), "wb").write(out)
    open(os.path.join(out_dir, "static_mod.bin"), "wb").write(prefix + b"".join(outBin))
    open(os.path.join(out_dir, "static_mod.relo"), "wb").write(prefix + b"".join(outRelo))
    open(os.path.join(out_dir, "static_mod.imp"), "wb").write(prefix + b"".join(outImp))
    print(f"assembled complete static_mod: {ac} entries ({kept} from patch, {filled} filled from chain); "
          f"bin={4 + sum(e[8] for e in outE):,} relo={4 + sum(e[9] for e in outE):,} imp={4 + sum(e[10] for e in outE):,}")
    print(f"  StreamChecksum (unique identity) = 0x{checksum:08x}  (was patch's 0x{patch['hdr'][0]:08x})")
    if mismatch:
        print(f"  ⚠ {mismatch} filled entr(ies) had th/ih/refcnt differing from the patch manifest "
              f"(used patch's authoritative metadata + chain data).")
    zero = sum(1 for e in outE if e[8] == 0)
    print(f"  zero-size entries remaining: {zero} (want 0 for a complete stream)")


if __name__ == "__main__":
    main()
