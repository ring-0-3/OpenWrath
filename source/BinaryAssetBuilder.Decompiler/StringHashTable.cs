using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Xml.Linq;
using BinaryAssetBuilder.Core.Hashing;

namespace BinaryAssetBuilder.Decompiler
{
    // Reverse map hash -> original string, parsed from the StringHashes.xml the compiler emits (HashProvider.
    // FinalizeStringHashes). SAGE stores many author strings only as a one-way FastHash: module tags
    // (ModuleData.id / TypedAssetId), StringHash fields, and the type/instance id tables. Those cannot be
    // recovered from the compiled bytes alone; this table is how the decompiler gets them back.
    //
    // Each entry is <StringAndHash Hash="<decimal uint>" Text="<string>" />. For case-insensitive bins the Hash
    // is FastHash(text.ToLower()) — which is exactly what TypedAssetId stores — so a plain hash->text lookup
    // round-trips. The table is optional: without it (e.g. a foreign mod whose StringHashes we don't have),
    // these fields fall back to a hex placeholder and are reported as known-lossy.
    public sealed class StringHashTable
    {
        private readonly Dictionary<uint, string> _byHash = new();

        public bool Available => _byHash.Count > 0;

        public static StringHashTable Load(string path)
        {
            var t = new StringHashTable();
            if (string.IsNullOrEmpty(path) || !File.Exists(path))
            {
                return t;
            }
            XDocument doc;
            try { doc = XDocument.Load(path); }
            catch { return t; }
            foreach (XElement e in doc.Descendants())
            {
                if (e.Name.LocalName != "StringAndHash")
                {
                    continue;
                }
                string h = (string)e.Attribute("Hash");
                string text = (string)e.Attribute("Text");
                if (h == null || text == null)
                {
                    continue;
                }
                if (uint.TryParse(h, NumberStyles.Integer, CultureInfo.InvariantCulture, out uint hash))
                {
                    // The table's recorded Hash is the bin's hash (case-sensitive or lowered, varies by bin).
                    // A field stores either FastHash(text) (StringHash, case-sensitive) or FastHash(text.ToLower())
                    // (TypedAssetId / most ids). Index the text under all three so any lookup form resolves.
                    t._byHash.TryAdd(hash, text);
                    t._byHash.TryAdd(FastHash.GetHashCode(text), text);
                    t._byHash.TryAdd(FastHash.GetHashCode(text.ToLowerInvariant()), text);
                }
            }
            return t;
        }

        public string Lookup(uint hash) => _byHash.TryGetValue(hash, out string s) ? s : null;
    }
}
