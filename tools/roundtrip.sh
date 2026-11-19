#!/usr/bin/env bash
# Round-trip validation harness for the native Linux decompiler.
#
#   tools/roundtrip.sh <source.xml-relative-to-dataroot> [--only NAME]
#
# Cycle:  compile source XML -> REF (manifest + .asset)      [reference bytes, as EA's BAB would produce]
#         decompile REF      -> DEC.xml (one combined stream) [the thing under test]
#         compile DEC.xml    -> NEW (manifest + .asset)       [does our XML reproduce the bytes?]
#         byte-compare every asset's instance/relo/imp buffers, keyed by (TypeId, InstanceId).
#
# A pass means the decompiler is loss-free for that asset: its XML recompiles to identical bytes.
# Requires: the built Debug/ BinaryAssetBuilder.dll + bab-decompile.dll, and the KW SDK XML tree.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BAB="$ROOT/Debug/BinaryAssetBuilder.dll"
DEC="$ROOT/Debug/bab-decompile.dll"
SCHEMA="${KW_SCHEMA:-$ROOT/schemas/kw/xsd/CnC3Types.xsd}"
DR="${KW_DATAROOT:-$HOME/kw-mod-sdk/KanesWrathXMLFiles}"
BM="${KW_BASEMANIFESTS:-$HOME/kw-mod-sdk/base-manifests}"
RM="$BM/global_common_2.manifest;$BM/static_common_2.manifest;$BM/global_english_2.manifest"

SRC="${1:?source xml (relative to dataroot) required}"; shift || true
ONLY=""
if [[ "${1:-}" == "--only" ]]; then ONLY="$2"; fi

export DOTNET_ROLL_FORWARD=LatestMajor DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
REF="$WORK/ref"; NEW="$WORK/new"; DECXML="$WORK/decompiled.xml"

echo "[1/4] compile reference: $SRC"
# -scd makes BAB emit StringHashes.xml (module tags / id strings the binary stores only as one-way hashes),
# which the decompiler needs to round-trip module ids. The subsequent StringHashTable-asset compile step is a
# pre-existing port limitation that exits non-zero AFTER the real assets+manifest are written, so tolerate it
# and verify the manifest below instead of trusting the exit code.
dotnet "$BAB" "$SRC" -dr:"$DR" -od:"$REF" -sp:"$SCHEMA" -rm:"$RM" -sc:false -bc:false -scd:"$WORK/cache" >/dev/null 2>&1 || true
mapfile -t MANIFESTS < <(find "$REF" -name '*.manifest' | sort)
if [[ ${#MANIFESTS[@]} -eq 0 ]]; then echo "  ERROR: reference compile produced no manifest"; exit 1; fi
SH="$WORK/cache/StringHashes.xml"
SHARG=(); [[ -f "$SH" ]] && SHARG=(--stringhashes "$SH")
ONLYARG=(); [[ -n "$ONLY" ]] && ONLYARG=(--only "$ONLY")

echo "[2/4] decompile ${#MANIFESTS[@]} manifest(s) -> $WORK/dec"
mkdir -p "$WORK/dec"
# A source file can compile into several manifests (one per sub-stream); decompile each and recompile all.
n=0
for MF in "${MANIFESTS[@]}"; do
  base="${MF%.manifest}"; ASSETS="$base/assets"
  [[ -d "$ASSETS" ]] || ASSETS="$(dirname "$MF")/assets"
  dotnet "$DEC" decompile "$MF" --assets "$ASSETS" --combined "$WORK/dec/s$n.xml" --schema "$SCHEMA" --rm "$RM" "${SHARG[@]}" "${ONLYARG[@]}"
  n=$((n+1))
done

echo "[3/4] recompile decompiled XML"
for f in "$WORK"/dec/s*.xml; do
  cp "$f" "$WORK/one.xml"
  dotnet "$BAB" "one.xml" -dr:"$WORK" -od:"$NEW" -sp:"$SCHEMA" -rm:"$RM" -sc:false -bc:false >/dev/null 2>&1 || true
done

echo "[4/4] compare buffers"
python3 - "$REF" "$NEW" "$ONLY" <<'PY'
import sys,struct,glob,os
refdir,newdir,only=sys.argv[1],sys.argv[2],sys.argv[3]
def load(p):
    b=open(p,'rb').read()
    tid,inst,th,ih,ids,rds,imps,z=struct.unpack_from('<8I',b,0); o=32
    return (tid,inst),(b[o:o+ids],b[o+ids:o+ids+rds],b[o+ids+rds:o+ids+rds+imps],(ids,rds,imps))
# Enumerate a stream's assets via its MANIFEST(s) — the authoritative stream index — not by globbing .asset
# files on disk (BAB also drops orphan base/dependency .asset files that are not part of any stream).
def index(d):
    m={}
    for mf in glob.glob(os.path.join(d,'**','*.manifest'),recursive=True):
        b=open(mf,'rb').read(); h=struct.unpack_from('<11I',b,4); n=h[2]
        base=mf[:-9]  # strip ".manifest"
        for i in range(n):
            e=48+i*44
            tid,inst,th,ih=struct.unpack_from('<4I',b,e)
            fn=f"{tid:08x}.{th:08x}.{inst:08x}.{ih:08x}.asset"
            for ad in (os.path.join(base,'assets',fn), os.path.join(os.path.dirname(mf),'assets',fn)):
                if os.path.exists(ad):
                    k,v=load(ad); m[k]=(v,ad); break
    return m
ref=index(refdir); new=index(newdir)
total=exact=fail=missing=0; fails=[]
for k,(rv,rp) in ref.items():
    name=os.path.basename(rp)
    total+=1
    if k not in new: missing+=1; fails.append((name,'MISSING in recompile')); continue
    nv,np_=new[k]
    if rv[0]==nv[0] and rv[1]==nv[1] and rv[2]==nv[2]:
        exact+=1
    else:
        fail+=1
        why=[]
        if rv[3]!=nv[3]: why.append(f"sizes ref{rv[3]} new{nv[3]}")
        if rv[0]!=nv[0]:
            for i in range(min(len(rv[0]),len(nv[0]))):
                if rv[0][i]!=nv[0][i]: why.append(f"inst diff@{i} ref{rv[0][i]:02x}/new{nv[0][i]:02x}"); break
            else: why.append(f"inst len ref{len(rv[0])}/new{len(nv[0])}")
        if rv[1]!=nv[1]: why.append("relo differs")
        if rv[2]!=nv[2]: why.append("imp differs")
        fails.append((name,'; '.join(why)))
print(f"  total={total}  byte_exact={exact}  fail={fail}  missing={missing}")
for n,w in fails[:15]: print(f"    FAIL {n}: {w}")
sys.exit(0 if fail==0 and missing==0 else 1)
PY