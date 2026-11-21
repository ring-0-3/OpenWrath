#!/usr/bin/env python3
# Surgically INSERT one NEW asset into a KW v5 LINKED stream (manifest+bin+relo+imp).
#
# Sibling of splice_asset.py. splice REPLACES an asset that already exists in the stream; insert ADDS one
# that does not — the capability a mod needs to ship a brand-new weapon / projectile / unit, not just tweak
# an existing one.
#
# It is pure APPEND, which is what makes it safe: the new asset's entry goes last, and its reference / name /
# source bytes are appended at the END of their buffers. Every existing entry therefore keeps its exact
# AssetReferenceOffset / NameOffset / SourceFileNameOffset and its chunk bytes — so every pre-existing asset
# round-trips byte-identical; only the new one is added. (Verify with the decompiler round-trip harness.)
#
# Linked manifest layout (LE): 48B header + N*44B AssetEntry + AssetRefBuf + RefManNameBuf + AssetNameBuf
#   + SrcNameBuf. AssetEntry(44B): TypeId,InstanceId,TypeHash,InstanceHash,AssetReferenceOffset,
#   AssetReferenceCount,NameOffset,SourceFileNameOffset,InstanceDataSize,RelocationDataSize,ImportsDataSize.
# .bin/.relo/.imp = 4B prefix + per-asset chunks concatenated in manifest order.
# .asset file = 32B header(TypeId,Inst,TypeHash,InstHash,InstDataSize,ReloSize,ImpSize,Zero)+inst+relo+imp.
# AssetReferences are self-contained 8-byte (TypeId,InstanceId) pairs — no RefManNameBuf dependency, so that
#   buffer is left untouched (a referenced asset is resolved globally across the loaded manifest set).
#
# usage: insert_asset.py <stream_dir> <new.asset> <new_manifest> <out_dir> <stream_name> [source_label]
import struct, sys, os

def rd(p): return open(p, 'rb').read()

