using System;
using System.IO;

namespace BinaryAssetBuilder.Core.IO
{
    // The tool lowercases paths (a Windows, case-insensitive-filesystem assumption). On a
    // case-sensitive filesystem (Linux) those lowercased paths don't match the real mixed-case
    // files, so the loader silently fell back to an empty document. This resolves a path to its
    // real on-disk casing by walking it component-by-component. Returns the input unchanged if
    // it already exists or no match is found (caller handles the miss as before).
    public static class CaseInsensitivePath
    {
        public static string Resolve(string path)
        {
            if (string.IsNullOrEmpty(path) || File.Exists(path) || Directory.Exists(path))
            {
                return path;
            }
            string full;
            try { full = Path.GetFullPath(path); }
            catch { return path; }
            string root = Path.GetPathRoot(full);
            if (string.IsNullOrEmpty(root) || !Directory.Exists(root))
            {
                return path;
            }
            string current = root;
            string[] parts = full.Substring(root.Length)
                .Split(new[] { Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar }, StringSplitOptions.RemoveEmptyEntries);
            foreach (string part in parts)
            {
                string next = Path.Combine(current, part);
                if (File.Exists(next) || Directory.Exists(next))
                {
                    current = next;
                    continue;
                }
                string match = null;
                try
                {
                    foreach (string entry in Directory.EnumerateFileSystemEntries(current))
                    {
                        if (string.Equals(Path.GetFileName(entry), part, StringComparison.OrdinalIgnoreCase))
                        {
                            match = entry;
                            break;
                        }
                    }
                }
                catch { return path; }
                if (match is null) { return path; }
                current = match;
            }
            return current;
        }
    }
}
