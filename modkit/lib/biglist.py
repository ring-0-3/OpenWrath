import struct, sys

# EA BIG (BIGF / BIG4) archive lister.
# Layout:
#   4s  magic ("BIGF" or "BIG4")
#   u32 LE archive size
#   u32 BE number of entries
#   u32 BE header size (offset to first data)
#   entries: u32 BE offset, u32 BE size, null-terminated name

def read_big(path, limit=60, name_filter=None):
    with open(path, "rb") as f:
        data = f.read(1_000_000)  # header region is small; names live near the front
    magic = data[:4]
    if magic not in (b"BIGF", b"BIG4"):
        print(f"  NOT a BIG archive (magic={magic!r})")
        return
    arch_size = struct.unpack_from("<I", data, 4)[0]
    num = struct.unpack_from(">I", data, 8)[0]
    hdr = struct.unpack_from(">I", data, 12)[0]
    print(f"  magic={magic.decode()} entries={num} header_size={hdr} archive_size={arch_size}")
    off = 16
    shown = 0
    exts = {}
    for i in range(num):
        if off + 8 > len(data):
            print("  (header beyond read window; stopping name scan)")
            break
        foff, fsize = struct.unpack_from(">II", data, off)
        off += 8
        end = data.find(b"\x00", off)
        nm = data[off:end].decode("latin1", "replace")
        off = end + 1
        ext = nm.rsplit(".", 1)[-1].lower() if "." in nm else "(none)"
        exts[ext] = exts.get(ext, 0) + 1
        if name_filter:
            if name_filter.lower() in nm.lower() and shown < limit:
                print(f"    {fsize:>10}  {nm}")
                shown += 1
        elif shown < limit:
            print(f"    {fsize:>10}  {nm}")
            shown += 1
    print(f"  extension histogram: {dict(sorted(exts.items(), key=lambda x:-x[1]))}")

if __name__ == "__main__":
    path = sys.argv[1]
    nf = sys.argv[2] if len(sys.argv) > 2 else None
    read_big(path, name_filter=nf)
