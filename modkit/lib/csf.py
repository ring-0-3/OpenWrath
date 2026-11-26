#!/usr/bin/env python3
# Read a SAGE/KW compiled string table (`.csf`) and emit the plaintext `.str` source the engine also accepts.
# Lets a mod ship a `data\cnc3.str` with a few edited labels (unit names, tooltips) WITHOUT a CSF compiler and
# WITHOUT editing the BYO game file. The engine loads ONE string table, so a mod must ship the COMPLETE table
# (base labels + edits) -> the strings big is LOCAL-ONLY (it embeds EA's shipped strings; same posture as the
# 0017 overlay drop-in). Reverse-figured + verified against the shipped cnc3.csf (7395 labels).
#
# CSF binary layout: magic ' FSC' (0x20 'F' 'S' 'C'), then <u32 version, numLabels, numStrings, unused, langId>.
#   Per label: tag ' LBL', <u32 numStrings, labelLen>, label name (latin1). Per value: tag ' RTS' (STR) or
#   'WRTS' (STRW), <u32 charLen>, string as bitwise-NOT UTF-16LE; STRW adds <u32 extraLen> + latin1 extra.
# (Lang-big copies are RefPack-compressed — reuse refpack.py / IsRefPack, finding 0012 — before parsing those.)
#
# usage: csf.py <base.csf> <out.str> [LABEL=VALUE ...]   (edits are case-insensitive on the label)
import sys, os, struct


def read_csf(path):
    """Return [(label_name, first_string_value), ...] in file order."""
    d = open(path, "rb").read()
    if d[:4] != b" FSC":
        raise ValueError(f"not a CSF (magic {d[:4]!r}); if RefPack-compressed, decompress first")
    _ver, nlbl, _nstr, _u, _lang = struct.unpack_from("<5I", d, 4)
    off = 24
    out = []
    for _ in range(nlbl):
        if d[off:off + 4] != b" LBL":
            raise ValueError(f"expected ' LBL' at {off}, got {d[off:off+4]!r}")
        off += 4
        nstrings, lbllen = struct.unpack_from("<2I", d, off); off += 8
        name = d[off:off + lbllen].decode("latin1"); off += lbllen
        value = ""
        for s in range(nstrings):
            tag = d[off:off + 4]; off += 4
            charlen = struct.unpack_from("<I", d, off)[0]; off += 4
            raw = d[off:off + charlen * 2]; off += charlen * 2
            txt = bytes(b ^ 0xFF for b in raw).decode("utf-16-le", "replace")
            if tag == b"WRTS":
                extralen = struct.unpack_from("<I", d, off)[0]; off += 4
                off += extralen
            if s == 0:
                value = txt
        out.append((name, value))
    return out


def to_str_bytes(labels, edits):
    """Serialize labels to `.str` bytes, applying `edits` (dict, case-insensitive on the label key).
    Returns (bytes, applied) where applied = [(label, old, new), ...]."""
    up = {k.upper(): v for k, v in (edits or {}).items()}
    applied = []
    blocks = []
    for name, value in labels:
        new = up.get(name.upper())
        if new is not None:
            applied.append((name, value, new))
            value = new
        value = value.replace("\r", "").replace("\n", "|")   # in-string line breaks -> '|'
        blocks.append(f'{name}\r\n\t"{value}"\r\nEnd\r\n')
    return ("\r\n".join(blocks) + "\r\n").encode("latin1", "replace"), applied


def main():
    if len(sys.argv) < 3:
        sys.exit("usage: csf.py <base.csf> <out.str> [LABEL=VALUE ...]")
    base, out = sys.argv[1], sys.argv[2]
    edits = dict(a.split("=", 1) for a in sys.argv[3:])
    labels = read_csf(base)
    data, applied = to_str_bytes(labels, edits)
    open(out, "wb").write(data)
    print(f"read {len(labels)} labels; applied {len(applied)} edit(s) -> {out}")
    for name, old, new in applied:
        print(f"   {name}: {old!r} -> {new!r}")


if __name__ == "__main__":
    main()
