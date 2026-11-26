#!/usr/bin/env python3
# Reorder assets in a LINKED SAGE/KW v5 stream, keeping the parallel data buffers in lockstep.
#
# WHY this is non-trivial: a linked stream's manifest entry carries only DATA SIZES
# (InstanceDataSize/RelocationDataSize/ImportsDataSize), NOT offsets. The engine locates asset i's
# bytes by SUMMING the sizes of all preceding entries, so the .bin/.relo/.imp buffers are
# concatenated strictly in MANIFEST ORDER. Reordering the manifest entries WITHOUT reordering those
# three buffers desyncs every asset after the first move -> the engine reads the wrong bytes -> crash.
# (The reference buffer and the three name buffers are addressed by ABSOLUTE per-entry offsets, so they
#  stay byte-identical and are NOT permuted. relocations/imports are asset-LOCAL, so moving a block is safe.)
#
# This tool applies the SAME permutation to the entry table and to the .bin/.relo/.imp data blocks.
# After writing, re-checksum with retag_checksum.py (identity depends on entry order).
#
# Manifest layout mirrors source/BinaryAssetBuilder.Decompiler/Containers/Manifest.cs (see check_forward_refs.py).
#
# usage:
#   reorder_stream.py <in_prefix> <out_prefix> --before <Type:Name> <Type:Name> [more...]
#       Move the listed assets (in order) to immediately BEFORE the first <Type:Name> (the anchor).
#   reorder_stream.py <in_prefix> <out_prefix> --auto-fix
#       Detect every FATAL forward reference (check_forward_refs.scan) and reorder to eliminate them:
#       move each forward-referenced projectile/warhead ahead of its earliest referrer (topologically among
#       themselves). Prints what moved; no-op (plain copy) if there are none. Finding 0011.
import sys, os, struct, shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_forward_refs as cfr  # single source of truth for fast_hash + forward-edge scan/classify

M = 0xffffffff
HEADER, ENTRY = 48, 44
fast_hash = cfr.fast_hash


def key_for(spec):
    tn, nm = spec.split(':', 1)
    return (fast_hash(tn), fast_hash(nm.lower()))


def _sizes(rec):
    return struct.unpack_from('<3i', rec, 32)  # InstanceDataSize, RelocationDataSize, ImportsDataSize


def _split(buf, blk_sizes, what):
    prefix = buf[:4]; blocks = []; off = 4
    for sz in blk_sizes:
        blocks.append(buf[off:off + sz]); off += sz
    if off != len(buf):
        raise SystemExit(f"{what}: size mismatch (consumed {off} of {len(buf)}; sum+4 != filesize)")
    return prefix, blocks


def load_all(prefix):
    man = bytearray(open(prefix + '.manifest', 'rb').read())
    hdr = list(struct.unpack_from('<11I', man, 4)); n = hdr[2]
    recs = [bytes(man[HEADER + i * ENTRY: HEADER + (i + 1) * ENTRY]) for i in range(n)]
    tail = bytes(man[HEADER + n * ENTRY:])
    inst = [_sizes(r)[0] for r in recs]; relo = [_sizes(r)[1] for r in recs]; imp = [_sizes(r)[2] for r in recs]
    bpre, bblk = _split(open(prefix + '.bin', 'rb').read(), inst, 'bin')
    rpre, rblk = _split(open(prefix + '.relo', 'rb').read(), relo, 'relo')
    ipre, iblk = _split(open(prefix + '.imp', 'rb').read(), imp, 'imp')
    return man, hdr, recs, tail, (bpre, bblk), (rpre, rblk), (ipre, iblk)


def apply_permutation(in_prefix, out_prefix, perm):
    """perm = list of ORIGINAL entry indices in the desired NEW order (a permutation of range(n))."""
    man, hdr, recs, tail, (bpre, bblk), (rpre, rblk), (ipre, iblk) = load_all(in_prefix)
    n = len(recs)
    if sorted(perm) != list(range(n)):
        raise SystemExit("internal: perm is not a permutation of range(n)")
    out_man = bytearray(man[:HEADER])
    out_bin = bytearray(bpre); out_relo = bytearray(rpre); out_imp = bytearray(ipre)
    for oi in perm:
        out_man += recs[oi]; out_bin += bblk[oi]; out_relo += rblk[oi]; out_imp += iblk[oi]
    out_man += tail
    assert len(out_man) == len(man)
    open(out_prefix + '.manifest', 'wb').write(out_man)
    open(out_prefix + '.bin', 'wb').write(out_bin)
    open(out_prefix + '.relo', 'wb').write(out_relo)
    open(out_prefix + '.imp', 'wb').write(out_imp)


