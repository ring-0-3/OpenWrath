using System;
using System.Collections.Generic;
using System.IO;
using System.Xml;
using System.Xml.Linq;
using BinaryAssetBuilder.Core.Hashing;
using BinaryAssetBuilder.Decompiler;
using BinaryAssetBuilder.Decompiler.Containers;

namespace BinaryAssetBuilder.Decompiler.Cli
{
    // Native Linux decompiler CLI: SAGE / Kane's Wrath compiled assets -> authoring XML.
    //
    //   bab-decompile decompile <manifest.manifest> [--only NAME] [--outdir DIR] [--assets DIR]
    //   bab-decompile info      <manifest.manifest>
    //
    // The decompiler is the structural inverse of BinaryAssetBuilder (same SageBinaryData structs + Relo
    // layout engine), so its output is designed to recompile byte-identically.
    public static class Program
    {
        public static int Main(string[] args)
        {
            if (args.Length == 0)
            {
                Console.Error.WriteLine("usage: bab-decompile <decompile|info> <manifest> [options]");
                return 2;
            }
            try
            {
                return args[0] switch
                {
                    "decompile" => Decompile(args),
                    "info" => Info(args),
                    "layout" => Layout(args),
                    _ => Fail($"unknown verb '{args[0]}'"),
                };
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("error: " + ex.Message);
                return 1;
            }
        }

        private static int Fail(string msg)
        {
            Console.Error.WriteLine("error: " + msg);
            return 2;
        }

        private static int Info(string[] args)
        {
            Manifest m = Manifest.Load(args[1]);
            Console.WriteLine($"manifest: linked={m.IsLinked} version={m.Version} assets={m.AssetCount}");
            var byType = new Dictionary<uint, int>();
            foreach (AssetStream.AssetEntry e in m.Entries)
            {
                byType.TryGetValue(e.TypeId, out int c);
                byType[e.TypeId] = c + 1;
            }
            TypeRegistry reg = TypeRegistry.Build();
            foreach (KeyValuePair<uint, int> kv in byType)
            {
                string name = reg.Get(kv.Key)?.Name ?? "(unknown)";
                Console.WriteLine($"  0x{kv.Key:x8}  {kv.Value,6}  {name}");
            }
            return 0;
        }

        // Debug helper: print the on-disk (x86) field layout of a SageBinaryData type, to map a byte offset
        // reported by the round-trip harness back to a field. Usage: bab-decompile layout WeaponTemplate
        private static int Layout(string[] args)
        {
            Type t = typeof(SageBinaryData.ArmorTemplate).Assembly.GetType("SageBinaryData." + args[1]);
            if (t == null)
            {
                return Fail($"unknown type {args[1]}");
            }
            Relo.TypeLayout layout = Relo.TypeLayout.Get(t);
            Console.WriteLine($"{t.Name}  SizeX86={layout.SizeX86}");
            foreach (Relo.TypeLayout.FieldLayout f in layout.Fields)
            {
                Console.WriteLine($"  @{f.X86Off,-5} sz={f.X86Size,-4} {f.Kind,-11} {f.Field?.FieldType.Name,-32} {f.Field?.Name}");
            }
            return 0;
        }

