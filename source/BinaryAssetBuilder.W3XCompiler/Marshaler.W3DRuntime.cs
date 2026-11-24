using Relo;
using SageBinaryData;
using System;
using System.Collections.Generic;
using System.Globalization;

// Pass-through marshaling for the PRE-COMPRESSED (runtime) form of a W3DAnimation. The authoring form
// (ChannelScalar / ChannelQuaternion with raw per-frame values) is compressed at build time by the
// lossy time-coded / adaptive-delta codecs, so decompress-then-recompress cannot reproduce the shipped
// bytes. The decompiler therefore emits the channels already in their shipped runtime form
// (<Timecoded> / <Delta>), and this code writes them straight into the W3DAnimationRuntime layout the
// game loads — byte-for-byte identical to what shipped, no re-compression. The channel element names map
// (via the schema) to AnimationChannelTimecoded / AnimationChannelDelta, whose FastHash equals the
// shipped channel TypeIds (0x60D8CF69 / 0x77F97305).
public static partial class Marshaler
{
    // Channel discriminators: the single source is SageBinaryData.AnimationChannelTypeIds (shared with the
    // decompiler's W3DAnimationReader and the time-coded/adaptive-delta compressors).
    private const uint TimecodedTypeId = AnimationChannelTypeIds.Timecoded;
    private const uint DeltaTypeId = AnimationChannelTypeIds.AdaptiveDelta;

    // True when this W3DAnimation is in the pre-compressed (runtime) form the game ships and the decompiler
    // emits. The authoring form is distinguished by its channel element names (ChannelScalar /
    // ChannelQuaternion); anything else — <Timecoded>/<Delta> channels, or an empty channel list (both of
    // which only occur in shipped/decompiled data) — is the runtime pass-through form.
    public static bool IsRuntimeAnimation(Node node)
    {
        Node channels = node.GetChildNode("Channels", null);
        if (channels is null)
        {
            return false;
        }
        List scalar = channels.GetChildNodes("ChannelScalar");
        if (scalar is not null && scalar.GetCount() > 0)
        {
            return false;
        }
        List quaternion = channels.GetChildNodes("ChannelQuaternion");
        if (quaternion is not null && quaternion.GetCount() > 0)
        {
            return false;
        }
        return true;
    }

    public static unsafe void MarshalW3DAnimationRuntime(Node node, W3DAnimationRuntime* objT, Tracker state)
    {
        // Base (BaseAssetType) marshals to nothing; the 4-byte slot stays 0, matching the shipped data.
        Marshal(node.GetAttributeValue(nameof(W3DAnimationRuntime.Hierarchy), null), &objT->Hierarchy, state);
        uint numFrames = ParseUInt(node.GetAttributeValue(nameof(W3DAnimationRuntime.NumFrames), "0"));
        state.InplaceEndianToPlatform(&numFrames);
        objT->NumFrames = numFrames;
        uint frameRate = ParseUInt(node.GetAttributeValue(nameof(W3DAnimationRuntime.FrameRate), "0"));
        state.InplaceEndianToPlatform(&frameRate);
        objT->FrameRate = frameRate;

        Node channelsNode = node.GetChildNode("Channels", null);
        List items = channelsNode?.GetChildNodes(null);
        uint count = items is null ? 0u : (uint)items.GetCount();
        AnimationChannelBaseRuntime*** channels = &objT->Channels.Items;
        using Tracker.Context context = state.Push((void**)channels, (uint)sizeof(IntPtr), count, typeof(IntPtr));
        uint channelCount = count;
        state.InplaceEndianToPlatform(&channelCount);
        objT->Channels.Count = channelCount;
        for (uint i = 0; i < count; ++i)
        {
            Node ch = items.GetNextNode();
            uint typeId = ParseUInt(ch.GetAttributeValue("TypeId", "0"));
            switch (typeId)
            {
                case TimecodedTypeId:
                    WriteTimecodedChannel(ch, state, (AnimationChannelTimecoded**)&objT->Channels.Items[i]);
                    break;
                case DeltaTypeId:
                    WriteDeltaChannel(ch, state, (AnimationChannelDelta**)&objT->Channels.Items[i]);
                    break;
                default:
                    throw new BinaryAssetBuilderException(
                        ErrorCode.InternalError,
                        "Unknown runtime animation channel TypeId 0x{0:x8}", typeId);
            }
        }
    }

