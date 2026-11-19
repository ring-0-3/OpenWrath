import struct, sys, os

# Pack files into an EA BIG4 archive. Args: <out.big> <archive_path>=<src_file> [...]
# archive_path uses backslashes as the game expects, e.g. data\static_mod.bin
FOOTER = b'L280\x15\x05\x00\x01'

def pack(outpath, entries):
    # entries: list of (archive_name_str, data_bytes)
    enc = [(n.encode("latin1"), d) for n, d in entries]
    header_size = 16 + sum(8 + len(n) + 1 for n, _ in enc) + len(FOOTER)
    off = header_size
    table = b""
    for n, d in enc:
        table += struct.pack(">II", off, len(d)) + n + b"\x00"
        off += len(d)
    total = header_size + sum(len(d) for _, d in enc)
    blob = b"BIG4" + struct.pack("<I", total) + struct.pack(">I", len(enc)) + struct.pack(">I", header_size) + table + FOOTER
    for _, d in enc:
        blob += d
    open(outpath, "wb").write(blob)
    print(f"wrote {outpath}: {total} bytes, {len(enc)} entries")

if __name__ == "__main__":
    out = sys.argv[1]
    entries = []
    for spec in sys.argv[2:]:
        name, src = spec.split("=", 1)
        entries.append((name, open(src, "rb").read()))
    pack(out, entries)
