using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
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
                    "decompile-stream" => DecompileStream(args),
                    "info" => Info(args),
                    "layout" => Layout(args),
                    "typescan" => TypeScan(args),
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

        // Discovery helper: group assets by the TYPE NAME parsed from the manifest's qualified
        // name table ("TypeName:InstanceName"), so even UNREGISTERED types surface by name, with
        // their TypeId, distinct TypeHash(es), count, and sample instance names.
        private static int TypeScan(string[] args)
        {
            Manifest m = Manifest.Load(args[1]);
            TypeRegistry reg = TypeRegistry.Build();
            var count = new Dictionary<string, int>();
            var ids = new Dictionary<string, uint>();
            var hashes = new Dictionary<string, HashSet<uint>>();
            var samples = new Dictionary<string, List<string>>();
            for (int i = 0; i < m.Entries.Length; i++)
            {
                AssetStream.AssetEntry e = m.Entries[i];
                string full = m.Names[i] ?? "";
                int c = full.IndexOf(':');
                string tn = c >= 0 ? full.Substring(0, c) : "(noname)";
                string inst = c >= 0 ? full.Substring(c + 1) : full;
                count.TryGetValue(tn, out int n); count[tn] = n + 1;
                ids[tn] = e.TypeId;
                if (!hashes.TryGetValue(tn, out HashSet<uint> hs)) { hs = new HashSet<uint>(); hashes[tn] = hs; }
                hs.Add(e.TypeHash);
                if (!samples.TryGetValue(tn, out List<string> sl)) { sl = new List<string>(); samples[tn] = sl; }
                if (sl.Count < 4) { sl.Add(inst); }
            }
            foreach (KeyValuePair<string, int> kv in count.OrderByDescending(k => k.Value))
            {
                string tn = kv.Key;
                bool registered = reg.Get(ids[tn]) != null;
                string hh = string.Join(",", hashes[tn].Select(h => h.ToString("x8")));
                Console.WriteLine($"{(registered ? "REG " : "--- ")} TypeId=0x{ids[tn]:x8} TypeHash=[{hh}] count={kv.Value,-5} {tn}");
                Console.WriteLine($"        samples: {string.Join(", ", samples[tn])}");
            }
            return 0;
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

        // Decompile a whole LINKED stream (manifest + sibling .bin/.relo/.imp) with graceful degradation:
        // every asset either decompiles or becomes a labelled <RawAsset>, and the run NEVER crashes on bad data.
        // This is the foreign-mod robustness test (e.g. Second Isomer's ~44k-asset static_mod).
        //   bab-decompile decompile-stream <manifest> [--rm ...] [--schema X] [--stringhashes X]
        //                                  [--outdir DIR] [--only NAME]
        private static int DecompileStream(string[] args)
        {
            string manifestPath = args[1];
            string only = GetOption(args, "--only");
            string outdir = GetOption(args, "--outdir");           // if set, write decompiled XML; else tally only
            string schemaPath = GetOption(args, "--schema");
            string rm = GetOption(args, "--rm");
            string stringHashesPath = GetOption(args, "--stringhashes");

            string baseNoExt = manifestPath.EndsWith(".manifest", StringComparison.OrdinalIgnoreCase)
                ? manifestPath.Substring(0, manifestPath.Length - ".manifest".Length)
                : manifestPath;
            string binPath = baseNoExt + ".bin", reloPath = baseNoExt + ".relo", impPath = baseNoExt + ".imp";
            foreach (string p in new[] { binPath, reloPath, impPath })
            {
                if (!File.Exists(p)) { return Fail($"missing stream file {p}"); }
            }

            Manifest m = Manifest.Load(manifestPath);
            TypeRegistry reg = TypeRegistry.Build();
            SchemaIndex schema = SchemaIndex.Load(schemaPath);
            var refManifests = new List<Manifest> { m };
            if (rm != null)
            {
                foreach (string p in rm.Split(';', StringSplitOptions.RemoveEmptyEntries))
                {
                    try { refManifests.Add(Manifest.Load(p.Trim())); }
                    catch (Exception ex) { Console.Error.WriteLine($"  WARN ref manifest {p}: {ex.Message}"); }
                }
            }
            ReferenceResolver resolver = ReferenceResolver.Build(refManifests);
            StringHashTable strings = StringHashTable.Load(stringHashesPath);
            var dec = new AssetDecompiler(reg, schema, resolver, strings);
            if (outdir != null) { Directory.CreateDirectory(outdir); }

            Console.WriteLine($"stream: {m.AssetCount} assets  (writing: {(outdir != null ? outdir : "tally-only")})");
            var statusCounts = new Dictionary<string, int>();
            int total = 0, unknownModules = 0, written = 0;
            // TypeId -> set of distinct TypeHashes seen (schema-version awareness).
            var typeHashes = new Dictionary<uint, HashSet<uint>>();
            var typeCounts = new Dictionary<uint, int>();
            var statusByType = new Dictionary<uint, int[]>(); // TypeId -> [okCount, rawCount]

            int i = 0;
            foreach (AssetInput asset in LinkedStreamReader.Read(m, binPath, reloPath, impPath))
            {
                i++;
                if (!typeHashes.TryGetValue(asset.TypeId, out HashSet<uint> hs)) { hs = new HashSet<uint>(); typeHashes[asset.TypeId] = hs; }
                hs.Add(asset.TypeHash);
                typeCounts.TryGetValue(asset.TypeId, out int tc); typeCounts[asset.TypeId] = tc + 1;

                if (only != null && !string.Equals(asset.Name, only, StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }
                total++;
                XElement el = dec.DecompileElement(asset, out string status, out int um);
                statusCounts.TryGetValue(status, out int sc); statusCounts[status] = sc + 1;
                unknownModules += um;
                bool isOk = status.StartsWith("ok", StringComparison.Ordinal);
                statusByType.TryGetValue(asset.TypeId, out int[] st); if (st == null) { st = new int[2]; statusByType[asset.TypeId] = st; }
                st[isOk ? 0 : 1]++;

                if (outdir != null)
                {
                    var doc = new XDocument(new XElement(AssetDecompiler.AssetNs + "AssetDeclaration", el));
                    // Qualify the output file by type name: instance names are only unique PER TYPE (e.g. both
                    // AudioLOD:Low and GameLODPreset:Low exist), so an instance-name-only file name lets one type
                    // silently overwrite the other's XML and drop it from the round-trip. The XML id attribute
                    // still carries the bare instance name; only the on-disk file name is qualified.
                    string typeName = reg.Get(asset.TypeId)?.Name ?? asset.TypeId.ToString("x8");
                    string fn = typeName + "." + (asset.Name ?? asset.InstanceId.ToString("x8")) + ".xml";
                    WriteXml(doc, Path.Combine(outdir, SafeName(fn)));
                    written++;
                }
                if (only == null && (i % 5000 == 0)) { Console.WriteLine($"  ...{i}/{m.AssetCount}"); }
            }

            Console.WriteLine("---- summary ----");
            Console.WriteLine($"processed={total}  unknownModulePlaceholders={unknownModules}  written={written}");
            foreach (KeyValuePair<string, int> kv in statusCounts.OrderByDescending(k => k.Value))
            {
                Console.WriteLine($"  {kv.Key,-20} {kv.Value}");
            }
            Console.WriteLine("---- top types (count, name, distinct TypeHashes) ----");
            foreach (KeyValuePair<uint, int> kv in typeCounts.OrderByDescending(k => k.Value).Take(15))
            {
                string name = reg.Get(kv.Key)?.Name ?? "(unknown)";
                string hashes = string.Join(",", typeHashes[kv.Key].Select(h => h.ToString("x8")));
                Console.WriteLine($"  0x{kv.Key:x8} {kv.Value,7}  {name,-28} [{hashes}]");
            }
            int multiSchema = typeHashes.Count(kv => kv.Value.Count > 1);
            Console.WriteLine($"types with >1 distinct TypeHash (schema variants): {multiSchema}");
            Console.WriteLine("---- biggest raw-fallback contributors (type: ok/raw) ----");
            foreach (KeyValuePair<uint, int[]> kv in statusByType.OrderByDescending(k => k.Value[1]).Take(12))
            {
                string name = reg.Get(kv.Key)?.Name ?? "(unknown-type)";
                Console.WriteLine($"  {name,-28} ok={kv.Value[0],-6} raw={kv.Value[1]}");
            }
            return 0; // completing without an unhandled crash is success; fallbacks are expected
        }

        private static string SafeName(string n)
        {
            foreach (char c in Path.GetInvalidFileNameChars()) { n = n.Replace(c, '_'); }
            return n;
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