    private static unsafe void WriteRuntimeChannelBase(Node ch, Tracker state, AnimationChannelBaseRuntime* b, uint typeId)
    {
        state.InplaceEndianToPlatform(&typeId);
        b->TypeId = typeId;
        uint type = (uint)ParseChannelType(ch.GetAttributeValue(nameof(AnimationChannelBaseRuntime.Type), "0"));
        state.InplaceEndianToPlatform(&type);
        b->Type = (AnimationChannelType)type;
        uint numFrames = ParseUInt(ch.GetAttributeValue(nameof(AnimationChannelBaseRuntime.NumFrames), "0"));
        state.InplaceEndianToPlatform(&numFrames);
        b->NumFrames = numFrames;
        uint vectorLen = ParseUInt(ch.GetAttributeValue(nameof(AnimationChannelBaseRuntime.VectorLen), "1"));
        state.InplaceEndianToPlatform(&vectorLen);
        b->VectorLen = vectorLen;
        ushort pivot = (ushort)ParseUInt(ch.GetAttributeValue(nameof(AnimationChannelBaseRuntime.Pivot), "0"));
        state.InplaceEndianToPlatform(&pivot);
        b->Pivot = pivot;
    }

    // [36-byte block][Values: NumFrames*VectorLen floats][FrameAndBinaryFlag: NumFrames ushorts].
    // Values is allocated BEFORE FrameAndBinaryFlag to match the shipped physical layout.
    private static unsafe void WriteTimecodedChannel(Node ch, Tracker state, AnimationChannelTimecoded** objT)
    {
        using Tracker.Context context = state.Push((void**)objT, (uint)sizeof(AnimationChannelTimecoded), 1u, typeof(AnimationChannelTimecoded));
        AnimationChannelTimecoded* result = *objT;
        WriteRuntimeChannelBase(ch, state, &result->Base, TimecodedTypeId);

        float[] values = ParseFloatList(ch.GetChildNode("Values", null)?.GetValue());
        ushort[] fab = ParseUShortList(ch.GetChildNode("FrameAndBinaryFlag", null)?.GetValue());

        uint valueCount = (uint)values.Length;
        uint vc = valueCount;
        state.InplaceEndianToPlatform(&vc);
        result->Values.Count = vc;
        uint fabCount = (uint)fab.Length;
        uint fc = fabCount;
        state.InplaceEndianToPlatform(&fc);
        result->FrameAndBinaryFlag.Count = fc;

        using (Tracker.Context valuesContext = state.Push((void**)&result->Values.Items, sizeof(float), valueCount))
        {
            for (uint i = 0; i < valueCount; ++i)
            {
                float v = values[i];
                state.InplaceEndianToPlatform((uint*)&v);
                result->Values.Items[i] = v;
            }
        }
        using (Tracker.Context fabContext = state.Push((void**)&result->FrameAndBinaryFlag.Items, sizeof(ushort), fabCount))
        {
            for (uint i = 0; i < fabCount; ++i)
            {
                ushort v = fab[i];
                state.InplaceEndianToPlatform(&v);
                result->FrameAndBinaryFlag.Items[i] = v;
            }
        }
    }

