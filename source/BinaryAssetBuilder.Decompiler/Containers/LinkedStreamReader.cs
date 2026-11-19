using System;
using System.Collections.Generic;
using System.IO;

namespace BinaryAssetBuilder.Decompiler.Containers
{
    // Reads a LINKED stream — a whole compiled asset bundle — rather than the per-asset `.asset` files
    // AssetInput.FromAssetFile handles. A linked stream is a manifest plus three sibling buffers (`.bin`,
    // `.relo`, `.imp`), each a 4-BYTE PREFIX followed by every asset's chunk concatenated in manifest order.
    // We walk the manifest entries and slice each asset's instance/relo/imp out at its cumulative offset.
    //
    // This is the form a real mod (e.g. Second Isomer's `static_mod`, ~44k assets) ships in. Yielding lazily
    // keeps peak memory to the three whole buffers plus the current asset, not 44k live copies.
    public static class LinkedStreamReader
    {
        public static IEnumerable<AssetInput> Read(Manifest m, string binPath, string reloPath, string impPath)
        {
            byte[] bin = File.ReadAllBytes(binPath);
            byte[] relo = File.ReadAllBytes(reloPath);
            byte[] imp = File.ReadAllBytes(impPath);

            int bo = 4, ro = 4, io = 4; // skip the 4-byte prefix on each buffer
            for (int i = 0; i < m.Entries.Length; i++)
            {
                AssetStream.AssetEntry e = m.Entries[i];
                byte[] inst = Slice(bin, bo, e.InstanceDataSize); bo += e.InstanceDataSize;
                byte[] rl = Slice(relo, ro, e.RelocationDataSize); ro += e.RelocationDataSize;
                byte[] ip = Slice(imp, io, e.ImportsDataSize); io += e.ImportsDataSize;

                string full = m.Names[i];
                string id = full != null && full.Contains(':') ? full.Substring(full.IndexOf(':') + 1) : full;

                AssetInput a = AssetInput.FromBuffers(e.TypeId, e.InstanceId, e.TypeHash, e.InstanceHash, id, inst, rl, ip);
                a.References = m.GetAssetReferences(i);
                yield return a;
            }
        }

        private static byte[] Slice(byte[] src, int offset, int length)
        {
            var dst = new byte[length];
            Buffer.BlockCopy(src, offset, dst, 0, length);
            return dst;
        }
    }
}