        private static int Decompile(string[] args)
        {
            string manifestPath = args[1];
            string only = GetOption(args, "--only");
            string outdir = GetOption(args, "--outdir") ?? ".";
            string combined = GetOption(args, "--combined");  // write ALL assets into one AssetDeclaration file
            string assetsDir = GetOption(args, "--assets") ?? Path.Combine(Path.GetDirectoryName(Path.GetFullPath(manifestPath)) ?? ".", "assets");
            string schemaPath = GetOption(args, "--schema");   // XSD root/dir (for bit-flag enum names, shape)
            string rm = GetOption(args, "--rm");                // ';'-separated reference manifests (cross-stream names)
            string stringHashesPath = GetOption(args, "--stringhashes"); // StringHashes.xml: recover module tags / hashes

            if (combined == null)
            {
                Directory.CreateDirectory(outdir);
            }
            Manifest m = Manifest.Load(manifestPath);
            TypeRegistry reg = TypeRegistry.Build();
            SchemaIndex schema = SchemaIndex.Load(schemaPath);

            // Build the name index: the stream being decompiled + any base-game reference manifests (same set
            // the compiler's -rm uses) so cross-stream references resolve to authored names, not placeholders.
            var refManifests = new List<Manifest> { m };
            if (rm != null)
            {
                foreach (string p in rm.Split(';', StringSplitOptions.RemoveEmptyEntries))
                {
                    try { refManifests.Add(Manifest.Load(p.Trim())); }
                    catch (Exception ex) { Console.Error.WriteLine($"  WARN could not load ref manifest {p}: {ex.Message}"); }
                }
            }
            ReferenceResolver resolver = ReferenceResolver.Build(refManifests);
            StringHashTable strings = StringHashTable.Load(stringHashesPath);
            var dec = new AssetDecompiler(reg, schema, resolver, strings);
            XElement combinedRoot = combined != null ? new XElement(AssetDecompiler.AssetNs + "AssetDeclaration") : null;

            int ok = 0, skipped = 0, failed = 0;
            for (int i = 0; i < m.Entries.Length; i++)
            {
                AssetStream.AssetEntry e = m.Entries[i];
                string fullName = m.Names[i];
                // The manifest stores the qualified name "TypeName:InstanceName"; the XML id attribute is the
                // instance part only (the compiler re-qualifies it from the element's schema type).
                string id = fullName != null && fullName.Contains(':')
                    ? fullName.Substring(fullName.IndexOf(':') + 1)
                    : fullName;
                if (only != null && !string.Equals(id, only, StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                string file = Path.Combine(assetsDir,
                    $"{e.TypeId:x8}.{e.TypeHash:x8}.{e.InstanceId:x8}.{e.InstanceHash:x8}.asset");
                if (!File.Exists(file))
                {
                    Console.Error.WriteLine($"  MISSING chunk for {fullName}: {file}");
                    skipped++;
                    continue;
                }

                AssetInput asset = AssetInput.FromAssetFile(file, id);
                asset.References = m.GetAssetReferences(i); // ordered (TypeId,InstanceId) for import-index resolution
                // sanity: the qualified name should hash to the InstanceId (case-insensitive)
                if (fullName != null
                    && FastHash.GetHashCode(fullName.ToLowerInvariant()) != asset.InstanceId
                    && FastHash.GetHashCode((id ?? "").ToLowerInvariant()) != asset.InstanceId)
                {
                    Console.Error.WriteLine($"  WARN name/InstanceId mismatch for '{fullName}'");
                }

                if (!dec.TryDecompile(asset, out XDocument doc, out string err))
                {
                    Console.Error.WriteLine($"  SKIP {fullName}: {err}");
                    skipped++;
                    continue;
                }

                if (combinedRoot != null)
                {
                    foreach (XElement assetElem in doc.Root.Elements())
                    {
                        combinedRoot.Add(assetElem);
                    }
                }
                else
                {
                    string outPath = Path.Combine(outdir, (id ?? e.InstanceId.ToString("x8")) + ".xml");
                    WriteXml(doc, outPath);
                }
                ok++;
            }
            if (combinedRoot != null)
            {
                WriteXml(new XDocument(combinedRoot), combined);
            }
            Console.WriteLine($"decompiled={ok} skipped={skipped} failed={failed}");
            return failed == 0 ? 0 : 1;
        }

        private static void WriteXml(XDocument doc, string path)
        {
            var settings = new XmlWriterSettings
            {
                Indent = true,
                IndentChars = "  ",
                OmitXmlDeclaration = false,
                Encoding = new System.Text.UTF8Encoding(false),
            };
            using var w = XmlWriter.Create(path, settings);
            doc.Save(w);
        }

        private static string GetOption(string[] args, string name)
        {
            for (int i = 0; i < args.Length - 1; i++)
            {
                if (args[i] == name)
                {
                    return args[i + 1];
                }
            }
            return null;
        }
    }
}
