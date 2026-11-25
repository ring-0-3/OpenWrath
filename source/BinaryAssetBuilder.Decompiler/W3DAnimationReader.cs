using System;
using System.Globalization;
using System.Text;
using System.Xml.Linq;
using BinaryAssetBuilder.Decompiler.Containers;
using SageBinaryData;

namespace BinaryAssetBuilder.Decompiler
{
    // Type-specific reader for W3DAnimation (TypeId 0x2448AE30). In Kane's Wrath a W3DAnimation ships in its
    // compiled RUNTIME form: W3DAnimationRuntime, whose per-bone channels are already time-coded or
    // adaptive-delta compressed (lossy). The generic struct-walker can't read it, because the registry maps
    // the TypeId to the AUTHORING struct (W3DAnimation) whose layout differs. Rather than decompress and lose
    // the exact bytes on re-compression, we emit the channels in their shipped runtime form (<Timecoded> /
    // <Delta>). The compiler's W3X pass-through writes them straight back, so the asset round-trips byte-exact.
    //
    // On-disk W3DAnimationRuntime (x86):
    //   @0  Base (BaseAssetType, 4, unused)   @4  Hierarchy (AssetReference import)
    //   @8  NumFrames (uint)                  @12 FrameRate (uint)
    //   @16 Channels.Count (uint)             @20 Channels.Items (ptr -> Count pointers)
    // Each channel pointer -> a block:
    //   @0 TypeId  @4 Type  @8 NumFrames  @12 VectorLen  @16 Pivot(ushort)
    //   Timecoded (0x60D8CF69): @20 FAB.Count @24 FAB.Items  @28 Values.Count @32 Values.Items
    //   Delta     (0x77F97305): @20 Scale    @24 Init.Count @28 Init.Items  @32 NumBits  @36 CV.Count @40 CV.Items
    public sealed class W3DAnimationReader
    {
        public const uint TypeId = 0x2448AE30u;
        // Channel discriminators: single source is SageBinaryData.AnimationChannelTypeIds (shared with the
        // compiler's runtime marshaler and the time-coded/adaptive-delta compressors).
        private const uint TimecodedTypeId = AnimationChannelTypeIds.Timecoded;
        private const uint DeltaTypeId = AnimationChannelTypeIds.AdaptiveDelta;

        private readonly AssetInput _asset;
        private readonly XNamespace _ns;
        private readonly ReferenceResolver _resolver;
        // Channel-type names come from the AnimationChannelType enum (the single source, shared with the schema
        // domain); see RenderChannelType. No hand-copied name list to drift out of order.

        public W3DAnimationReader(AssetInput asset, XNamespace ns, ReferenceResolver resolver)
        {
            _asset = asset;
            _ns = ns;
            _resolver = resolver;
        }

        public void Read(XElement root)
        {
            // Hierarchy: an AssetReference import at offset 4 (index into the asset's reference list).
            if (_asset.ImportFroms.Contains(4u))
            {
                string hierarchy = ResolveReference(_asset.ReadSlot(4u));
                if (hierarchy != null)
                {
                    root.SetAttributeValue("Hierarchy", hierarchy);
                }
            }
            root.SetAttributeValue("NumFrames", _asset.ReadSlot(8u).ToString(CultureInfo.InvariantCulture));
            root.SetAttributeValue("FrameRate", _asset.ReadSlot(12u).ToString(CultureInfo.InvariantCulture));

            uint count = _asset.ReadSlot(16u);
            uint arrOff = _asset.ReadSlot(20u);
            var channels = new XElement(_ns + "Channels");
            if (count != 0 && _asset.ReloFroms.Contains(20u))
            {
                _asset.CheckRange(arrOff, (long)count * 4, "anim channel array");
                for (uint i = 0; i < count; i++)
                {
                    uint slot = arrOff + i * 4;
                    if (!_asset.ReloFroms.Contains(slot))
                    {
                        continue;
                    }
                    ReadChannel(_asset.ReadSlot(slot), channels);
                }
            }
            root.Add(channels);
        }

