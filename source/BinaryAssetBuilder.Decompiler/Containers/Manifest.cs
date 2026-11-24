using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using AssetStream;

namespace BinaryAssetBuilder.Decompiler.Containers
{
    // Reads a SAGE/KW v5 asset *manifest* and the three parallel chunk buffers (instance/relo/imports),
    // whether they are laid out as a single linked stream (static_mod.bin/.relo/.imp, each with a 4-byte
    // prefix and all assets concatenated in manifest order) or as per-asset `.asset` files in an `assets/`
    // directory (BinaryAssetBuilder `-ls:false` output; each file = 32B AssetHeader + instance + relo + imp).
    //
    // This is the C# port of the hand-written Python parsers in ~/cnc-kw-modtools (manifest_names.py /
    // extract_asset.py); the manifest struct fields mirror AssetStream.ManifestHeader / AssetEntry exactly.
    public sealed class Manifest
    {
        public const int HeaderSize = 48;   // 4 (flags+version) + 11 * 4
        public const int EntrySize = 44;    // 11 * 4 (VERSION5: no Tokenized field)

        public bool IsBigEndian;
        public bool IsLinked;
        public ushort Version;
        public uint AssetCount;
        public uint AssetReferenceBufferSize;
        public uint ReferenceManifestNameBufferSize;
        public uint AssetNameBufferSize;
        public uint SourceFileNameBufferSize;

        public AssetEntry[] Entries;
        public string[] Names;         // authored name per entry (from the AssetNameBuffer)
        public string[] SourceNames;   // source .xml per entry (from the SourceFileNameBuffer)

        // Raw buffer start offsets within the manifest file.
        private int _assetRefBufOffset;
        private int _assetNameBufOffset;
        private byte[] _raw;

        public static Manifest Load(string manifestPath)
        {
            byte[] bytes = File.ReadAllBytes(manifestPath);
            var m = new Manifest { _raw = bytes };
            m.Parse();
            return m;
        }

        private void Parse()
        {
            // Shipped stream manifests are often RefPack-compressed. RefPack is identified by its SECOND byte
            // (0xFB signature); the first byte is a flags byte that legitimately varies (0x10/0x11/0x90/0x91).
            // A compressed manifest's non-zero first byte would otherwise trip the little-endian check below and
            // be misreported as an "Xbox360 big-endian" manifest — a misleading dead end. Detect it on the
            // signature (not one sampled flags value — see docs/findings/0012) and name the real cause: it needs
            // decompressing first.
            if (RefPack.IsRefPack(_raw))
            {
                throw new NotSupportedException(
                    "This manifest is RefPack-compressed (0xFB signature), not a raw manifest — decompress it first. " +
                    "It is NOT an Xbox360/big-endian manifest.");
            }
            IsBigEndian = _raw[0] != 0;
            IsLinked = _raw[1] != 0;
            if (IsBigEndian)
            {
                throw new NotSupportedException("Big-endian (Xbox360) manifests are out of scope for Linux KW modding.");
            }
            Version = BitConverter.ToUInt16(_raw, 2);
            uint[] h = new uint[11];
            for (int i = 0; i < 11; i++)
            {
                h[i] = BitConverter.ToUInt32(_raw, 4 + i * 4);
            }
            AssetCount = h[2];
            AssetReferenceBufferSize = h[7];
            ReferenceManifestNameBufferSize = h[8];
            AssetNameBufferSize = h[9];
            SourceFileNameBufferSize = h[10];

            int n = (int)AssetCount;
            Entries = new AssetEntry[n];
            Names = new string[n];
            SourceNames = new string[n];

            for (int i = 0; i < n; i++)
            {
                int b = HeaderSize + i * EntrySize;
                Entries[i] = new AssetEntry
                {
                    TypeId = BitConverter.ToUInt32(_raw, b + 0),
                    InstanceId = BitConverter.ToUInt32(_raw, b + 4),
                    TypeHash = BitConverter.ToUInt32(_raw, b + 8),
                    InstanceHash = BitConverter.ToUInt32(_raw, b + 12),
                    AssetReferenceOffset = BitConverter.ToInt32(_raw, b + 16),
                    AssetReferenceCount = BitConverter.ToInt32(_raw, b + 20),
                    NameOffset = BitConverter.ToInt32(_raw, b + 24),
                    SourceFileNameOffset = BitConverter.ToInt32(_raw, b + 28),
                    InstanceDataSize = BitConverter.ToInt32(_raw, b + 32),
                    RelocationDataSize = BitConverter.ToInt32(_raw, b + 36),
                    ImportsDataSize = BitConverter.ToInt32(_raw, b + 40),
                };
            }

            _assetRefBufOffset = HeaderSize + n * EntrySize;
            int refManNameOffset = _assetRefBufOffset + (int)AssetReferenceBufferSize;
            _assetNameBufOffset = refManNameOffset + (int)ReferenceManifestNameBufferSize;
            int srcNameBufOffset = _assetNameBufOffset + (int)AssetNameBufferSize;

            for (int i = 0; i < n; i++)
            {
                Names[i] = ReadCString(_assetNameBufOffset + Entries[i].NameOffset);
                SourceNames[i] = ReadCString(srcNameBufOffset + Entries[i].SourceFileNameOffset);
            }
        }

        private string ReadCString(int offset)
        {
            if (offset < 0 || offset >= _raw.Length)
            {
                return null;
            }
            int end = offset;
            while (end < _raw.Length && _raw[end] != 0)
            {
                end++;
            }
            return Encoding.ASCII.GetString(_raw, offset, end - offset);
        }

        // The 8-byte asset references for entry i: pairs of (TypeId, InstanceId). Used in Phase 3 to resolve
        // imports back to authored names.
        public (uint TypeId, uint InstanceId)[] GetAssetReferences(int entryIndex)
        {
            AssetEntry e = Entries[entryIndex];
            var result = new (uint, uint)[e.AssetReferenceCount];
            int baseOff = _assetRefBufOffset + e.AssetReferenceOffset;
            for (int i = 0; i < e.AssetReferenceCount; i++)
            {
                uint t = BitConverter.ToUInt32(_raw, baseOff + i * 8);
                uint inst = BitConverter.ToUInt32(_raw, baseOff + i * 8 + 4);
                result[i] = (t, inst);
            }
            return result;
        }
    }
}
