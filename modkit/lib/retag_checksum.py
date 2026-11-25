#!/usr/bin/env python3
# Retag a linked stream's StreamChecksum (manifest header h0 + the matching first-dword of
# bin/relo/imp) to a UNIQUE, content-derived identity.
#
# WHY (finding: stream-identity collision): the engine treats StreamChecksum as an OPAQUE stream
# IDENTITY, not a recomputed integrity hash (proven: EA's own patch header 0xd285ee18 does NOT equal
# a from-manifest-order FastHash of its tuples, so the engine cannot be recomputing+comparing it).
# `assemble_complete_stream.py` copies the patch's h0 verbatim, so a complete mod static_mod ships
# with EA's patch identity. The engine then treats the mod stream as the already-known patch stream
# and never consults the mod's gameplay data -> the edit is ignored (art differs/goes magenta as a
# secondary symptom of the collision). A UNIQUE identity (what BAB gives SecondIsomer) fixes it.
#
# The new value is FastHash over this stream's own (TypeId,TypeHash,InstanceId,InstanceHash,RefCount)
# tuples in manifest order, padded to the .NET MemoryStream capacity and seeded with that capacity --
# the exact algorithm, verified to reproduce Core/1.0 static_common's stored checksum byte-for-byte.
# It is a deterministic function of the stream's content, guaranteed != the patch's (content differs),
# and recomputes if the content changes. Zero-EA: computed, never copied from EA.
#
# usage: retag_checksum.py <prefix>   (rewrites <prefix>.{manifest,bin,relo,imp} in place)
import os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import refpack

EO, ES = 48, 44
M32 = 0xffffffff


def _fasthashfn(buf, length, seed):
    h = seed & M32
    extra = length & 3
    n = length >> 2
    p = 0
    for _ in range(n):
        lo = buf[p] | (buf[p + 1] << 8)
        hi = buf[p + 2] | (buf[p + 3] << 8)
        h = (h + lo) & M32
        h = (h ^ (((hi ^ ((h << 5) & M32)) << 11) & M32)) & M32
        h = (h + (h >> 11)) & M32
        p += 4
    if extra == 1:
        h = (h + buf[p]) & M32; h = (h ^ ((h << 10) & M32)) & M32; h = (h + (h >> 1)) & M32
    elif extra == 2:
        v = buf[p] | (buf[p + 1] << 8); h = (h + v) & M32; h = (h ^ ((h << 11) & M32)) & M32; h = (h + (h >> 17)) & M32
    elif extra == 3:
        v = buf[p] | (buf[p + 1] << 8); h = (h + v) & M32; h = (h ^ ((h << 16) & M32)) & M32
        h = (h ^ ((buf[p + 2] << 18) & M32)) & M32; h = (h + (h >> 11)) & M32
    h = (h ^ ((h << 3) & M32)) & M32
    h = (h + (h >> 5)) & M32
    h = (h ^ ((h << 2) & M32)) & M32
    h = (h + (h >> 15)) & M32
    h = (h ^ ((h << 10) & M32)) & M32
    return h


def _dotnet_capacity(L):
    cap, pos = 0, 0
    for _ in range(0, L, 4):
        need = pos + 4
        if need > cap:
            nc = need
            if nc < 256: nc = 256
            if nc < cap * 2: nc = cap * 2
            cap = nc
        pos += 4
    return cap


def compute_checksum(manifest_bytes):
    hdr = struct.unpack_from("<11I", manifest_bytes, 4)
    ac = hdr[2]
    data = bytearray()
    for i in range(ac):
        e = struct.unpack_from("<4I7i", manifest_bytes, EO + i * ES)  # tid,iid,th,ih,refOff,refCnt,...
        data += struct.pack("<IIIIi", e[0], e[2], e[1], e[3], e[5])    # TypeId,TypeHash,InstanceId,InstanceHash,RefCount
    L = len(data)
    cap = _dotnet_capacity(L)
    buf = bytearray(data) + bytearray(cap - L)
    return _fasthashfn(buf, len(buf), len(buf))


def main():
    prefix = sys.argv[1]
    man = open(prefix + ".manifest", "rb").read()
    if refpack.is_refpack(man):
        sys.exit("manifest is RefPack-compressed; retag the uncompressed stream before packing.")
    old = struct.unpack_from("<I", man, 4)[0]
    new = compute_checksum(man)
    if new == old:
        print(f"checksum already unique/current: 0x{old:08x} (no change)")
        return
    # manifest header
    man = bytearray(man)
    struct.pack_into("<I", man, 4, new)
    open(prefix + ".manifest", "wb").write(man)
    # bin/relo/imp first dword
    for ext in ("bin", "relo", "imp"):
        p = prefix + "." + ext
        d = bytearray(open(p, "rb").read())
        struct.pack_into("<I", d, 0, new)
        open(p, "wb").write(d)
    print(f"retagged StreamChecksum: 0x{old:08x} -> 0x{new:08x}  (manifest + bin/relo/imp)")


if __name__ == "__main__":
    main()
