using System;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;
using System.Threading;

namespace Relo
{
    public sealed class Tracker : IDisposable
    {
        internal sealed class Bookmark
        {
            public uint Index;
            public uint From;
            public uint To;

            public override string ToString()
            {
                return $"Bookmark [{Index}] From: 0x{From:X08} To: 0x{To:X08}";
            }
        }

        internal sealed class Block
        {
            public IntPtr Data;
            public uint Size;              // x64 (in-memory) block size in bytes
            public Type ElementType;       // managed element type, or null for opaque byte/primitive blocks
            public uint ElementCount;      // number of elements
            public uint ElementSizeX64;    // sizeof(element) the caller passed in (x64)

            public Block(uint size)
            {
                Data = Marshal.AllocHGlobal((int)size);
                Size = size;
                Native.MsVcRt.MemSet(Data, 0, new Native.SizeT(size));
            }
        }

        public sealed class Context : IDisposable
        {
            private Tracker _parent;

            internal unsafe Context(Tracker parent)
            {
                _parent = parent;
            }

            public void Dispose()
            {
                if (_parent != null)
                {
                    _parent.Pop();
                    _parent = null;
                }
            }
        }

        public static Tracker NullTracker { get; } = new Tracker();

        private uint _instanceBufferSize;
        private readonly System.Collections.Generic.List<uint> _stack;
        private readonly System.Collections.Generic.List<Block> _blocks;
        private readonly System.Collections.Generic.List<Bookmark> _relocations;
        private readonly System.Collections.Generic.List<Bookmark> _imports;

        public bool IsBigEndian { get; private set; }

        private Tracker()
        {
            _stack = new System.Collections.Generic.List<uint>();
            _blocks = new System.Collections.Generic.List<Block>();
            _relocations = new System.Collections.Generic.List<Bookmark>();
            _imports = new System.Collections.Generic.List<Bookmark>();
        }

        public unsafe Tracker(void** rootPointer, uint size, bool isBigEndian) : this(rootPointer, size, isBigEndian, null)
        {
        }

        public unsafe Tracker(void** rootPointer, uint size, bool isBigEndian, Type rootType) : this()
        {
            IsBigEndian = isBigEndian;
            uint index = Allocate(1u, size, rootType);
            _stack.Add(index);
            *(IntPtr*)rootPointer = _blocks[(int)index].Data;
        }

        internal static unsafe bool BookmarkCompare(Bookmark x, Bookmark y)
        {
            return x.Index < y.Index || (x.Index <= y.Index && x.To < y.To);
        }

        private unsafe uint Allocate(uint count, uint elementSize, Type elementType)
        {
            Thread.MemoryBarrier();
            uint blockSize = (uint)((((int)count * (int)elementSize) + 3) & -4);
            Block block = new Block(blockSize)
            {
                ElementType = elementType,
                ElementCount = count,
                ElementSizeX64 = elementSize
            };
            _blocks.Add(block);
            _instanceBufferSize += blockSize;
            Thread.MemoryBarrier();
            return (uint)(_blocks.Count - 1);
        }

        private unsafe void ByteSwap16(ushort* value)
        {
            byte* pValue = (byte*)value;
            ushort result;
            byte* pResult = (byte*)&result;
            *pResult = pValue[1];
            pResult[1] = *pValue;
            *value = result;
        }

        private unsafe void ByteSwap32(uint* value)
        {
            byte* pValue = (byte*)value;
            uint result;
            byte* pResult = (byte*)&result;
            *pResult = pValue[3];
            pResult[1] = pValue[2];
            pResult[2] = pValue[1];
            pResult[3] = *pValue;
            *value = result;
        }

        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        public unsafe void InplaceEndianToPlatform(ushort* value)
        {
            if (IsBigEndian)
            {
                ByteSwap16(value);
            }
        }

        [MethodImpl(MethodImplOptions.AggressiveInlining)]
        public unsafe void InplaceEndianToPlatform(uint* value)
        {
            if (IsBigEndian)
            {
                ByteSwap32(value);
            }
        }

        public unsafe Context Push(void** pointerLocation, uint objectSize, uint objectCount)
        {
            return Push(pointerLocation, objectSize, objectCount, null);
        }

        public unsafe Context Push(void** pointerLocation, uint objectSize, uint objectCount, Type elementType)
        {
            uint index = _stack[^1];
            uint newIndex = Allocate(objectCount, objectSize, elementType);
            _stack.Add(newIndex);
            if ((IntPtr)pointerLocation == IntPtr.Zero)
            {
                return null;
            }
            Bookmark bookmark = new Bookmark
            {
                Index = index,
                From = (uint)((byte*)pointerLocation - (byte*)_blocks[(int)index].Data),
                To = newIndex
            };
            *(IntPtr*)pointerLocation = _blocks[(int)newIndex].Data;
            _relocations.Add(bookmark);
            return new Context(this);
        }

        public void Pop()
        {
            Thread.MemoryBarrier();
            _stack.RemoveAt(_stack.Count - 1);
            Thread.MemoryBarrier();
        }

