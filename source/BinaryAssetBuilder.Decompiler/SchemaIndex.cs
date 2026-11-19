using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Xml.Linq;

namespace BinaryAssetBuilder.Decompiler
{
    // Index over the KW XSD tree. It answers two questions the binary alone cannot, and that the decompiler
    // needs to emit XML the compiler will accept and round-trip:
    //
    //  1. Which attributes a type actually declares. The hand-maintained SageBinaryData structs sometimes carry
    //     MORE fields than the shipped XSD declares (e.g. LocomotorTemplate.BurningDeathRadius). The compiler
    //     validates against the XSD and rejects undeclared attributes. Because the source XML could never have
    //     set such a field, its compiled value is always the marshal-default, so omitting it on decompile is
    //     both required (to validate) and byte-safe (recompile re-applies the same default).
    //
    //  2. Which enum a bit-flag datatype lists (<xs:list itemType="Enum"/>), so flags emit enum names.
    //
    // The XSD tree has duplicate type declarations across its include files (which XmlSchemaSet.Compile rejects),
    // so we parse the documents directly and resolve xs:extension bases + xs:attributeGroup refs ourselves.
    public sealed class SchemaIndex
    {
        private static readonly XNamespace Xs = "http://www.w3.org/2001/XMLSchema";

        private sealed class ComplexType
        {
            public readonly List<string> OwnAttributes = new();
            public readonly List<string> AttributeGroupRefs = new();
            public readonly List<string> OwnElements = new();
            public string BaseType;
        }

        private readonly Dictionary<string, ComplexType> _complexTypes = new(StringComparer.Ordinal);
        private readonly Dictionary<string, ComplexType> _attributeGroups = new(StringComparer.Ordinal);
        private readonly Dictionary<string, string> _bitFlagItemEnum = new(StringComparer.Ordinal);
        private readonly Dictionary<string, List<string>> _enumValues = new(StringComparer.Ordinal);
        private readonly Dictionary<string, HashSet<string>> _resolvedAttrs = new(StringComparer.Ordinal);
        // typeName -> authoring element name, from <xs:element name="X" type="Y"/>. A polymorphic module is
        // authored as <ShortName> (e.g. <ActiveBody>) whose XSD type is the full struct name
        // (ActiveBodyModuleData). The binary only records the type (its hash at module offset 0); this map
        // recovers the element name to emit. First declaration wins (module element/type pairs are 1:1).
        private readonly Dictionary<string, string> _typeToElement = new(StringComparer.Ordinal);
        private readonly bool _available;

        private SchemaIndex(bool available) { _available = available; }

        public static SchemaIndex Load(string schemaPathOrDir)
        {
            if (string.IsNullOrEmpty(schemaPathOrDir))
            {
                return new SchemaIndex(false);
            }
            string dir = Directory.Exists(schemaPathOrDir) ? schemaPathOrDir : Path.GetDirectoryName(schemaPathOrDir);
            if (dir == null || !Directory.Exists(dir))
            {
                return new SchemaIndex(false);
            }
            var idx = new SchemaIndex(true);
            foreach (string file in Directory.EnumerateFiles(dir, "*.xsd", SearchOption.AllDirectories))
            {
                XDocument doc;
                try { doc = XDocument.Load(file); }
                catch { continue; }
                idx.IngestDocument(doc);
            }
            return idx;
        }

        private void IngestDocument(XDocument doc)
        {
            XElement schema = doc.Root;
            if (schema == null)
            {
                return;
            }
            foreach (XElement ct in schema.Elements(Xs + "complexType"))
            {
                string name = (string)ct.Attribute("name");
                if (name != null)
                {
                    _complexTypes[name] = ParseAttributeContainer(ct);
                }
            }
            foreach (XElement ag in schema.Elements(Xs + "attributeGroup"))
            {
                string name = (string)ag.Attribute("name");
                if (name != null)
                {
                    _attributeGroups[name] = ParseAttributeContainer(ag);
                }
            }
            // Element declarations anywhere in the document: name + named type -> authoring element name.
            foreach (XElement el in schema.Descendants(Xs + "element"))
            {
                string elName = (string)el.Attribute("name");
                string elType = Local((string)el.Attribute("type"));
                if (elName != null && elType != null && !_typeToElement.ContainsKey(elType))
                {
                    _typeToElement[elType] = elName;
                }
            }
            foreach (XElement st in schema.Elements(Xs + "simpleType"))
            {
                string name = (string)st.Attribute("name");
                if (name == null)
                {
                    continue;
                }
                XElement list = st.Element(Xs + "list");
                string item = list == null ? null : Local((string)list.Attribute("itemType"));
                if (item != null)
                {
                    _bitFlagItemEnum[name] = item;
                }
                // Enumeration facets, in declaration order == enum value order (0,1,2,...). This is the
                // authoritative name<->bit mapping the compiler validates against.
                XElement restr = st.Element(Xs + "restriction");
                if (restr != null)
                {
                    var vals = restr.Elements(Xs + "enumeration")
                        .Select(e => (string)e.Attribute("value"))
                        .Where(v => v != null)
                        .ToList();
                    if (vals.Count > 0)
                    {
                        _enumValues[name] = vals;
                    }
                }
            }
        }