        private void ReadChannel(uint off, XElement channels)
        {
            _asset.CheckRange(off, 20, "anim channel base");
            uint typeId = _asset.ReadSlot(off);
            uint type = _asset.ReadSlot(off + 4);
            uint numFrames = _asset.ReadSlot(off + 8);
            uint vectorLen = _asset.ReadSlot(off + 12);
            ushort pivot = BitConverter.ToUInt16(_asset.Instance, (int)(off + 16));

            string elemName = typeId == TimecodedTypeId ? "Timecoded" : typeId == DeltaTypeId ? "Delta" : null;
            if (elemName == null)
            {
                throw new DesyncException($"unknown anim channel TypeId 0x{typeId:x8}@{off}");
            }
            var ch = new XElement(_ns + elemName);
            // No TypeId attribute is emitted: the compiler binds <Timecoded>/<Delta> to EA's own channel types
            // (SchemaSet.BindRuntimeAnimationChannels) and stamps TypeId from the bound schema type, exactly as it
            // does for every other polymorphic element. The element name alone identifies the channel here.
            ch.SetAttributeValue("Pivot", ((uint)pivot).ToString(CultureInfo.InvariantCulture));
            ch.SetAttributeValue("Type", RenderChannelType(type));
            ch.SetAttributeValue("NumFrames", numFrames.ToString(CultureInfo.InvariantCulture));
            ch.SetAttributeValue("VectorLen", vectorLen.ToString(CultureInfo.InvariantCulture));

            if (typeId == TimecodedTypeId)
            {
                uint fabCount = _asset.ReadSlot(off + 20);
                uint fabOff = _asset.ReadSlot(off + 24);
                uint valCount = _asset.ReadSlot(off + 28);
                uint valOff = _asset.ReadSlot(off + 32);
                ch.Add(new XElement(_ns + "FrameAndBinaryFlag", _asset.RenderUShortList(fabOff, fabCount, "anim ushort list")));
                ch.Add(new XElement(_ns + "Values", RenderFloats(valOff, valCount)));
            }
            else
            {
                float scale = BitConverter.ToSingle(_asset.Instance, (int)(off + 20));
                uint initCount = _asset.ReadSlot(off + 24);
                uint initOff = _asset.ReadSlot(off + 28);
                uint numBits = _asset.ReadSlot(off + 32);
                uint cvCount = _asset.ReadSlot(off + 36);
                uint cvOff = _asset.ReadSlot(off + 40);
                ch.SetAttributeValue("Scale", ValueRender.Float(scale));
                ch.SetAttributeValue("Init", RenderFloats(initOff, initCount));
                ch.SetAttributeValue("NumBits", numBits.ToString(CultureInfo.InvariantCulture));
                ch.Add(new XElement(_ns + "CompressedValues", RenderBytes(cvOff, cvCount)));
            }
            channels.Add(ch);
        }

        private static string RenderChannelType(uint type)
        {
            // Single source: the AnimationChannelType enum (same domain the schema declares). A defined value
            // renders to its member name (XTranslation..Visibility); anything else falls back to the numeric
            // form, which stays binary-exact.
            return Enum.IsDefined(typeof(AnimationChannelType), (int)type)
                ? ((AnimationChannelType)(int)type).ToString()
                : type.ToString(CultureInfo.InvariantCulture);
        }

        private string ResolveReference(uint index)
        {
            if (index < (uint)_asset.References.Length)
            {
                (uint t, uint inst) = _asset.References[index];
                string name = _resolver?.ResolveByTypeInstance(t, inst) ?? _resolver?.ResolveByInstance(inst);
                if (name != null)
                {
                    return name;
                }
            }
            return "0x" + index.ToString("x8", CultureInfo.InvariantCulture);
        }

        private string RenderFloats(uint off, uint count)
        {
            if (count == 0)
            {
                return string.Empty;
            }
            _asset.CheckRange(off, (long)count * 4, "anim float list");
            var sb = new StringBuilder();
            for (uint i = 0; i < count; i++)
            {
                if (i > 0) sb.Append(' ');
                sb.Append(ValueRender.Float(BitConverter.ToSingle(_asset.Instance, (int)(off + i * 4))));
            }
            return sb.ToString();
        }

        private string RenderBytes(uint off, uint count)
        {
            if (count == 0)
            {
                return string.Empty;
            }
            _asset.CheckRange(off, count, "anim byte list");
            var sb = new StringBuilder();
            for (uint i = 0; i < count; i++)
            {
                if (i > 0) sb.Append(' ');
                sb.Append(_asset.Instance[(int)(off + i)].ToString(CultureInfo.InvariantCulture));
            }
            return sb.ToString();
        }
    }
}
