#!/usr/bin/env bash
# Corpus round-trip coverage measurement.
#
#   tools/corpus-roundtrip.sh [file1.xml file2.xml ...]   # paths relative to $KW_DATAROOT
#
# For every source XML it: compiles -> decompiles -> recompiles -> byte-compares each asset, then AGGREGATES
# the results PER ASSET TYPE across the whole set: total / byte_exact / fail / missing, with a few first-diff
# samples per failing type. Writes a machine-readable TSV to $CORPUS_OUT (default: a temp file, path printed)
# which tools/coverage-report.py turns into docs/reference/COVERAGE.md.
#
# "Byte-exact" means the decompiled XML recompiled to identical instance/relocation/import bytes — the same
# honest gate as tools/roundtrip.sh, just tallied by type across many files. Run `source tools/dev-env.sh` first.
set -uo pipefail   # deliberately NOT -e: a single file failing must not abort the whole corpus run

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BAB="$ROOT/Debug/BinaryAssetBuilder.dll"
DEC="$ROOT/Debug/bab-decompile.dll"
SCHEMA="${KW_SCHEMA:-$ROOT/schemas/kw/xsd/CnC3Types.xsd}"
DR="${KW_DATAROOT:?set KW_DATAROOT (source tools/dev-env.sh)}"
BM="${KW_BASEMANIFESTS:?set KW_BASEMANIFESTS (source tools/dev-env.sh)}"
RM="$BM/global_common_2.manifest;$BM/static_common_2.manifest;$BM/global_english_2.manifest"
export DOTNET_ROLL_FORWARD=LatestMajor DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1

RESULTS="${CORPUS_OUT:-$(mktemp)}"; : > "$RESULTS"
FILES=("$@")
echo "corpus: ${#FILES[@]} source files; results -> $RESULTS"

ok_files=0; bad_files=0; i=0
for SRC in "${FILES[@]}"; do
  i=$((i+1))
  WORK="$(mktemp -d)"
  REF="$WORK/ref"; NEW="$WORK/new"
  dotnet "$BAB" "$SRC" -dr:"$DR" -od:"$REF" -sp:"$SCHEMA" -rm:"$RM" -sc:false -bc:false -scd:"$WORK/cache" >/dev/null 2>&1 || true
  MF="$(find "$REF" -name '*.manifest' 2>/dev/null | head -1)"
  if [[ -z "$MF" ]]; then echo "  [$i/${#FILES[@]}] SKIP (no manifest): $SRC"; bad_files=$((bad_files+1)); rm -rf "$WORK"; continue; fi
  SH="$WORK/cache/StringHashes.xml"; SHARG=(); [[ -f "$SH" ]] && SHARG=(--stringhashes "$SH")
  mkdir -p "$WORK/dec"; n=0
  for M in $(find "$REF" -name '*.manifest' | sort); do
    base="${M%.manifest}"; ASSETS="$base/assets"; [[ -d "$ASSETS" ]] || ASSETS="$(dirname "$M")/assets"
    dotnet "$DEC" decompile "$M" --assets "$ASSETS" --combined "$WORK/dec/s$n.xml" --schema "$SCHEMA" --rm "$RM" "${SHARG[@]}" >/dev/null 2>&1 || true
    n=$((n+1))
  done
  for f in "$WORK"/dec/s*.xml; do
    [[ -f "$f" ]] || continue
    cp "$f" "$WORK/one.xml"
    dotnet "$BAB" "one.xml" -dr:"$WORK" -od:"$NEW" -sp:"$SCHEMA" -rm:"$RM" -sc:false -bc:false >/dev/null 2>&1 || true
  done
  # Per-asset compare, appending "typeid<TAB>typename<TAB>status<TAB>reason" rows to RESULTS.
  python3 - "$REF" "$NEW" "$RESULTS" <<'PY'
import sys,struct,glob,os
refdir,newdir,results=sys.argv[1],sys.argv[2],sys.argv[3]
def load(p):
    b=open(p,'rb').read(); tid,inst,th,ih,ids,rds,imps,z=struct.unpack_from('<8I',b,0); o=32
    return (tid,inst),(b[o:o+ids],b[o+ids:o+ids+rds],b[o+ids+rds:o+ids+rds+imps])
def index(d):
    m={}; names={}
    for mf in glob.glob(os.path.join(d,'**','*.manifest'),recursive=True):
        b=open(mf,'rb').read(); h=struct.unpack_from('<11I',b,4); nA=h[2]
        base=mf[:-9]
        aro=48+nA*44; nameoff=aro+h[7]+h[8]
        for i in range(nA):
            e=48+i*44; tid,inst,th,ih=struct.unpack_from('<4I',b,e); noff=struct.unpack_from('<i',b,e+24)[0]
            p=nameoff+noff; en=b.index(b'\x00',p) if p<len(b) else p
            nm=b[p:en].decode('latin1','replace'); tn=nm.split(':')[0] if ':' in nm else ''
            fn=f"{tid:08x}.{th:08x}.{inst:08x}.{ih:08x}.asset"
            for ad in (os.path.join(base,'assets',fn),os.path.join(os.path.dirname(mf),'assets',fn)):
                if os.path.exists(ad):
                    k,v=load(ad); m[k]=v; names[k]=tn; break
    return m,names
ref,names=index(refdir); new,_=index(newdir)
with open(results,'a') as out:
    for k,rv in ref.items():
        tid,inst=k; tn=names.get(k,'')
        if k not in new: out.write(f"{tid:08x}\t{tn}\tmissing\t\n"); continue
        nv=new[k]
        if rv==nv: out.write(f"{tid:08x}\t{tn}\texact\t\n")
        else:
            reason=""
            if rv[0]!=nv[0]:
                for j in range(min(len(rv[0]),len(nv[0]))):
                    if rv[0][j]!=nv[0][j]: reason=f"inst@{j}"; break
                else: reason=f"instlen {len(rv[0])}/{len(nv[0])}"
            elif rv[1]!=nv[1]: reason="relo"
            elif rv[2]!=nv[2]: reason="imp"
            out.write(f"{tid:08x}\t{tn}\tfail\t{reason}\n")
PY
  ok_files=$((ok_files+1))
  rm -rf "$WORK"
  [[ $((i % 10)) -eq 0 ]] && echo "  ...$i/${#FILES[@]} files"
done
echo "done: $ok_files files measured, $bad_files skipped. results=$RESULTS"
