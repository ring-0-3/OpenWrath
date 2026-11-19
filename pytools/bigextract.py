import struct, sys, os

# Extract named files from an EA BIG4 archive (raw-stored entries).
def entries(path):
    with open(path, "rb") as f:
        head = f.read(16)
        magic = head[:4]
        assert magic in (b"BIGF", b"BIG4"), magic
        num = struct.unpack_from(">I", head, 8)[0]
        hdr = struct.unpack_from(">I", head, 12)[0]
        tbl = f.read(hdr - 16)
    off = 0
    out = []
    for _ in range(num):
        foff, fsize = struct.unpack_from(">II", tbl, off)
        off += 8
        end = tbl.find(b"\x00", off)
        nm = tbl[off:end].decode("latin1")
        off = end + 1
        out.append((nm, foff, fsize))
    return out

def extract(path, needle, outdir):
    os.makedirs(outdir, exist_ok=True)
    with open(path, "rb") as f:
        for nm, foff, fsize in entries(path):
            if needle.lower() in nm.lower():
                f.seek(foff)
                data = f.read(fsize)
                base = os.path.basename(nm.replace("\\", "/"))
                dst = os.path.join(outdir, base)
                with open(dst, "wb") as o:
                    o.write(data)
                print(f"extracted {nm} ({fsize} bytes) -> {dst}")

if __name__ == "__main__":
    bigpath, needle, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
    extract(bigpath, needle, outdir)