def main():
    stream_dir, new_asset, new_mf, out_dir, stream = sys.argv[1:6]
    source_label = sys.argv[6] if len(sys.argv) > 6 else None
    os.makedirs(out_dir, exist_ok=True)

    man = bytearray(rd(os.path.join(stream_dir, f'{stream}.manifest')))
    binf = rd(os.path.join(stream_dir, f'{stream}.bin'))
    relof = rd(os.path.join(stream_dir, f'{stream}.relo'))
    impf = rd(os.path.join(stream_dir, f'{stream}.imp'))

    hdr = list(struct.unpack_from('<11I', man, 4))
    ac = hdr[2]
    EO, ES = 48, 44
    E = [list(struct.unpack_from('<11i', man, EO + i * ES)) for i in range(ac)]

    aro = EO + ac * ES
    arsz, rmsz, ansz, snsz = hdr[7], hdr[8], hdr[9], hdr[10]
    assetRefBuf = man[aro:aro + arsz]
    refManNameBuf = man[aro + arsz:aro + arsz + rmsz]
    assetNameBuf = man[aro + arsz + rmsz:aro + arsz + rmsz + ansz]
    srcNameBuf = man[aro + arsz + rmsz + ansz:aro + arsz + rmsz + ansz + snsz]
    assert len(srcNameBuf) == snsz, (len(srcNameBuf), snsz)

    # stream buffers: 4B prefix + per-asset chunks
    def slices(buf, sizefield):
        assert len(buf) == 4 + sum(e[sizefield] for e in E), (sizefield, len(buf), 4 + sum(e[sizefield] for e in E))
        off = 4; out = []
        for e in E:
            out.append(buf[off:off + e[sizefield]]); off += e[sizefield]
        return buf[:4], out
    pbin, binC = slices(binf, 8)
    prelo, reloC = slices(relof, 9)
    pimp, impC = slices(impf, 10)

    # load new asset
    a = rd(new_asset)
    at, ai, ath, aih, aids, ards, aimps, azero = struct.unpack_from('<8I', a, 0)
    assert len(a) == 32 + aids + ards + aimps, 'asset len mismatch'
    n_inst = a[32:32 + aids]; n_relo = a[32 + aids:32 + aids + ards]; n_imp = a[32 + aids + ards:]

    # guard: the id must NOT already be in the stream (that would be a splice, not an insert)
    if any((e[0] & 0xffffffff) == at and (e[1] & 0xffffffff) == ai for e in E):
        sys.exit(f'error: {at:08x}:{ai:08x} already exists in {stream} — use splice_asset.py to replace it')

    # pull the new asset's references + authored name + source name from its own compile manifest
    nm = rd(new_mf); nhdr = struct.unpack_from('<11I', nm, 4); nac = nhdr[2]
    n_arsz, n_rmsz, n_ansz = nhdr[7], nhdr[8], nhdr[9]
    n_aro = 48 + nac * 44
    n_nameBase = n_aro + n_arsz + n_rmsz
    n_srcBase = n_nameBase + n_ansz
    nz = [i for i in range(nac)
          if struct.unpack_from('<2I', nm, 48 + i * 44)[0] == at and struct.unpack_from('<2I', nm, 48 + i * 44)[1] == ai]
    assert len(nz) == 1, ('new asset not in its manifest', len(nz)); nzi = nz[0]
    nro, nrc = struct.unpack_from('<2i', nm, 48 + nzi * 44 + 16)
    n_refs = nm[n_aro + nro:n_aro + nro + nrc * 8]
    nnoff, nsoff = struct.unpack_from('<2i', nm, 48 + nzi * 44 + 24)

    def cstr(buf, off):
        p = off
        end = buf.index(b'\x00', p)
        return buf[p:end]
    name_bytes = cstr(nm, n_nameBase + nnoff)                       # e.g. b"WeaponTemplate:NukeAvatarWarhead"
    # source: use a clean label (avoid leaking an absolute build path into the shipped stream)
    if source_label is not None:
        src_bytes = source_label.encode('latin1', 'replace')
    else:
        raw = cstr(nm, n_srcBase + nsoff)
        src_bytes = os.path.basename(raw.decode('latin1', 'replace')).encode('latin1', 'replace')
    print(f'inserting {name_bytes.decode("latin1")}  '
          f'inst/relo/imp/refs={aids}/{ards}/{aimps}/{nrc}  src="{src_bytes.decode("latin1")}"')

    # --- build the new entry (appended last; every offset points at the END of its buffer) ---
    new_entry = [at, ai, ath, aih,
                 arsz,          # AssetReferenceOffset = current end of AssetRefBuf
                 nrc,           # AssetReferenceCount
                 ansz,          # NameOffset = current end of AssetNameBuf
                 snsz,          # SourceFileNameOffset = current end of SrcNameBuf
                 aids, ards, aimps]
    E.append(new_entry)
    binC.append(n_inst); reloC.append(n_relo); impC.append(n_imp)
    assetRefBuf += n_refs
    assetNameBuf += name_bytes + b'\x00'
    srcNameBuf += src_bytes + b'\x00'

    # rebuild stream buffers (new chunk is last, matching the new last entry)
    newbin = pbin + b''.join(binC)
    newrelo = prelo + b''.join(reloC)
    newimp = pimp + b''.join(impC)

    # header updates
    hdr[2] = len(E)                              # AssetCount
    hdr[3] = sum(e[8] for e in E)                # TotalInstanceDataSize
    hdr[4] = max(e[8] for e in E)                # MaxBinaryChunkSize
    hdr[5] = max(e[9] for e in E)                # MaxRelocationChunkSize
    hdr[6] = max(e[10] for e in E)               # MaxImportsChunkSize
    hdr[7] = len(assetRefBuf)                     # AssetReferenceBufferSize
    hdr[8] = len(refManNameBuf)                   # ReferenceManifestNameBufferSize (unchanged)
    hdr[9] = len(assetNameBuf)                     # AssetNameBufferSize
    hdr[10] = len(srcNameBuf)                      # SourceFileNameBufferSize

    out = bytearray()
    out += man[0:4]                               # isBE, isLinked, version(2)
    out += struct.pack('<11I', *[h & 0xffffffff for h in hdr])
    for e in E:
        out += struct.pack('<4I7i', e[0] & 0xffffffff, e[1] & 0xffffffff, e[2] & 0xffffffff, e[3] & 0xffffffff,
                           e[4], e[5], e[6], e[7], e[8], e[9], e[10])
    out += assetRefBuf
    out += refManNameBuf
    out += assetNameBuf
    out += srcNameBuf

    open(os.path.join(out_dir, f'{stream}.manifest'), 'wb').write(out)
    open(os.path.join(out_dir, f'{stream}.bin'), 'wb').write(newbin)
    open(os.path.join(out_dir, f'{stream}.relo'), 'wb').write(newrelo)
    open(os.path.join(out_dir, f'{stream}.imp'), 'wb').write(newimp)
    print('WROTE', out_dir, f'(assets {ac} -> {len(E)})')
    print(f'  manifest {len(out)}  bin {len(newbin)}  relo {len(newrelo)}  imp {len(newimp)}')

main()
