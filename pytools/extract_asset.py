#!/usr/bin/env python3
# Extract one asset's instance/relo/imp chunks from a KW v5 LINKED stream, and analyze
# its relocation pointer graph. usage: extract_asset.py <si_dir> <TypeId_hex> <InstanceId_hex> <out_prefix>
import struct, sys

si_dir, tid_hex, iid_hex, outp = sys.argv[1:5]
TID=int(tid_hex,16); IID=int(iid_hex,16)
man=open(si_dir+'/static_mod.manifest','rb').read()
h=struct.unpack_from('<11I',man,4); ac=h[2]; EO=48; ES=44
# cumulative offsets
cb=cr=ci=0; ent=None
for i in range(ac):
    b=EO+i*ES
    t,ii=struct.unpack_from('<2I',man,b)
    ids,rds,imps=struct.unpack_from('<3i',man,b+32)
    if (t==TID) and (ii==IID):
        ent=(i,cb,ids,cr,rds,ci,imps); break
    cb+=ids; cr+=rds; ci+=imps
assert ent, 'not found'
i,binoff,ids,relooff,rds,impoff,imps=ent
print('index=%d  InstanceDataSize=%d ReloSize=%d ImpSize=%d'%(i,ids,rds,imps))
binf=open(si_dir+'/static_mod.bin','rb'); binf.seek(4+binoff); inst=binf.read(ids)
relof=open(si_dir+'/static_mod.relo','rb'); relof.seek(4+relooff); relo=relof.read(rds)
impf=open(si_dir+'/static_mod.imp','rb'); impf.seek(4+impoff); imp=impf.read(imps)
open(outp+'.inst','wb').write(inst); open(outp+'.relo','wb').write(relo); open(outp+'.imp','wb').write(imp)
print('wrote',outp+'.inst/.relo/.imp')
# parse relocations: array of uint32 'from' offsets, terminated by 0xFFFFFFFF
rl=[]; o=0
while o+4<=len(relo):
    v=struct.unpack_from('<I',relo,o)[0]; o+=4
    if v==0xFFFFFFFF: break
    rl.append(v)
print('relocations: %d (each = offset in instance where a pointer->instance lives)'%len(rl))
# imports: array of uint32 'from' offsets, terminated
il=[]; o=0
while o+4<=len(imp):
    v=struct.unpack_from('<I',imp,o)[0]; o+=4
    if v==0xFFFFFFFF: break
    il.append(v)
print('imports: %d (each = offset where an imported-asset InstanceId is stored)'%len(il))
# show the pointer targets for first relocations
print('--- first 12 relocations: from -> to(value stored there) ---')
for f in rl[:12]:
    to=struct.unpack_from('<I',inst,f)[0] if f+4<=len(inst) else None
    print('  from=%d -> to=%s'%(f,to))
