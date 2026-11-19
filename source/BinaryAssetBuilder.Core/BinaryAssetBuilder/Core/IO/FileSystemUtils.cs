using System;
using System.IO;

namespace BinaryAssetBuilder.Core.IO
{
    public static class FileSystemUtils
    {
        public static string GetErrorString(int code)
        {
            return code.ToString();
        }

        // Windows version opened \\.\C: and FlushFileBuffers'd the whole volume (a build-cache
        // coherency step). There is no volume handle concept on other platforms; per-file writes
        // are flushed where it matters via FileStream. Best-effort no-op off Windows.
        public static void FlushVolume(char drive)
        {
            // intentionally a no-op on non-Windows; retained so callers (PathMonitor) are unchanged.
        }
    }
}
