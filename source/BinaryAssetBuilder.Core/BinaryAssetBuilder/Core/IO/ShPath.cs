using System.IO;

namespace BinaryAssetBuilder.Core.IO
{
    // Cross-platform replacements for the shlwapi.dll path helpers this tool used.
    public static class ShPath
    {
        // PathCanonicalizeW collapsed "." / ".." segments. Callers always pass an absolute path
        // (Path.Combine against an absolute root), so Path.GetFullPath normalizes identically.
        public static string Canonicalize(string path)
        {
            try { return Path.GetFullPath(path); }
            catch { return string.Empty; }
        }

        // PathRemoveFileSpecW stripped the trailing filename, leaving the directory.
        public static string RemoveFileSpec(string path)
        {
            return Path.GetDirectoryName(path) ?? string.Empty;
        }
    }
}
