using System;
using System.Collections.Generic;
using System.Xml.Linq;
using BinaryAssetBuilder.Decompiler.Containers;

namespace BinaryAssetBuilder.Decompiler
{
    // Turns one AssetInput into an <AssetDeclaration> XML document, the authoring form the compiler consumes.
    public sealed class AssetDecompiler
    {
        public static readonly XNamespace AssetNs = "uri:ea.com:eala:asset";

        private readonly TypeRegistry _registry;
        private readonly SchemaIndex _schema;
        private readonly Dictionary<string, Type> _enumsByName;
        private readonly ReferenceResolver _resolver;
        private readonly StringHashTable _strings;

        public AssetDecompiler(TypeRegistry registry, SchemaIndex schema = null, ReferenceResolver resolver = null,
            StringHashTable strings = null)
        {
            _registry = registry;
            _schema = schema;
            _resolver = resolver;
            _strings = strings;
            _enumsByName = BuildEnumIndex();
        }

        // All enums in the SageBinaryData assembly, keyed by simple name, so a bit-flag's XSD itemType
        // (e.g. "Surface") resolves to the concrete enum type for name rendering.
        private static Dictionary<string, Type> BuildEnumIndex()
        {
            var map = new Dictionary<string, Type>(StringComparer.Ordinal);
            foreach (Type t in typeof(SageBinaryData.ArmorTemplate).Assembly.GetTypes())
            {
                if (t.IsEnum)
                {
                    map[t.Name] = t; // last-wins; SAGE enum names are unique in practice
                }
            }
            return map;
        }

        public bool TryDecompile(AssetInput asset, out XDocument document, out string error)
        {
            document = null;
            error = null;
            if (!_registry.TryGet(asset.TypeId, out Type type))
            {
                error = $"unknown TypeId 0x{asset.TypeId:x8}";
                return false; // Phase 5 turns this into a <RawAsset> block instead of a failure
            }

            var root = new XElement(AssetNs + type.Name);
            if (!string.IsNullOrEmpty(asset.Name))
            {
                root.SetAttributeValue("id", asset.Name);
            }
            new StructReader(asset, _registry, AssetNs, _schema, _enumsByName, _resolver, _strings).ReadStruct(type, 0u, root);

            document = new XDocument(new XElement(AssetNs + "AssetDeclaration", root));
            return true;
        }
    }
}
