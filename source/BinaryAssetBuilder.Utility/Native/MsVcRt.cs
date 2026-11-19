using System;

namespace Native
{
    // Cross-platform managed reimplementation of the few msvcrt.dll routines this tool used.
    // Same method names/signatures as the old P/Invoke delegates, so callers are unchanged.
    public static class MsVcRt
    {
        public static unsafe IntPtr MemSet(IntPtr ptr, byte value, SizeT count)
        {
            new Span<byte>((void*)ptr, (int)count).Fill(value);
            return ptr;
        }

        public static unsafe IntPtr MemCpy(IntPtr dest, IntPtr src, SizeT count)
        {
            long n = (int)count;
            Buffer.MemoryCopy((void*)src, (void*)dest, n, n);
            return dest;
        }

        // Case-insensitive byte compare (the original bound msvcrt _memicmp).
        public static unsafe int MemICmp(IntPtr buf1, IntPtr buf2, SizeT size)
        {
            int n = (int)size;
            byte* a = (byte*)buf1;
            byte* b = (byte*)buf2;
            for (int i = 0; i < n; i++)
            {
                int ca = a[i]; if (ca >= 'A' && ca <= 'Z') ca += 32;
                int cb = b[i]; if (cb >= 'A' && cb <= 'Z') cb += 32;
                int d = ca - cb;
                if (d != 0) return d < 0 ? -1 : 1;
            }
            return 0;
        }
    }
}
