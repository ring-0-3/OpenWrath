using System;
using System.Collections.Concurrent;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;

namespace Relo
{
    // Computes the 32-bit (on-disk, x86 / MSVC) memory layout of a managed struct type that the
    // x64 marshaller builds using native 8-byte pointers. SAGE's on-disk asset format uses 4-byte
    // pointers, so every pointer field (and the padding/alignment it induces) must be collapsed
    // from 8 bytes to 4. This engine walks a type's fields recursively and produces:
    //   - the x64 size (to validate against the sizeof() the marshaller passed in), and
    //   - the x86 size plus a field map able to compact an x64 instance into x86 bytes and to
    //     translate an x64 field offset (a relocation/import "from") into its x86 equivalent.
    // The only source of divergence between the two layouts is pointer width (8 vs 4); all scalar
    // fields are <= 4 bytes and laid out identically, so scalar offsets differ only by how much
    // preceding pointers shrank.
    // Made public (was internal) so the decompiler can drive a read-walk from the same field
    // metadata the compiler uses to write. Purely a visibility change plus the added Field handle;
    // the compile-side behaviour (Compact / MapOffset / Tracker) is unchanged.
    public sealed class TypeLayout
    {
        public enum Kind : byte { Scalar, Pointer, Nested, FixedBuffer }

        public sealed class FieldLayout
        {
            public uint X64Off;
            public uint X86Off;
            public uint X64Size;
            public uint X86Size;
            public Kind Kind;
            public TypeLayout Nested;
            public FieldInfo Field;   // the managed field (name + semantic type) for the decompiler's reader
        }

        public uint SizeX64;
        public uint SizeX86;
        public uint AlignX64;
        public uint AlignX86;
        public bool PointerLeaf;   // the type itself is a raw pointer (e.g. IntPtr / T**)
        public bool ScalarLeaf;    // the type itself is a primitive / enum scalar
        public FieldLayout[] Fields;

        private static readonly ConcurrentDictionary<Type, TypeLayout> _cache = new();

        public static TypeLayout Get(Type type)
        {
            return _cache.GetOrAdd(type, Build);
        }

        private static bool IsPointerLeaf(Type t)
        {
            return t.IsPointer || t == typeof(IntPtr) || t == typeof(UIntPtr);
        }

        // Returns (size, align) for a primitive/enum scalar; (0,0) if not a scalar.
        private static (uint size, uint align) Scalar(Type t)
        {
            if (t.IsEnum)
            {
                t = Enum.GetUnderlyingType(t);
            }
            if (t == typeof(bool) || t == typeof(byte) || t == typeof(sbyte))
            {
                return (1u, 1u);
            }
            if (t == typeof(char) || t == typeof(short) || t == typeof(ushort))
            {
                return (2u, 2u);
            }
            if (t == typeof(int) || t == typeof(uint) || t == typeof(float))
            {
                return (4u, 4u);
            }
            if (t == typeof(long) || t == typeof(ulong) || t == typeof(double))
            {
                return (8u, 8u);
            }
            return (0u, 0u);
        }

        private static uint AlignUp(uint value, uint align)
        {
            if (align <= 1u)
            {
                return value;
            }
            return (value + align - 1u) & ~(align - 1u);
        }

