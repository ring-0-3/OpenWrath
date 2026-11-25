using Relo;
using SageBinaryData;
using System;

// Pass-through marshaling for the shipped runtime Texture / OnDemandTexture records (findings 0023/0024). A shipped
// Texture carries a LITERAL complete D3D9 .dds file as its payload — the compile-time output of EA's DXT compressor
// + mip generator, which is lossy and not bit-reproducible — so, exactly as with W3DMesh's packed vertex data
// (Marshaler.W3DMeshRuntime), we never re-encode: the decompiler emits the shipped DDS bytes verbatim as a
// <Payload> base64 element (StructReader.ReadTexturePayload) and this code writes them straight back into the
// DataBlob the game loads. That gives byte-exact for SHIPPED textures without reimplementing the compressor;
// authoring NEW textures is stated-tier and out of scope. OnDemandTexture is the lazy twin: an 8-byte all-zero
// placeholder (null payload pointer, streamed on demand by id/name), so it marshals to nothing but the Base slot.
public static partial class Marshaler
{
    public static unsafe void Marshal(Node node, Texture* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        // Runtime pass-through: <Payload> carries the shipped DDS bytes verbatim as base64. The length is derived
        // from the actual blob (never a baked sampled value), and written as Payload.Size AFTER the Data pointer to
        // match the shipped {Data ptr @+0, Size @+4} field order.
        byte[] payload = ParseTexturePayload(node.GetChildNode(nameof(Texture.Payload), null)?.GetValue());
        uint size = (uint)payload.Length;
        state.InplaceEndianToPlatform(&size);
        objT->Payload.Size = size;
        if (payload.Length > 0)
        {
            using Tracker.Context context = state.Push(&objT->Payload.Data, 1u, (uint)payload.Length);
            Span<byte> span = new Span<byte>(objT->Payload.Data, payload.Length);
            payload.CopyTo(span);
        }
        Marshal(node, (BaseAssetType*)objT, state);
    }

    public static unsafe void Marshal(Node node, OnDemandTexture* objT, Tracker state)
    {
        if (node is null)
        {
            return;
        }
        // The lazy twin stores only identity: a null payload pointer (resolved on demand at runtime) that stays
        // null here -> no relocation, reproducing the shipped 8-byte all-zero record. Only the Base slot is written.
        Marshal(node, (BaseAssetType*)objT, state);
    }

    // Decode the <Payload> element's base64 text into the raw DDS bytes. First (and only) base64 consumer in the
    // XmlCompiler marshaler; the W3DMeshRuntime helper of the same shape lives in a separate plugin assembly.
    private static byte[] ParseTexturePayload(Value value)
    {
        string text = value?.GetText();
        if (string.IsNullOrWhiteSpace(text))
        {
            return Array.Empty<byte>();
        }
        return Convert.FromBase64String(text.Trim());
    }
}
