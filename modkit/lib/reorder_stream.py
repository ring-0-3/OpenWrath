#!/usr/bin/env python3
# Reorder assets in a LINKED SAGE/KW v5 stream, keeping the parallel data buffers in lockstep.
#
# WHY this is non-trivial: a linked stream's manifest entry carries only DATA SIZES
# (InstanceDataSize/RelocationDataSize/ImportsDataSize), NOT offsets. The engine locates asset i's
# bytes by SUMMING the sizes of all preceding entries, so the .bin/.relo/.imp buffers are
# concatenated strictly in MANIFEST ORDER. Reordering the manifest entries WITHOUT reordering those
# three buffers desyncs every asset after the first move -> the engine reads the wrong bytes -> crash.
# (The reference buffer and the three name buffers are addressed by ABSOLUTE per-entry offsets, so they
#  stay byte-identical and are NOT permuted.)
#
# This tool applies the SAME permutation to the entry table and to the .bin/.relo/.imp data blocks.
# After writing, re-checksum with retag_checksum.py (identity depends on entry order).
#
# Manifest layout (mirrors source/BinaryAssetBuilder.Decompiler/Containers/Manifest.cs):
#   [0]   byte isBigEndian, [1] byte isLinked, [2..3] uint16 version
#   [4..47] 11 x uint32 header: h[2]=AssetCount, h[7]=AssetRefBufSize, h[8]=RefManNameBufSize,
#           h[9]=AssetNameBufSize, h[10]=SourceFileNameBufSize   (h[0]=StreamChecksum)
#   [48..]  AssetCount x 44-byte entries (11 ints):
#           TypeId, InstanceId, TypeHash, InstanceHash, AssetRefOffset, AssetRefCount,
#           NameOffset, SourceFileNameOffset, InstanceDataSize, RelocationDataSize, ImportsDataSize
#   then: AssetReferenceBuffer | ReferenceManifestNameBuffer | AssetNameBuffer | SourceFileNameBuffer
# Each of .bin/.relo/.imp = 4-byte StreamChecksum prefix + per-asset data concatenated in manifest order.
#
# usage:
#   reorder_stream.py <in_prefix> <out_prefix> --before <Type:Name> <Type:Name> [more...]
#     Moves the listed assets (in the given order) to immediately BEFORE the first <Type:Name> (the anchor).
#     i.e. the first arg after --before is the ANCHOR; the rest are MOVED to just ahead of it.
import os, sys, struct

M = 0xffffffff
HEADER, ENTRY = 48, 44


def fast_hash(s):
    b = s.encode('ascii'); L = len(b)
    if L == 0: return 0x1337C0DE
    h = L & M; extra = L & 3; n = L >> 2; i = 0
    u16 = lambda j: b[j] | (b[j + 1] << 8)
    while n > 0:
        h = (h + u16(i)) & M
        h = (h ^ (((u16(i + 2) ^ ((h << 5) & M)) << 11) & M)) & M
        h = (h + (h >> 11)) & M
        i += 4; n -= 1
    if extra == 1:
        h = (h + b[i]) & M; h = (h ^ ((h << 10) & M)) & M; h = (h + (h >> 1)) & M
    elif extra == 2:
        h = (h + u16(i)) & M; h = (h ^ ((h << 11) & M)) & M; h = (h + (h >> 17)) & M
    elif extra == 3:
        h = (h + u16(i)) & M; h = (h ^ ((h << 16) & M)) & M
        h = (h ^ ((b[i + 2] << 18) & M)) & M; h = (h + (h >> 11)) & M
    h = (h ^ ((h << 3) & M)) & M; h = (h + (h >> 5)) & M
    h = (h ^ ((h << 2) & M)) & M; h = (h + (h >> 15)) & M; h = (h ^ ((h << 10) & M)) & M
    return h & M


def key_for(spec):
    # "Type:Name" -> (fast_hash(Type), fast_hash(name.lower()))   (type as-is, instance lowercased)
    tn, nm = spec.split(':', 1)
    return (fast_hash(tn), fast_hash(nm.lower()))


def load_entries(man):
    hdr = list(struct.unpack_from('<11I', man, 4))
    n = hdr[2]
    recs = [bytes(man[HEADER + i * ENTRY: HEADER + (i + 1) * ENTRY]) for i in range(n)]
    tail = bytes(man[HEADER + n * ENTRY:])  # refbuf + 3 name buffers (absolute-addressed; unchanged)
    return hdr, recs, tail