    // [44-byte block][Init: VectorLen floats][CompressedValues: N bytes]. Init before CompressedValues.
    private static unsafe void WriteDeltaChannel(Node ch, Tracker state, AnimationChannelDelta** objT)
    {
        using Tracker.Context context = state.Push((void**)objT, (uint)sizeof(AnimationChannelDelta), 1u, typeof(AnimationChannelDelta));
        AnimationChannelDelta* result = *objT;
        WriteRuntimeChannelBase(ch, state, &result->Base, DeltaTypeId);

        float scale = ParseFloat(ch.GetAttributeValue(nameof(AnimationChannelDelta.Scale), "0").GetText());
        state.InplaceEndianToPlatform((uint*)&scale);
        result->Scale = scale;

        float[] init = ParseFloatList(ch.GetAttributeValue(nameof(AnimationChannelDelta.Init), ""));
        byte[] compressed = ParseByteList(ch.GetChildNode("CompressedValues", null)?.GetValue());

        uint numBits = ParseUInt(ch.GetAttributeValue(nameof(AnimationChannelDelta.NumBits), "0"));
        state.InplaceEndianToPlatform(&numBits);
        result->NumBits = numBits;
        uint initCount = (uint)init.Length;
        uint ic = initCount;
        state.InplaceEndianToPlatform(&ic);
        result->Init.Count = ic;
        uint compressedCount = (uint)compressed.Length;
        uint cc = compressedCount;
        state.InplaceEndianToPlatform(&cc);
        result->CompressedValues.Count = cc;

        using (Tracker.Context initContext = state.Push((void**)&result->Init.Items, sizeof(float), initCount))
        {
            for (uint i = 0; i < initCount; ++i)
            {
                float v = init[i];
                state.InplaceEndianToPlatform((uint*)&v);
                result->Init.Items[i] = v;
            }
        }
        using (Tracker.Context compressedContext = state.Push((void**)&result->CompressedValues.Items, sizeof(byte), compressedCount))
        {
            for (uint i = 0; i < compressedCount; ++i)
            {
                result->CompressedValues.Items[i] = compressed[i];
            }
        }
    }

    // ---- small parse helpers (invariant culture; whitespace-separated lists) --------------------------

    private static uint ParseUInt(Value value)
    {
        string text = value?.GetText();
        return string.IsNullOrEmpty(text) ? 0u : uint.Parse(text, CultureInfo.InvariantCulture);
    }

    private static AnimationChannelType ParseChannelType(Value value)
    {
        string text = value?.GetText();
        if (string.IsNullOrEmpty(text))
        {
            return AnimationChannelType.XTranslation;
        }
        // Accept both the enum name (XTranslation, Orientation, ...) and a bare ordinal.
        if (uint.TryParse(text, NumberStyles.Integer, CultureInfo.InvariantCulture, out uint ordinal))
        {
            return (AnimationChannelType)ordinal;
        }
        return Enum.Parse<AnimationChannelType>(text);
    }

    private static float ParseFloat(string text)
    {
        if (string.IsNullOrEmpty(text))
        {
            return 0.0f;
        }
        return float.Parse(text, NumberStyles.Float, CultureInfo.InvariantCulture);
    }

    private static float[] ParseFloatList(Value value)
    {
        return ParseFloatList(value?.GetText());
    }

    private static float[] ParseFloatList(string text)
    {
        if (string.IsNullOrWhiteSpace(text))
        {
            return Array.Empty<float>();
        }
        string[] tokens = text.Split((char[])null, StringSplitOptions.RemoveEmptyEntries);
        var result = new float[tokens.Length];
        for (int i = 0; i < tokens.Length; ++i)
        {
            result[i] = ParseFloat(tokens[i]);
        }
        return result;
    }

    private static ushort[] ParseUShortList(Value value)
    {
        string text = value?.GetText();
        if (string.IsNullOrWhiteSpace(text))
        {
            return Array.Empty<ushort>();
        }
        string[] tokens = text.Split((char[])null, StringSplitOptions.RemoveEmptyEntries);
        var result = new ushort[tokens.Length];
        for (int i = 0; i < tokens.Length; ++i)
        {
            result[i] = ushort.Parse(tokens[i], CultureInfo.InvariantCulture);
        }
        return result;
    }

    private static byte[] ParseByteList(Value value)
    {
        string text = value?.GetText();
        if (string.IsNullOrWhiteSpace(text))
        {
            return Array.Empty<byte>();
        }
        string[] tokens = text.Split((char[])null, StringSplitOptions.RemoveEmptyEntries);
        var result = new byte[tokens.Length];
        for (int i = 0; i < tokens.Length; ++i)
        {
            result[i] = byte.Parse(tokens[i], CultureInfo.InvariantCulture);
        }
        return result;
    }
}
