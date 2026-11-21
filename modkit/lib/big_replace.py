#!/usr/bin/env python3
# Stream-based EA BIG4 entry replacer.
#
# Reads an original BIG4 archive and writes a new one where a named set of entries are
# swapped for replacement files on disk. Every other entry is copied byte-for-byte from
# the original. Offsets and the archive total size are recomputed; the original header
# layout (entry-name table + trailing footer) is preserved exactly because entry NAMES are
# unchanged -> header_size is unchanged -> the real EA footer (whatever 8 bytes follow the
# name table, e.g. b'L219\x00\x00\x00\x00' on this archive) is carried over verbatim.
#
# BIG4 layout (see biglist.py / pack_big.py):
#   "BIG4" | u32 LE total size | u32 BE entry count | u32 BE header size
#   entries[ u32 BE offset, u32 BE size, name\0 ] ... | footer (bytes up to header_size)
#   then raw data, contiguous, starting at header_size.
#
# usage: big_replace.py <orig.big> <out.big> name1=repl1 [name2=repl2 ...]
#   name uses backslashes exactly as stored, e.g. 'data\static_mod.bin'
import struct, sys, os

CHUNK = 8 * 1024 * 1024

def main():
    orig, out = sys.argv[1], sys.argv[2]
    repl = {}
    for spec in sys.argv[3:]:
        name, src = spec.split("=", 1)
        repl[name.lower()] = src

    with open(orig, "rb") as f:
        head = f.read(16)
        assert head[:4] == b"BIG4", head[:4]
        num = struct.unpack_from(">I", head, 8)[0]
        header_size = struct.unpack_from(">I", head, 12)[0]
        header = bytearray(head + f.read(header_size - 16))  # full header region (table + footer)

    # Parse table: record field positions + orig offset/size + name.
    entries = []  # (off_field_pos, size_field_pos, orig_offset, orig_size, name)
    pos = 16
    for _ in range(num):
        off_pos = pos
        size_pos = pos + 4
        foff, fsize = struct.unpack_from(">II", header, pos)
        pos += 8
        end = header.find(b"\x00", pos)
        name = header[pos:end].decode("latin1")
        pos = end + 1
        entries.append([off_pos, size_pos, foff, fsize, name])

    # Resolve new sizes for replaced entries.
    matched = set()
    for e in entries:
        key = e[4].lower()
        if key in repl:
            e.append(repl[key])                 # e[5] = src path
            e[3] = os.path.getsize(repl[key])   # new size overrides orig size
            matched.add(key)
        else:
            e.append(None)
    missing = set(repl) - matched
    if missing:
        raise SystemExit(f"ERROR: replacement names not found in archive: {missing}")

    # Assign new offsets in PHYSICAL order (sorted by original offset; archive is contiguous),
    # then patch each entry's offset+size fields in the in-memory header.
    cursor = header_size
    phys = sorted(entries, key=lambda e: e[2])
    for e in phys:
        new_off = cursor
        struct.pack_into(">II", header, e[0], new_off, e[3])  # off_pos holds offset, +4 holds size
        e.append(new_off)                                     # e[6] = new offset
        cursor += e[3]
    total = cursor
    struct.pack_into("<I", header, 4, total)  # LE total archive size

    # Write output: patched header, then data in physical order.
    with open(orig, "rb") as fin, open(out, "wb") as fout:
        fout.write(header)
        written = header_size
        for e in phys:
            assert e[6] == written, (e[4], e[6], written)
            if e[5] is not None:  # replaced -> copy from src file
                with open(e[5], "rb") as rf:
                    while True:
                        b = rf.read(CHUNK)
                        if not b:
                            break
                        fout.write(b)
                        written += len(b)
            else:  # copy orig_size bytes from original at orig_offset
                fin.seek(e[2])
                remaining = e[3]
                while remaining > 0:
                    b = fin.read(min(CHUNK, remaining))
                    if not b:
                        raise SystemExit(f"ERROR: short read for {e[4]}")
                    fout.write(b)
                    written += len(b)
                    remaining -= len(b)
        assert written == total, (written, total)
        # Durability: flush every byte to disk before we claim success, so a caller can never install a
        # partially-flushed (truncated) archive. (A past truncation shipped a half-written big because the
        # bytes were only in the page cache when the next step copied it.)
        fout.flush()
        os.fsync(fout.fileno())

    actual = os.path.getsize(out)
    if actual != total:
        raise SystemExit(f"ERROR: output big is {actual} bytes but should be {total} — refusing (truncated write)")

    print(f"wrote {out}")
    print(f"  entries={num} header_size={header_size} total={total} (orig_total patched)")
    print(f"  replaced: {sorted(matched)}")

if __name__ == "__main__":
    main()
