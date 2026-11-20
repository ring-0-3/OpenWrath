#!/usr/bin/env python3
# Merge many per-file StringHashes.xml tables into one master table.
#
#   tools/merge-stringhashes.py <out.xml> <root-dir> [<root-dir> ...]
#
# Each <root-dir> is searched recursively for files named StringHashes.xml (the tables the compiler emits via
# -scd:<dir>). Entries are <StringAndHash Hash="<uint>" Text="<string>"/> keyed on Hash. Because a single
# compiler process overwrites rather than accumulates its table, a full-corpus table is built by compiling
# each source file to its own output dir and unioning the results here.
#
# The union keeps the FIRST text seen for a hash (inputs are visited in sorted path order, so the choice is
# deterministic). If a later file maps the same hash to a DIFFERENT text that is a genuine hash collision in
# the source data; it is logged to stderr and counted. Output is the VERSION5 single-TheStringTable format,
# sorted by numeric hash for a stable diff.
import sys, os, glob
import xml.etree.ElementTree as ET

NS = "uri:ea.com:eala:asset"

def main():
    if len(sys.argv) < 3:
        sys.stderr.write("usage: merge-stringhashes.py <out.xml> <root-dir> [<root-dir> ...]\n")
        return 2
    out = sys.argv[1]
    roots = sys.argv[2:]

    tables = []
    for root in roots:
        if os.path.isfile(root):
            tables.append(root)
        else:
            tables.extend(glob.glob(os.path.join(root, "**", "StringHashes.xml"), recursive=True))
    tables = sorted(set(tables))

    merged = {}          # hash(int) -> text(str)
    collisions = 0
    files_with_entries = 0
    total_seen = 0
    for t in tables:
        try:
            tree = ET.parse(t)
        except ET.ParseError as e:
            sys.stderr.write(f"WARN: skip unparseable {t}: {e}\n")
            continue
        n_here = 0
        for el in tree.iter():
            tag = el.tag.split('}')[-1]
            if tag != "StringAndHash":
                continue
            h = el.get("Hash")
            txt = el.get("Text")
            if h is None or txt is None:
                continue
            try:
                hi = int(h)
            except ValueError:
                continue
            total_seen += 1
            n_here += 1
            if hi in merged:
                if merged[hi] != txt:
                    collisions += 1
                    sys.stderr.write(
                        f"COLLISION hash={hi}: keep '{merged[hi]}' drop '{txt}' (from {t})\n")
            else:
                merged[hi] = txt
        if n_here:
            files_with_entries += 1

    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        f.write(f'<AssetDeclaration xmlns="{NS}">\n')
        f.write('  <StringHashTable id="TheStringTable">\n')
        for hi in sorted(merged):
            txt = (merged[hi].replace("&", "&amp;").replace('"', "&quot;")
                   .replace("<", "&lt;").replace(">", "&gt;"))
            f.write(f'    <StringAndHash Hash="{hi}" Text="{txt}" />\n')
        f.write('  </StringHashTable>\n')
        f.write('</AssetDeclaration>\n')

    sys.stderr.write(
        f"merged {len(merged)} unique hashes from {files_with_entries}/{len(tables)} tables "
        f"({total_seen} entries seen, {collisions} collisions) -> {out}\n")
    return 0

if __name__ == "__main__":
    sys.exit(main())
