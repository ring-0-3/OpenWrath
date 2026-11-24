using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
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
                return false;
            }

            var root = new XElement(AssetNs + type.Name);
            if (!string.IsNullOrEmpty(asset.Name))
            {
                root.SetAttributeValue("id", asset.Name);
            }
            PopulateRoot(asset, type, root);

            document = new XDocument(new XElement(AssetNs + "AssetDeclaration", root));
            return true;
        }

        // Single dispatch from a decoded asset to the right reader: the type-specific W3DAnimationReader for
        // W3DAnimation (ships in its compressed runtime form), the generic struct-walker for everything else.
        // One copy so the closed-loop and foreign-mod paths can never pick different readers for the same type.
        private void PopulateRoot(AssetInput asset, Type type, XElement root)
        {
            if (asset.TypeId == W3DAnimationReader.TypeId)
            {
                new W3DAnimationReader(asset, AssetNs, _resolver).Read(root);
            }
            else
            {
                new StructReader(asset, _registry, AssetNs, _schema, _enumsByName, _resolver, _strings).ReadStruct(type, 0u, root);
            }
        }

        // Foreign-mod-robust decompile of a single asset. NEVER throws: an unknown type, a desync, or any other
        // error becomes a labelled <RawAsset> fallback so one bad asset can never abort a whole stream. Returns
        // the asset element (either the decompiled root or a <RawAsset>); `status` is one of
        // ok | ok-unknownmodules | raw:unknown-type | raw:desync | raw:error; `unknownModules` counts
        // <UnknownModule> placeholders emitted inside a successful decompile.
        public XElement DecompileElement(AssetInput asset, out string status, out int unknownModules)
        {
            unknownModules = 0;
            if (!_registry.TryGet(asset.TypeId, out Type type))
            {
                status = "raw:unknown-type";
                return RawAsset(asset, "unknown-type");
            }
            try
            {
                var root = new XElement(AssetNs + type.Name);
                if (!string.IsNullOrEmpty(asset.Name))
                {
                    root.SetAttributeValue("id", asset.Name);
                }
                PopulateRoot(asset, type, root);
                unknownModules = root.Descendants(AssetNs + "UnknownModule").Count();
                status = unknownModules > 0 ? "ok-unknownmodules" : "ok";
                return root;
            }
            catch (DesyncException dx)
            {
                status = "raw:desync";
                return RawAsset(asset, "desync: " + dx.Message);
            }
            catch (Exception ex)
            {
                status = "raw:error";
                return RawAsset(asset, ex.GetType().Name + ": " + ex.Message);
            }
        }

        private static XElement RawAsset(AssetInput a, string reason)
        {
            var e = new XElement(AssetNs + "RawAsset");
            e.SetAttributeValue("TypeId", "0x" + a.TypeId.ToString("x8", CultureInfo.InvariantCulture));
            e.SetAttributeValue("TypeHash", "0x" + a.TypeHash.ToString("x8", CultureInfo.InvariantCulture));
            e.SetAttributeValue("InstanceId", "0x" + a.InstanceId.ToString("x8", CultureInfo.InvariantCulture));
            if (!string.IsNullOrEmpty(a.Name))
            {
                e.SetAttributeValue("id", a.Name);
            }
            e.SetAttributeValue("reason", reason);
            e.Value = Convert.ToBase64String(a.Instance);
            return e;
        }
    }
}
