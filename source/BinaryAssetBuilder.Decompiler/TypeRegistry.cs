using System;
using System.Collections.Generic;
using System.Reflection;
using BinaryAssetBuilder.Core.Hashing;

namespace BinaryAssetBuilder.Decompiler
{
    // The compiler identifies a type purely by TypeId = FastHash.GetHashCode(type.Name) (case-sensitive) —
    // see Plugin.CreateTypeInfo. That hash is one-way, so to decompile we precompute the reverse mapping by
    // reflecting every struct in the SageBinaryData assembly and hashing its name. The same mapping serves
    // both top-level assets (manifest AssetEntry.TypeId) and polymorphic module items (the module hash written
    // at offset 0 of each item block by Marshaler.MarshalPolymorphicType).
    //
    // Building it from reflection (rather than a hand-maintained table) means it can never drift from the
    // struct definitions the compiler actually uses.
    public sealed class TypeRegistry
    {
        private readonly Dictionary<uint, Type> _byTypeId = new();
        private readonly Dictionary<uint, List<string>> _collisions = new();

        public static TypeRegistry Build()
        {
            var reg = new TypeRegistry();
            Assembly asm = typeof(SageBinaryData.ArmorTemplate).Assembly;
            foreach (Type t in asm.GetTypes())
            {
                if (!t.IsValueType || t.IsEnum || t.IsGenericType || t.IsNested && !t.IsNestedPublic)
                {
                    continue;
                }
                uint id = FastHash.GetHashCode(t.Name);
                if (reg._byTypeId.TryGetValue(id, out Type existing))
                {
                    if (!reg._collisions.TryGetValue(id, out List<string> list))
                    {
                        list = new List<string> { existing.Name };
                        reg._collisions[id] = list;
                    }
                    list.Add(t.Name);
                    // Keep the first registration deterministically; collisions are surfaced via Collisions.
                    continue;
                }
                reg._byTypeId[id] = t;
            }
            return reg;
        }

        public bool TryGet(uint typeId, out Type type) => _byTypeId.TryGetValue(typeId, out type);

        public Type Get(uint typeId) => _byTypeId.TryGetValue(typeId, out Type t) ? t : null;

        // (typeId -> colliding simple names). Should be empty in practice; a non-empty result is a build-time
        // warning that two SAGE struct names hash to the same TypeId and need disambiguation.
        public IReadOnlyDictionary<uint, List<string>> Collisions => _collisions;

        public int Count => _byTypeId.Count;
    }
}