def sizes(rec):
    # InstanceDataSize, RelocationDataSize, ImportsDataSize at +32/+36/+40
    inst, relo, imp = struct.unpack_from('<3i', rec, 32)
    return inst, relo, imp


def split_buffer(buf, order_sizes):
    # buf = 4-byte prefix + concat(block_i). Return (prefix, [block_i...]) in current order.
    prefix = buf[:4]
    blocks = []
    off = 4
    for sz in order_sizes:
        blocks.append(buf[off:off + sz]); off += sz
    if off != len(buf):
        raise SystemExit(f"buffer size mismatch: consumed {off} of {len(buf)} (sum+4 != filesize)")
    return prefix, blocks


def main():
    if len(sys.argv) < 5 or sys.argv[3] != '--before':
        sys.exit(__doc__)
    inp, outp = sys.argv[1], sys.argv[2]
    specs = sys.argv[4:]
    anchor = key_for(specs[0])
    movers = [key_for(s) for s in specs[1:]]
    if not movers:
        sys.exit("need an anchor and at least one asset to move before it")

    man = bytearray(open(inp + '.manifest', 'rb').read())
    hdr, recs, tail = load_entries(man)
    n = len(recs)
    keyf = lambda r: struct.unpack_from('<2I', r, 0)  # (TypeId, InstanceId)

    # index lookup
    idx = {}
    for i, r in enumerate(recs):
        idx[keyf(r)] = i
    for k, s in zip([anchor] + movers, specs):
        if k not in idx:
            sys.exit(f"asset not found in stream: {s}  (hashes {k[0]:#010x},{k[1]:#010x})")
    anchor_i = idx[anchor]
    mover_set = set(movers)

    # build new entry order: drop movers from their spots; emit them (in given order) right before the anchor
    mover_recs = {keyf(recs[idx[k]]): recs[idx[k]] for k in movers}
    new_order_recs = []
    for i, r in enumerate(recs):
        if keyf(r) in mover_set:
            continue
        if i == anchor_i:
            for k in movers:
                new_order_recs.append(mover_recs[k])
        new_order_recs.append(r)
    if len(new_order_recs) != n:
        sys.exit(f"internal: new order has {len(new_order_recs)} != {n} entries")

    # current per-entry sizes, in ORIGINAL order, to split the 3 data buffers
    orig_inst = [sizes(r)[0] for r in recs]
    orig_relo = [sizes(r)[1] for r in recs]
    orig_imp = [sizes(r)[2] for r in recs]

    bin_ = open(inp + '.bin', 'rb').read()
    relo = open(inp + '.relo', 'rb').read()
    imp = open(inp + '.imp', 'rb').read()
    bpre, bblocks = split_buffer(bin_, orig_inst)
    rpre, rblocks = split_buffer(relo, orig_relo)
    ipre, iblocks = split_buffer(imp, orig_imp)

    # map original-entry key -> original index, so we can fetch its data block
    key_to_orig = {keyf(recs[i]): i for i in range(n)}

    # reassemble each data buffer in the NEW entry order
    out_bin = bytearray(bpre); out_relo = bytearray(rpre); out_imp = bytearray(ipre)
    for r in new_order_recs:
        oi = key_to_orig[keyf(r)]
        out_bin += bblocks[oi]; out_relo += rblocks[oi]; out_imp += iblocks[oi]

    # reassemble manifest: header(unchanged; checksum retagged later) + new entries + tail(unchanged)
    out_man = bytearray(man[:HEADER])
    for r in new_order_recs:
        out_man += r
    out_man += tail

    assert len(out_man) == len(man), (len(out_man), len(man))
    assert len(out_bin) == len(bin_) and len(out_relo) == len(relo) and len(out_imp) == len(imp)

    open(outp + '.manifest', 'wb').write(out_man)
    open(outp + '.bin', 'wb').write(out_bin)
    open(outp + '.relo', 'wb').write(out_relo)
    open(outp + '.imp', 'wb').write(out_imp)

    # report the new positions of the involved assets
    newpos = {}
    for i, r in enumerate(new_order_recs):
        k = keyf(r)
        if k == anchor or k in mover_set:
            newpos[k] = i
    print(f"reordered {n} entries + bin/relo/imp blocks in lockstep -> {outp}.*")
    for k, s in zip([anchor] + movers, specs):
        print(f"  {s:50s} -> new index {newpos[k]}")
    print("NOTE: run retag_checksum.py on the OUTPUT prefix next (identity depends on entry order).")


if __name__ == '__main__':
    main()