        // Compacts a block's x64 element bytes into their 32-bit on-disk form and returns the x86
        // size (rounded up to 4, as the original allocator rounded the x64 block). Opaque blocks
        // (ElementType == null: raw byte/primitive arrays with no pointers) are copied verbatim.
        private static unsafe uint CompactBlock(Block block, byte* dst)
        {
            if (block.ElementType == null)
            {
                Native.MsVcRt.MemCpy((IntPtr)dst, block.Data, new Native.SizeT(block.Size));
                return block.Size;
            }
            TypeLayout layout = TypeLayout.Get(block.ElementType);
            if (layout.SizeX64 != block.ElementSizeX64)
            {
                throw new InvalidOperationException(
                    $"Relo layout mismatch for {block.ElementType}: computed x64 size {layout.SizeX64} != sizeof {block.ElementSizeX64}");
            }
            uint elemX64 = layout.SizeX64;
            uint elemX86 = layout.SizeX86;
            byte* src = (byte*)block.Data;
            for (uint i = 0; i < block.ElementCount; ++i)
            {
                layout.Compact(src + i * elemX64, dst + i * elemX86);
            }
            uint used = block.ElementCount * elemX86;
            return (used + 3u) & ~3u;
        }

        // Maps an x64 "from" offset (block-relative, as recorded by Push/AddReference) to the
        // corresponding x86 block-relative offset after compaction.
        private static uint MapFrom(Block block, uint fromX64)
        {
            if (block.ElementType == null)
            {
                return fromX64;
            }
            TypeLayout layout = TypeLayout.Get(block.ElementType);
            uint elemX64 = layout.SizeX64;
            uint elemX86 = layout.SizeX86;
            uint element = fromX64 / elemX64;
            uint within = fromX64 % elemX64;
            return element * elemX86 + layout.MapOffset(within);
        }

        public unsafe bool MakeRelocatable(Chunk chunk)
        {
            uint importsBufferSize = 0;
            if (_imports.Count > 0)
            {
                importsBufferSize = ((uint)_imports.Count + 1u) * 4u;
            }
            uint relocationBufferSize = 0;
            if (_relocations.Count > 0)
            {
                relocationBufferSize = ((uint)_relocations.Count + 1u) * 4u;
            }

            int blockCount = _blocks.Count;
            uint[] bookmarks = new uint[blockCount];
            uint[] blockSizesX86 = new uint[blockCount];

            // First pass: determine each block's x86 (on-disk) size and its offset.
            uint total = 0;
            for (int i = 0; i < blockCount; ++i)
            {
                Block block = _blocks[i];
                uint x86Size;
                if (block.ElementType == null)
                {
                    x86Size = block.Size;
                }
                else
                {
                    TypeLayout layout = TypeLayout.Get(block.ElementType);
                    x86Size = (block.ElementCount * layout.SizeX86 + 3u) & ~3u;
                }
                bookmarks[i] = total;
                blockSizesX86[i] = x86Size;
                total += x86Size;
            }

            if (!chunk.Allocate(total, relocationBufferSize, importsBufferSize))
            {
                return false;
            }
            fixed (byte* instanceBuffer = &chunk.InstanceBuffer[0])
            {
                for (int i = 0; i < blockCount; ++i)
                {
                    CompactBlock(_blocks[i], instanceBuffer + bookmarks[i]);
                }
                if (relocationBufferSize > 0)
                {
                    _relocations.Sort(new Comparison<Bookmark>((x, y) => BookmarkCompare(x, y) ? -1 : 1));
                    fixed (byte* pRelocationBuffer = &chunk.RelocationBuffer[0])
                    {
                        uint* relocationBuffer = (uint*)pRelocationBuffer;
                        foreach (Bookmark relocation in _relocations)
                        {
                            uint from = bookmarks[relocation.Index] + MapFrom(_blocks[(int)relocation.Index], relocation.From);
                            *relocationBuffer = from;
                            InplaceEndianToPlatform(relocationBuffer);
                            uint to = bookmarks[(int)relocation.To];
                            InplaceEndianToPlatform(&to);
                            *(uint*)(instanceBuffer + from) = to;
                            relocationBuffer++;
                        }
                        *relocationBuffer = uint.MaxValue;
                    }
                }
                if (importsBufferSize > 0u)
                {
                    _imports.Sort(new Comparison<Bookmark>((x, y) => BookmarkCompare(x, y) ? -1 : 1));
                    fixed (byte* pImportsBuffer = &chunk.ImportsBuffer[0])
                    {
                        uint* importsBuffer = (uint*)pImportsBuffer;
                        foreach (Bookmark import in _imports)
                        {
                            uint from = bookmarks[import.Index] + MapFrom(_blocks[(int)import.Index], import.From);
                            *importsBuffer = from;
                            InplaceEndianToPlatform(importsBuffer);
                            uint to = import.To;
                            InplaceEndianToPlatform(&to);
                            *(uint*)(instanceBuffer + from) = to;
                            importsBuffer++;
                        }
                        *importsBuffer = uint.MaxValue;
                    }
                }
            }
            return true;
        }

        public unsafe void AddReference(void* location, uint value)
        {
            uint index = _stack[^1];
            Bookmark bookmark = new Bookmark
            {
                Index = index,
                From = (uint)((byte*)location - (byte*)_blocks[(int)index].Data),
                To = value
            };
            *(uint*)location = value;
            _imports.Add(bookmark);
        }

        public void Dispose()
        {
            while (_blocks.Count != 0)
            {
                Marshal.FreeHGlobal(_blocks[^1].Data);
                _blocks.RemoveAt(_blocks.Count - 1);
            }
            _imports.Clear();
            _relocations.Clear();
            _blocks.Clear();
            _stack.Clear();
        }
    }
}
