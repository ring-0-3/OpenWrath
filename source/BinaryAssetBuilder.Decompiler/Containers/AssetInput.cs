using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;

namespace BinaryAssetBuilder.Decompiler.Containers
{
    // One asset ready to be decoded: its identity + the three on-disk buffers, with the relocation and
    // import "from"-offset lists parsed into fast lookup sets.
    //
    // On disk (see Relo.Tracker.MakeRelocatable), within InstanceData:
    //   * a 4-byte slot whose offset is in ReloFroms holds the asset-local byte offset of a target block
    //     (an internal pointer to follow);
    //   * a 4-byte slot whose offset is in ImportFroms holds a cross-asset reference id (resolved to a name
    //     in Phase 3);
    //   * a slot that is in neither and reads 0 is a null pointer (empty list / string / absent reference).
    // The relocation and import buffers are each a uint32 array of "from" offsets terminated by 0xFFFFFFFF.
    public sealed class AssetInput
    {
        public uint TypeId;
        public uint InstanceId;
        public uint TypeHash;
        public uint InstanceHash;
        public string Name;          // authored id (from the manifest), null if unknown

        public byte[] Instance;
        public HashSet<uint> ReloFroms;
        public HashSet<uint> ImportFroms;

        // The asset's ReferencedInstances list (from the manifest's AssetReferenceBuffer), in index order.
        // An AssetReference import slot stores an INDEX into this array; References[index] = (TypeId, InstanceId)
        // of the referenced asset, which the ReferenceResolver maps back to an authored name.
        public (uint TypeId, uint InstanceId)[] References = Array.Empty<(uint, uint)>();

        // Original relocation/import byte buffers (kept for raw round-trip verification in Phase 0).
        public byte[] RelocationBuffer;
        public byte[] ImportsBuffer;

        public static AssetInput FromBuffers(
            uint typeId, uint instanceId, uint typeHash, uint instanceHash, string name,
            byte[] instance, byte[] relo, byte[] imp)
        {
            return new AssetInput
            {
                TypeId = typeId,
                InstanceId = instanceId,
                TypeHash = typeHash,
                InstanceHash = instanceHash,
                Name = name,
                Instance = instance,
                RelocationBuffer = relo ?? Array.Empty<byte>(),
                ImportsBuffer = imp ?? Array.Empty<byte>(),
                ReloFroms = ParseOffsetList(relo),
                ImportFroms = ParseOffsetList(imp),
            };
        }

        // Load a standalone BinaryAssetBuilder `.asset` file: 32B AssetHeader + instance + relo + imp.
        public static AssetInput FromAssetFile(string path, string name = null)
        {
            byte[] b = File.ReadAllBytes(path);
            uint typeId = BitConverter.ToUInt32(b, 0);
            uint instanceId = BitConverter.ToUInt32(b, 4);
            uint typeHash = BitConverter.ToUInt32(b, 8);
            uint instanceHash = BitConverter.ToUInt32(b, 12);
            int instSize = BitConverter.ToInt32(b, 16);
            int reloSize = BitConverter.ToInt32(b, 20);
            int impSize = BitConverter.ToInt32(b, 24);
            // b[28..32] = Zero
            int o = 32;
            byte[] instance = Slice(b, o, instSize); o += instSize;
            byte[] relo = Slice(b, o, reloSize); o += reloSize;
            byte[] imp = Slice(b, o, impSize);
            return FromBuffers(typeId, instanceId, typeHash, instanceHash, name, instance, relo, imp);
        }

        private static byte[] Slice(byte[] src, int offset, int length)
        {
            var dst = new byte[length];
            Buffer.BlockCopy(src, offset, dst, 0, length);
            return dst;
        }

        // Parse a 0xFFFFFFFF-terminated uint32 "from"-offset array into a set.
        private static HashSet<uint> ParseOffsetList(byte[] buffer)
        {
            var set = new HashSet<uint>();
            if (buffer == null)
            {
                return set;
            }
            for (int i = 0; i + 4 <= buffer.Length; i += 4)
            {
                uint v = BitConverter.ToUInt32(buffer, i);
                if (v == 0xFFFFFFFFu)
                {
                    break;
                }
                set.Add(v);
            }
            return set;
        }

        // Read the 4-byte value stored at an instance offset (the pointer-offset or import id the writer laid down).
        // Bounds-checked: a read past the instance end means the walk has desynced (e.g. the on-disk layout of
        // this asset's type differs from our schema). We raise DesyncException so the caller can fall back to a
        // raw block instead of crashing — the robustness property a schema-walking decompiler lacks.
        public uint ReadSlot(uint offset)
        {
            if ((long)offset + 4 > Instance.Length)
            {
                throw new DesyncException($"read@{offset} past instance end ({Instance.Length})");
            }
            return BitConverter.ToUInt32(Instance, (int)offset);
        }

        // Render a contiguous array of `count` little-endian uint16s at `offset` as a space-separated decimal list
        // (range-checked). Shared single source for the readers' ushort-list rendering (W3DAnimation's
        // FrameAndBinaryFlag, W3DMesh's Bones) so the spelling can't drift between them (invariant 3).
        public string RenderUShortList(uint offset, uint count, string what)
        {
            if (count == 0)
            {
                return string.Empty;
            }
            CheckRange(offset, (long)count * 2, what);
            var sb = new StringBuilder();
            for (uint i = 0; i < count; i++)
            {
                if (i > 0) sb.Append(' ');
                sb.Append(BitConverter.ToUInt16(Instance, (int)(offset + i * 2)).ToString(CultureInfo.InvariantCulture));
            }
            return sb.ToString();
        }

        // Validate that [offset, offset+len) lies inside the instance; throw a labelled DesyncException if not.
        // Used before following a list/string/blob/pointer-array to a target region, so an implausible count or
        // offset becomes a clean desync rather than an out-of-bounds crash or a huge allocation.
        public void CheckRange(uint offset, long len, string what)
        {
            if (len < 0 || (long)offset + len > Instance.Length)
            {
                throw new DesyncException($"{what}@{offset} len {len} past instance end ({Instance.Length})");
            }
        }
    }

    // Raised when the binary read-walk steps outside the asset's instance data — the signal that the on-disk
    // layout did not match the schema we walked it with (a foreign/mismatched-schema asset). The decompiler
    // catches it per asset and emits a labelled <RawAsset> fallback, so one bad asset never aborts the stream.
    public sealed class DesyncException : Exception
    {
        public DesyncException(string message) : base(message) { }
    }
}
