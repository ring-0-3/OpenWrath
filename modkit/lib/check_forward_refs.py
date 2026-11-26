#!/usr/bin/env python3
# Lint a LINKED SAGE/KW stream for FORWARD asset references — a reference whose target appears LATER in the
# manifest than the referencing asset.
#
# WHY (finding 0011, SOLVED 2026-11-26): the engine instantiates a linked stream's assets in MANIFEST ORDER, and
# some reference kinds are bound eagerly to a direct pointer AT LOAD, in order. A target ordered AFTER its
# referrer isn't registered yet -> the pointer binds to NULL, SILENTLY. The proven fatal case: a WeaponTemplate's
# ProjectileNugget -> its projectile (GameObject) and warhead (WeaponTemplate). Forward => the weapon fires FX +
# weapon-local nuggets but spawns/detonates nothing. EA's compiler emits a topological (dependencies-first) order,
# so shipped data is ~99.98% backward-only; the handful of EA forward edges are all to TEXTURES, which are bound
# through an order-INDEPENDENT managed store (benign). Mods that put a ProjectileNugget on a weapon pointing at a
# projectile/warhead placed later in the stream introduce the fatal kind. Fix with modkit/lib/reorder_stream.py.
#
# Classification (honest — only two cases are empirically settled):
#   BENIGN  : target is a Texture/OnDemandTexture        (EA ships forward ones; verified harmless)
#   FATAL   : WeaponTemplate -> GameObject or WeaponTemplate (ProjectileNugget projectile/warhead) -> silent no-launch
#   SUSPECT : any other forward edge                      (not tested; flagged for investigation, not asserted fatal)
#
# usage: check_forward_refs.py <manifest-or-prefix>        (exit 1 if any FATAL forward edge is found)
import sys, os, struct

M = 0xffffffff
EO, ES = 48, 44


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


# Known type names -> hashed id, for readable type labels + classification.
KNOWN_TYPES = [
    "WeaponTemplate", "GameObject", "Texture", "OnDemandTexture", "PackedTextureImage",
    "OnDemandTextureImage", "W3DMesh", "W3DContainer", "W3DHierarchy", "W3DAnimation",
    "W3DCollisionBox", "FXParticleSystemTemplate", "ObjectCreationList", "FXList", "ArmorTemplate",
    "LocomotorTemplate", "UpgradeTemplate", "SpecialPowerTemplate", "DamageFX", "LogicCommand",
    "LogicCommandSet",
]
TYPE_BY_ID = {fast_hash(t): t for t in KNOWN_TYPES}
BENIGN_TARGET_TYPES = {"Texture", "OnDemandTexture", "PackedTextureImage", "OnDemandTextureImage"}


def load(path):
    if not path.endswith(".manifest"):
        path = path + ".manifest"
    d = open(path, "rb").read()
    H = list(struct.unpack_from("<11I", d, 4)); n = H[2]
    arbuf_sz, refman_sz = H[7], H[8]
    arbuf_off = EO + n * ES
    name_off = arbuf_off + arbuf_sz + refman_sz

    def cstr(o):
        e = o
        while e < len(d) and d[e] != 0:
            e += 1
        return d[o:e].decode("ascii", "replace")

    ent = []; names = []
    for i in range(n):
        b = EO + i * ES
        tid, iid = struct.unpack_from("<2I", d, b)
        arOff = struct.unpack_from("<i", d, b + 16)[0]
        arCnt = struct.unpack_from("<i", d, b + 20)[0]
        nmOff = struct.unpack_from("<i", d, b + 24)[0]
        ent.append((tid, iid, arOff, arCnt))
        names.append(cstr(name_off + nmOff))
    return d, ent, names, arbuf_off


def tname(tid):
    return TYPE_BY_ID.get(tid, f"0x{tid:08x}")


def classify(src_type, tgt_type):
    if tgt_type in BENIGN_TARGET_TYPES:
        return "BENIGN"
    if src_type == "WeaponTemplate" and tgt_type in ("GameObject", "WeaponTemplate"):
        return "FATAL"
    return "SUSPECT"


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: check_forward_refs.py <manifest-or-prefix>")
    d, ent, names, arbuf_off = load(sys.argv[1])
    pos = {(e[0], e[1]): i for i, e in enumerate(ent)}
    buckets = {"FATAL": [], "SUSPECT": [], "BENIGN": []}
    total_refs = 0
    for i, (tid, iid, arOff, arCnt) in enumerate(ent):
        st = tname(tid)
        for k in range(arCnt):
            rt, ri = struct.unpack_from("<2I", d, arbuf_off + arOff + k * 8)
            total_refs += 1
            j = pos.get((rt, ri))
            if j is not None and j > i:
                v = classify(st, tname(rt))
                buckets[v].append((i, names[i], st, j, names[j], tname(rt)))

    nf, ns, nb = len(buckets["FATAL"]), len(buckets["SUSPECT"]), len(buckets["BENIGN"])
    print(f"forward-reference lint: {nf} FATAL, {ns} SUSPECT, {nb} BENIGN "
          f"(of {total_refs} refs across {len(ent)} assets)")
    for v in ("FATAL", "SUSPECT", "BENIGN"):
        if not buckets[v]:
            continue
        print(f"\n== {v} ==")
        for (i, sn, st, j, tn, tt) in buckets[v]:
            print(f"  [{i:5d}] {sn}")
            print(f"        --> [{j:5d}] {tn}   (target is LATER by {j - i})")
    if nf:
        print(f"\nFAIL: {nf} fatal forward reference(s) — these will SILENTLY not launch/detonate in-game.")
        print("Fix: reorder so each target precedes its referrer (modkit/lib/reorder_stream.py), then retag_checksum.py.")
    sys.exit(1 if nf else 0)


if __name__ == "__main__":
    main()