        private static TypeLayout Build(Type type)
        {
            if (IsPointerLeaf(type))
            {
                return new TypeLayout { PointerLeaf = true, SizeX64 = 8u, SizeX86 = 4u, AlignX64 = 8u, AlignX86 = 4u };
            }
            (uint ssize, uint salign) = Scalar(type);
            if (ssize != 0u)
            {
                return new TypeLayout { ScalarLeaf = true, SizeX64 = ssize, SizeX86 = ssize, AlignX64 = salign, AlignX86 = salign };
            }

            // Struct: walk instance fields in declaration (metadata) order.
            FieldInfo[] rawFields = type.GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
            Array.Sort(rawFields, (a, b) => a.MetadataToken.CompareTo(b.MetadataToken));

            var fields = new System.Collections.Generic.List<FieldLayout>(rawFields.Length);
            uint offX64 = 0u, offX86 = 0u, maxAlignX64 = 1u, maxAlignX86 = 1u;

            foreach (FieldInfo fi in rawFields)
            {
                uint fSizeX64, fSizeX86, fAlignX64, fAlignX86;
                Kind kind;
                TypeLayout nested = null;

                FixedBufferAttribute fb = fi.GetCustomAttribute<FixedBufferAttribute>();
                if (fb != null)
                {
                    (uint esize, uint ealign) = Scalar(fb.ElementType);
                    if (esize == 0u)
                    {
                        // fixed buffer of a non-scalar is not expected; fall back to marshal size.
                        esize = (uint)Marshal.SizeOf(fb.ElementType);
                        ealign = esize;
                    }
                    uint total = esize * (uint)fb.Length;
                    fSizeX64 = fSizeX86 = total;
                    fAlignX64 = fAlignX86 = ealign;
                    kind = Kind.FixedBuffer;
                }
                else
                {
                    Type ft = fi.FieldType;
                    if (IsPointerLeaf(ft))
                    {
                        fSizeX64 = 8u; fAlignX64 = 8u; fSizeX86 = 4u; fAlignX86 = 4u;
                        kind = Kind.Pointer;
                    }
                    else
                    {
                        (uint sz, uint al) = Scalar(ft);
                        if (sz != 0u)
                        {
                            fSizeX64 = fSizeX86 = sz;
                            fAlignX64 = fAlignX86 = al;
                            kind = Kind.Scalar;
                        }
                        else
                        {
                            nested = Get(ft);
                            fSizeX64 = nested.SizeX64; fAlignX64 = nested.AlignX64;
                            fSizeX86 = nested.SizeX86; fAlignX86 = nested.AlignX86;
                            kind = Kind.Nested;
                        }
                    }
                }

                offX64 = AlignUp(offX64, fAlignX64);
                offX86 = AlignUp(offX86, fAlignX86);
                fields.Add(new FieldLayout
                {
                    X64Off = offX64,
                    X86Off = offX86,
                    X64Size = fSizeX64,
                    X86Size = fSizeX86,
                    Kind = kind,
                    Nested = nested,
                    Field = fi
                });
                offX64 += fSizeX64;
                offX86 += fSizeX86;
                if (fAlignX64 > maxAlignX64) maxAlignX64 = fAlignX64;
                if (fAlignX86 > maxAlignX86) maxAlignX86 = fAlignX86;
            }

            uint sizeX64 = AlignUp(offX64, maxAlignX64);
            uint sizeX86 = AlignUp(offX86, maxAlignX86);

            // Honour [StructLayout(Size = N)].
            StructLayoutAttribute sla = type.StructLayoutAttribute;
            if (sla != null && sla.Size > 0)
            {
                uint explicitSize = (uint)sla.Size;
                if (fields.Count == 0)
                {
                    sizeX64 = explicitSize;
                    sizeX86 = explicitSize;
                    maxAlignX64 = 1u;
                    maxAlignX86 = 1u;
                }
                else
                {
                    if (explicitSize > sizeX64) sizeX64 = explicitSize;
                    if (explicitSize > sizeX86) sizeX86 = explicitSize;
                }
            }

            return new TypeLayout
            {
                SizeX64 = sizeX64,
                SizeX86 = sizeX86,
                AlignX64 = maxAlignX64,
                AlignX86 = maxAlignX86,
                Fields = fields.ToArray()
            };
        }

        // Compact one element from x64 memory (src) into x86 on-disk bytes (dst).
        public unsafe void Compact(byte* src, byte* dst)
        {
            if (PointerLeaf)
            {
                *(uint*)dst = *(uint*)src; // low 32 bits of the 64-bit pointer slot
                return;
            }
            if (ScalarLeaf || Fields == null)
            {
                Buffer.MemoryCopy(src, dst, SizeX86, SizeX64);
                return;
            }
            foreach (FieldLayout f in Fields)
            {
                byte* s = src + f.X64Off;
                byte* d = dst + f.X86Off;
                switch (f.Kind)
                {
                    case Kind.Pointer:
                        *(uint*)d = *(uint*)s;
                        break;
                    case Kind.Nested:
                        f.Nested.Compact(s, d);
                        break;
                    default: // Scalar or FixedBuffer
                        Buffer.MemoryCopy(s, d, f.X86Size, f.X64Size);
                        break;
                }
            }
        }

        // Translate an x64 field offset (within a single element) to its x86 offset.
        public uint MapOffset(uint x64Off)
        {
            if (PointerLeaf || ScalarLeaf || Fields == null)
            {
                return x64Off;
            }
            foreach (FieldLayout f in Fields)
            {
                if (x64Off >= f.X64Off && x64Off < f.X64Off + f.X64Size)
                {
                    if (f.Kind == Kind.Nested)
                    {
                        return f.X86Off + f.Nested.MapOffset(x64Off - f.X64Off);
                    }
                    return f.X86Off + (x64Off - f.X64Off);
                }
            }
            return x64Off;
        }
    }
}
