using System.Collections.Generic;
using BinaryAssetBuilder.Decompiler.Containers;

namespace BinaryAssetBuilder.Decompiler
{
    // Maps a referenced asset's identity back to its authored instance name. References in the binary are
    // stored as ids (an AssetReference import resolves via the asset's AssetReferenceBuffer to a
    // (TypeId, InstanceId); a TypedAssetId stores FastHash(name.ToLower()) == the referenced InstanceId).
    // To emit XML that recompiles byte-exact we must turn those ids back into the NAME the compiler will
    // re-hash — so we index every asset name the toolchain can see: the stream being decompiled plus the
    // base-game "reference manifests" (the same set the compiler's -rm uses), which do carry names.
    //
    // This is the lossless half WrathEd lacks: it blanked cross-stream references it could not name.
    public sealed class ReferenceResolver
    {
        private readonly Dictionary<(uint TypeId, uint InstanceId), string> _byTypeInstance = new();
        private readonly Dictionary<uint, string> _byInstance = new();

        public static ReferenceResolver Build(IEnumerable<Manifest> manifests)
        {
            var r = new ReferenceResolver();
            foreach (Manifest m in manifests)
            {
                if (m != null)
                {
                    r.Add(m);
                }
            }
            return r;
        }

        private void Add(Manifest m)
        {
            for (int i = 0; i < m.Entries.Length; i++)
            {
                string full = m.Names[i];
                if (string.IsNullOrEmpty(full))
                {
                    continue;
                }
                // Manifest names are "TypeName:InstanceName"; the authored reference uses the instance part.
                string inst = full.Contains(':') ? full.Substring(full.IndexOf(':') + 1) : full;
                uint t = m.Entries[i].TypeId;
                uint id = m.Entries[i].InstanceId;
                _byTypeInstance[(t, id)] = inst;
                // First writer wins; if the same name/id recurs the string is identical anyway.
                _byInstance.TryAdd(id, inst);
            }
        }

        // Precise lookup for AssetReference (both TypeId and InstanceId known).
        public string ResolveByTypeInstance(uint typeId, uint instanceId)
            => _byTypeInstance.TryGetValue((typeId, instanceId), out string n) ? n : null;

        // Instance-only lookup for TypedAssetId (stores the hash == InstanceId; the type isn't recorded inline).
        public string ResolveByInstance(uint instanceId)
            => _byInstance.TryGetValue(instanceId, out string n) ? n : null;
    }
}
