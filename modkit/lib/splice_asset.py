#!/usr/bin/env python3
# Surgically replace ONE asset in a KW v5 LINKED stream (manifest+bin+relo+imp)
# with a freshly-compiled per-asset .asset (+ its AssetReferences from that compile's manifest).
#
# Linked manifest layout (LE): 48B header + N*44B AssetEntry + AssetRefBuf + RefManNameBuf
#   + AssetNameBuf + SrcNameBuf.
# AssetEntry(44B): TypeId,InstanceId,TypeHash,InstanceHash,AssetReferenceOffset,AssetReferenceCount,
#   NameOffset,SourceFileNameOffset,InstanceDataSize,RelocationDataSize,ImportsDataSize.
# .bin/.relo/.imp each = 4B prefix + per-asset chunks concatenated in manifest order (sizes from entries).
# .asset file = 32B AssetHeader(TypeId,Inst,TypeHash,InstHash,InstDataSize,ReloSize,ImpSize,Zero)
#   + instance + relo + imp.
#
# usage: splice_asset.py <si_dir> <new.asset> <new_manifest> <out_dir> <TypeId_hex> <InstanceId_hex>
import struct, sys, os

def rd(p): return open(p,'rb').read()

def main():
    si_dir, new_asset, new_mf, out_dir, tid_hex, iid_hex = sys.argv[1:7]
    TID=int(tid_hex,16); IID=int(iid_hex,16)
    os.makedirs(out_dir, exist_ok=True)

    man = bytearray(rd(os.path.join(si_dir,'static_mod.manifest')))
    binf = rd(os.path.join(si_dir,'static_mod.bin'))
    relof= rd(os.path.join(si_dir,'static_mod.relo'))
    impf = rd(os.path.join(si_dir,'static_mod.imp'))

    hdr = list(struct.unpack_from('<11I', man, 4))
    ac = hdr[2]
    EO=48; ES=44
    # parse entries
    E=[]
    for i in range(ac):
        E.append(list(struct.unpack_from('<11i', man, EO+i*ES)))  # signed view ok for sizes/offsets; ids wrap
    # locate buffers
    aro = EO+ac*ES
    arsz,rmsz,ansz,snsz = hdr[7],hdr[8],hdr[9],hdr[10]
    assetRefBuf = man[aro:aro+arsz]
    rest = man[aro+arsz:]  # refManNameBuf+assetNameBuf+srcNameBuf (unchanged)
    assert len(rest)==rmsz+ansz+snsz, (len(rest),rmsz+ansz+snsz)

    # verify stream prefixes + slice per-asset chunks
    def slices(buf, sizefield):
        assert len(buf) == 4 + sum(e[sizefield] for e in E), (sizefield,len(buf),4+sum(e[sizefield] for e in E))
        off=4; out=[]
        for e in E:
            out.append(buf[off:off+e[sizefield]]); off+=e[sizefield]
        return buf[:4], out
    pbin, binC = slices(binf, 8)   # InstanceDataSize idx8
    prelo,reloC= slices(relof,9)   # RelocationDataSize idx9
    pimp, impC = slices(impf, 10)  # ImportsDataSize idx10
    # ref slices (cumulative, 8 bytes each)
    refC=[]; o=0
    for e in E:
        n=e[5]*8; refC.append(assetRefBuf[o:o+n]); o+=n
    assert o==arsz

    # find target
    zi=[i for i,e in enumerate(E) if (e[0]&0xffffffff)==TID and (e[1]&0xffffffff)==IID]
    assert len(zi)==1, ('target count',len(zi)); z=zi[0]
    print('target index',z,'old sizes inst/relo/imp/refcnt=',E[z][8],E[z][9],E[z][10],E[z][5])

    # load new asset
    a=rd(new_asset)
    at,ai,ath,aih,aids,ards,aimps,azero=struct.unpack_from('<8I',a,0)
    assert at==TID and ai==IID, 'asset id mismatch'
    assert len(a)==32+aids+ards+aimps, 'asset len mismatch'
    n_inst=a[32:32+aids]; n_relo=a[32+aids:32+aids+ards]; n_imp=a[32+aids+ards:]
    # load new refs from new manifest
    nm=rd(new_mf); nhdr=struct.unpack_from('<11I',nm,4); nac=nhdr[2]
    naro=48+nac*44
    nz=[i for i in range(nac) if struct.unpack_from('<2I',nm,48+i*44)[0]==TID and struct.unpack_from('<2I',nm,48+i*44)[1]==IID]
    assert len(nz)==1; nzi=nz[0]
    nro,nrc=struct.unpack_from('<2i',nm,48+nzi*44+16)
    n_refs=nm[naro+nro:naro+nro+nrc*8]
    print('new sizes inst/relo/imp/refcnt=',aids,ards,aimps,nrc)

    # swap chunks
    binC[z]=n_inst; reloC[z]=n_relo; impC[z]=n_imp; refC[z]=n_refs
    E[z][8]=aids; E[z][9]=ards; E[z][10]=aimps; E[z][5]=nrc; E[z][3]=aih  # InstanceHash update
    # recompute cumulative AssetReferenceOffset (idx4)
    cum=0
    for e in E:
        e[4]=cum; cum+=e[5]*8
    new_arsz=cum
    # rebuild buffers
    newbin  = pbin  + b''.join(binC)
    newrelo = prelo + b''.join(reloC)
    newimp  = pimp  + b''.join(impC)
    newref  = b''.join(refC)
    # update header
    hdr[3]=sum(e[8] for e in E)           # TotalInstanceDataSize
    hdr[4]=max(e[8] for e in E)           # MaxBinaryChunkSize
    hdr[5]=max(e[9] for e in E)           # MaxRelocationChunkSize
    hdr[6]=max(e[10] for e in E)          # MaxImportsChunkSize
    hdr[7]=new_arsz                        # AssetReferenceBufferSize
    # reassemble manifest cleanly
    out=bytearray()
    out+=man[0:4]                                           # isBE,isLinked,version(2)
    out+=struct.pack('<11I', *[h & 0xffffffff for h in hdr])
    for e in E:
        out+=struct.pack('<4I7i', e[0]&0xffffffff,e[1]&0xffffffff,e[2]&0xffffffff,e[3]&0xffffffff,
                         e[4],e[5],e[6],e[7],e[8],e[9],e[10])
    out+=newref
    out+=rest
    # sanity: manifest size
    open(os.path.join(out_dir,'static_mod.manifest'),'wb').write(out)
    open(os.path.join(out_dir,'static_mod.bin'),'wb').write(newbin)
    open(os.path.join(out_dir,'static_mod.relo'),'wb').write(newrelo)
    open(os.path.join(out_dir,'static_mod.imp'),'wb').write(newimp)
    print('WROTE', out_dir)
    print('  manifest',len(out),'bin',len(newbin),'relo',len(newrelo),'imp',len(newimp))
    print('  new TotalInstanceDataSize',hdr[3],'assetRefBufSize',new_arsz)

main()