def _keys(recs):
    return [struct.unpack_from('<2I', r, 0) for r in recs]


def perm_before(recs, anchor_key, mover_keys):
    keys = _keys(recs); pos = {k: i for i, k in enumerate(keys)}
    for k in [anchor_key] + mover_keys:
        if k not in pos:
            raise SystemExit(f"asset not found: hashes {k[0]:#010x},{k[1]:#010x}")
    anchor_i = pos[anchor_key]; mover_set = set(mover_keys)
    perm = []
    for i, k in enumerate(keys):
        if k in mover_set:
            continue
        if i == anchor_i:
            perm.extend(pos[mk] for mk in mover_keys)
        perm.append(i)
    return perm


def _toposort(nodes, edges):
    # edges: list of (u, v) meaning u depends-on/must-precede-nothing... here (src,tgt): tgt must come BEFORE src.
    # We want order with every tgt before its src. Build "must precede" = tgt -> src, emit via Kahn.
    from collections import defaultdict, deque
    succ = defaultdict(list); indeg = {x: 0 for x in nodes}
    for (src, tgt) in edges:
        if src in nodes and tgt in nodes:
            succ[tgt].append(src); indeg[src] += 1
    q = deque(sorted(x for x in nodes if indeg[x] == 0))
    out = []
    while q:
        x = q.popleft(); out.append(x)
        for y in sorted(succ[x]):
            indeg[y] -= 1
            if indeg[y] == 0:
                q.append(y)
    if len(out) != len(nodes):            # cycle (shouldn't happen for proj/warhead) -> stable fallback
        out = sorted(nodes)
    return out


def perm_autofix(in_prefix):
    """Build a permutation that eliminates every FATAL forward edge, or None if there are none."""
    buckets, _, _ = cfr.scan(in_prefix + '.manifest')
    fatal = buckets['FATAL']
    if not fatal:
        return None, []
    edges = [(si, ti) for (si, _, _, ti, _, _) in fatal]
    targets = set(ti for _, ti in edges)
    anchor = min(si for si, _ in edges)                 # earliest referrer of any fatal edge
    ordered_targets = _toposort(targets, edges)         # a target that references another target comes first
    man, hdr, recs, *_ = load_all(in_prefix)
    n = len(recs)
    non_targets = [i for i in range(n) if i not in targets]
    insert_at = len(non_targets)
    for idx, orig in enumerate(non_targets):
        if orig >= anchor:
            insert_at = idx; break
    perm = non_targets[:insert_at] + ordered_targets + non_targets[insert_at:]
    moved = [(ti, fatal[[t for _, t in edges].index(ti)]) for ti in ordered_targets]
    return perm, fatal


def main():
    if len(sys.argv) >= 4 and sys.argv[3] == '--before':
        inp, outp = sys.argv[1], sys.argv[2]
        specs = sys.argv[4:]
        if len(specs) < 2:
            sys.exit("need an anchor and at least one asset to move before it")
        _, _, recs, *_ = load_all(inp)
        perm = perm_before(recs, key_for(specs[0]), [key_for(s) for s in specs[1:]])
        apply_permutation(inp, outp, perm)
        print(f"reordered {len(recs)} entries + bin/relo/imp in lockstep -> {outp}.*")
        print("NOTE: run retag_checksum.py on the OUTPUT prefix next.")
        return
    if len(sys.argv) == 4 and sys.argv[3] == '--auto-fix':
        inp, outp = sys.argv[1], sys.argv[2]
        perm, fatal = perm_autofix(inp)
        if perm is None:
            if inp != outp:
                for ext in ('manifest', 'bin', 'relo', 'imp'):
                    shutil.copyfile(inp + '.' + ext, outp + '.' + ext)
            print("auto-fix: no FATAL forward references — nothing to reorder.")
            return
        apply_permutation(inp, outp, perm)
        print(f"auto-fix: moved {len(set(t for _,_,_,t,_,_ in fatal))} forward-referenced template(s) "
              f"ahead of their referrer(s) to clear {len(fatal)} FATAL forward edge(s):")
        for (si, sn, st, ti, tn, tt) in fatal:
            print(f"    {sn}  ->  {tn}  (was +{ti - si})")
        print("NOTE: run retag_checksum.py on the OUTPUT prefix next.")
        return
    sys.exit(__doc__)


if __name__ == '__main__':
    main()
