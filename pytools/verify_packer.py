import struct, sys, hashlib

# Round-trip test: read every entry from a real EA BIG, repack with OUR writer,
# compare against the original bytes to confirm our format is byte-accurate.

def read_entries(path):
    with open(path, "rb") as f:
        raw = f.read()
    magic = raw[:4]
    assert magic in (b"BIGF", b"BIG4"), magic
    arch_size = struct.unpack_from("<I", raw, 4)[0]
    num = struct.unpack_from(">I", raw, 8)[0]
    hdr = struct.unpack_from(">I", raw, 12)[0]
    off = 16
    files = []
    for _ in range(num):
        foff, fsize = struct.unpack_from(">II", raw, off); off += 8
        end = raw.find(b"\x00", off); nm = raw[off:end]; off = end + 1
        files.append((nm, raw[foff:foff+fsize]))
    return raw, arch_size, num, hdr, off, files  # off = end of name table

def pack_minimal(files):
    header_size = 16 + sum(8 + len(nm) + 1 for nm, _ in files)
    off = header_size; table = b""
    for nm, data in files:
        table += struct.pack(">II", off, len(data)) + nm + b"\x00"; off += len(data)
    total = header_size + sum(len(d) for _, d in files)
    blob = b"BIG4" + struct.pack("<I", total) + struct.pack(">I", len(files)) + struct.pack(">I", header_size) + table
    for _, d in files: blob += d
    return blob

p = sys.argv[1]
raw, arch_size, num, hdr, name_end, files = read_entries(p)
print(f"original: size={arch_size} entries={num} header_size={hdr} name_table_ends_at={name_end}")
print(f"  gap between name-table end ({name_end}) and first-data/header_size ({hdr}) = {hdr-name_end} bytes")
if hdr > name_end:
    print(f"  footer bytes: {raw[name_end:hdr]!r}")
mine = pack_minimal(files)
print(f"mine: size={len(mine)} header_size={16+sum(8+len(nm)+1 for nm,_ in files)}")
print(f"identical? {mine == raw}")
if mine != raw:
    # find first differing byte
    for i in range(min(len(mine), len(raw))):
        if mine[i] != raw[i]:
            print(f"  first diff at byte {i}: mine={mine[i]:#04x} orig={raw[i]:#04x}")
            print(f"  context orig[{i}:{i+16}]={raw[i:i+16]!r}")
            break
    print(f"  len mine={len(mine)} orig={len(raw)}")
