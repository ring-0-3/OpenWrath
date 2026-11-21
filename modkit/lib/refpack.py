import sys

# EA RefPack (a.k.a. "refpack"/QFS) decompressor. Used for compressed entries inside SAGE .big
# files (e.g. the base static_common.manifest/.bin). Header: [flags][0xFB][size field(s)],
# then control-byte-driven literal runs + back-references.
#
# Two flag-byte conventions appear in KW data and must both be handled:
#   * Classic refpack: bit 0x01 selects 4-byte (vs 3-byte) size fields; bit 0x80 means a
#     COMPRESSED-size field precedes the uncompressed-size field (and must be skipped).
#   * EA KW "0x90" variant (as on static_common.bin): bit 0x80 set, bit 0x01 clear, but here the
#     stream carries ONLY a single 4-byte big-endian UNCOMPRESSED size and NO compressed-size
#     field, so the actual compressed data starts at byte offset 6 (2 signature + 4 size). The
#     classic reading (size_len=3, skip a 3-byte compressed size) is wrong for this variant.

def decompress(data):
    pos = 0
    flags = data[pos]; magic = data[pos + 1]; pos += 2
    if magic != 0xFB:
        raise ValueError(f"not refpack (magic={magic:#x})")
    if flags & 0x80:
        # EA KW 0x90 variant: single 4-byte uncompressed size, no compressed-size prefix.
        size_len = 4
        skip_compressed = False
    else:
        size_len = 4 if (flags & 0x01) else 3
        skip_compressed = False
    if skip_compressed:
        pos += size_len
    unsize = 0
    for _ in range(size_len):
        unsize = (unsize << 8) | data[pos]; pos += 1

    out = bytearray()
    while pos < len(data):
        ctrl = data[pos]; pos += 1
        if ctrl < 0x80:                      # 2-byte form
            a = data[pos]; pos += 1
            proc = ctrl & 0x03
            ref = ((ctrl & 0x1C) >> 2) + 3
            dist = ((ctrl & 0x60) << 3) + a + 1
        elif ctrl < 0xC0:                    # 3-byte form
            a = data[pos]; b = data[pos + 1]; pos += 2
            proc = (a >> 6) & 0x03
            ref = (ctrl & 0x3F) + 4
            dist = ((a & 0x3F) << 8) + b + 1
        elif ctrl < 0xE0:                    # 4-byte form
            a = data[pos]; b = data[pos + 1]; c = data[pos + 2]; pos += 3
            proc = ctrl & 0x03
            ref = ((ctrl & 0x0C) << 6) + c + 5
            dist = ((ctrl & 0x10) << 12) + (a << 8) + b + 1
        elif ctrl < 0xFC:                    # literal run only
            proc = ((ctrl & 0x1F) << 2) + 4
            ref = 0; dist = 0
        else:                                # 0xFC-0xFF: final literals, then stop
            proc = ctrl & 0x03
            ref = 0; dist = 0
        # proc literal bytes copied straight from input
        out += data[pos:pos + proc]; pos += proc
        # ref bytes copied from already-emitted output at `dist` back (may overlap)
        for _ in range(ref):
            out.append(out[-dist])
        if ctrl >= 0xFC:
            break
    return bytes(out), unsize

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    raw = open(src, "rb").read()
    out, unsize = decompress(raw)
    open(dst, "wb").write(out)
    print(f"decompressed {len(raw)} -> {len(out)} bytes (header said {unsize}); first bytes: {out[:8].hex()}")
