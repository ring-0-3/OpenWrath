using System;

namespace BinaryAssetBuilder.Decompiler.Containers
{
    // The single C# authority for "what is a RefPack stream". EA RefPack (QFS) data begins with a 2-byte
    // signature: [flags][0xFB]. The SIGNATURE is the second byte (0xFB); the first byte is a flags byte that
    // legitimately varies across KW data — 0x10, 0x11 (bit 0x01 → 4-byte size fields), and the EA-KW 0x90
    // variant (bit 0x80) seen on static_common.bin (0x91 = both bits). Discriminating on the flags byte is
    // overfitting to sampled values and lets lawful variants slip through (finding 0012). The authoritative
    // Python rule is identical (modkit/lib/refpack.py: magic = data[1]; must be 0xFB).
    public static class RefPack
    {
        public static bool IsRefPack(ReadOnlySpan<byte> data) => data.Length >= 2 && data[1] == 0xFB;
    }
}