        // Collect attributes, attribute-group refs and an extension/restriction base anywhere beneath `root`.
        private static ComplexType ParseAttributeContainer(XElement root)
        {
            var c = new ComplexType();
            foreach (XElement e in root.Descendants())
            {
                if (e.Name == Xs + "attribute")
                {
                    string an = (string)e.Attribute("name");
                    if (an != null) c.OwnAttributes.Add(an);
                }
                else if (e.Name == Xs + "attributeGroup")
                {
                    string r = Local((string)e.Attribute("ref"));
                    if (r != null) c.AttributeGroupRefs.Add(r);
                }
                else if (e.Name == Xs + "element")
                {
                    // Direct child elements of THIS type only (not elements inside a nested inline complexType),
                    // so we know which fields the XSD expects as child elements rather than attributes.
                    string en = (string)e.Attribute("name");
                    if (en != null && e.Ancestors(Xs + "complexType").FirstOrDefault() == root)
                    {
                        c.OwnElements.Add(en);
                    }
                }
                else if ((e.Name == Xs + "extension" || e.Name == Xs + "restriction") && c.BaseType == null)
                {
                    c.BaseType = Local((string)e.Attribute("base"));
                }
            }
            return c;
        }

        private static string Local(string qname)
        {
            if (qname == null) return null;
            int c = qname.IndexOf(':');
            return c >= 0 ? qname.Substring(c + 1) : qname;
        }

        // Declared attribute local-names for a complex type (inherited base + attribute-group attributes folded
        // in), or null if the schema is unavailable / the type is unknown (caller then emits unfiltered).
        public HashSet<string> GetDeclaredAttributeNames(string typeName)
        {
            if (!_available)
            {
                return null;
            }
            if (_resolvedAttrs.TryGetValue(typeName, out HashSet<string> cached))
            {
                return cached;
            }
            if (!_complexTypes.ContainsKey(typeName))
            {
                _resolvedAttrs[typeName] = null;
                return null;
            }
            var names = new HashSet<string>(StringComparer.Ordinal);
            Collect(typeName, names, new HashSet<string>(StringComparer.Ordinal));
            _resolvedAttrs[typeName] = names;
            return names;
        }

        private readonly Dictionary<string, HashSet<string>> _resolvedElems = new(StringComparer.Ordinal);

        // Declared CHILD-ELEMENT local-names for a complex type (inherited base folded in). Used to emit a field
        // the XSD expects as a child element (e.g. FXShaderConstantTexture.Value) as <name>value</name> rather
        // than as an attribute (which the validator would reject). null if schema unavailable / type unknown.
        public HashSet<string> GetDeclaredElementNames(string typeName)
        {
            if (!_available)
            {
                return null;
            }
            if (_resolvedElems.TryGetValue(typeName, out HashSet<string> cached))
            {
                return cached;
            }
            if (!_complexTypes.ContainsKey(typeName))
            {
                _resolvedElems[typeName] = null;
                return null;
            }
            var names = new HashSet<string>(StringComparer.Ordinal);
            CollectElements(typeName, names, new HashSet<string>(StringComparer.Ordinal));
            _resolvedElems[typeName] = names;
            return names;
        }

        private void CollectElements(string typeName, HashSet<string> into, HashSet<string> visiting)
        {
            if (typeName == null || !visiting.Add(typeName))
            {
                return;
            }
            if (_complexTypes.TryGetValue(typeName, out ComplexType ct))
            {
                foreach (string el in ct.OwnElements) into.Add(el);
                if (ct.BaseType != null) CollectElements(ct.BaseType, into, visiting);
            }
        }

        private void Collect(string typeName, HashSet<string> into, HashSet<string> visiting)
        {
            if (typeName == null || !visiting.Add(typeName))
            {
                return;
            }
            if (_complexTypes.TryGetValue(typeName, out ComplexType ct))
            {
                foreach (string a in ct.OwnAttributes) into.Add(a);
                foreach (string g in ct.AttributeGroupRefs) CollectGroup(g, into, visiting);
                if (ct.BaseType != null) Collect(ct.BaseType, into, visiting);
            }
        }

        private void CollectGroup(string groupName, HashSet<string> into, HashSet<string> visiting)
        {
            if (groupName == null || !visiting.Add("@grp:" + groupName))
            {
                return;
            }
            if (_attributeGroups.TryGetValue(groupName, out ComplexType ag))
            {
                foreach (string a in ag.OwnAttributes) into.Add(a);
                foreach (string g in ag.AttributeGroupRefs) CollectGroup(g, into, visiting);
            }
        }

        public string GetBitFlagItemEnum(string bitFlagTypeName)
        {
            return _bitFlagItemEnum.TryGetValue(bitFlagTypeName, out string e) ? e : null;
        }

        // Ordered enumeration value names for an enum simpleType (index == bit/enum value), or null.
        public List<string> GetEnumValues(string enumTypeName)
        {
            return enumTypeName != null && _enumValues.TryGetValue(enumTypeName, out List<string> v) ? v : null;
        }

        // Authoring element name for a (module) type, or null if the schema doesn't declare an element of it.
        public string GetElementNameForType(string typeName)
        {
            return typeName != null && _typeToElement.TryGetValue(typeName, out string el) ? el : null;
        }

        public bool Available => _available;
    }
}
