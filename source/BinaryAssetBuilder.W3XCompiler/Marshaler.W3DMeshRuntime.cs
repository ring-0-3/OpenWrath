using Relo;
using SageBinaryData;
using System;

// Pass-through marshaling for the PACKED (runtime) form of a W3DMesh's vertex data. A shipped W3DMesh carries a
// compile-time W3DMeshVertexData — the interleaved vertex buffer, the D3D vertex declaration, and the per-mesh
// bone-remap table — produced by W3DMeshProcessor from the authoring <Vertices>/<Normals>/... tags. That packer
// is lossy and order-sensitive (float->D3DCOLOR vertex colours, a default-white colour when none is authored,
// bone-index remapping), so re-running it on decompiled data cannot reproduce the shipped bytes. The decompiler
// therefore emits the packed block verbatim as a runtime <VertexData> element (NumVertices + VertexStride +
// base64 VertexElementData/VertexDeclaration + Bones), and this code writes it straight back into the
// W3DMeshVertexData layout the game loads — byte-for-byte identical, no re-packing. This mirrors the W3DAnimation
// runtime pass-through (Marshaler.W3DRuntime). The physical allocation order below — VertexElementData, then
// VertexDeclaration, then Bones — reproduces W3DMeshProcessor.BuildVertexData's exact Push order so offsets match.
public static partial class Marshaler
{
    // True when the mesh is in the decompiled/runtime form: it carries a packed <VertexData> element, or it has no
    // authoring <Vertices> at all. An authoring mesh (hand-written or SDK source) always has <Vertices>; a
    // decompiled shipped mesh never does. A mesh with neither (a bone/empty mesh whose shipped VertexData pointer
    // is null) is still "runtime" here, and writes a null VertexData pointer.
    public static bool IsRuntimeMesh(Node node)
    {
        if (node.GetChildNode("VertexData", null) is not null)
        {
            return true;
        }
        List vertices = node.GetChildNodes("Vertices");
        return vertices is null || vertices.GetCount() == 0;
    }

    // Write the packed W3DMeshVertexData from the runtime <VertexData> element. Layout (x86), matching
    // W3DMeshProcessor.BuildVertexData's output:
    //   @0  NumVertices (int)
    //   @4  VertexElementData.Count — the per-vertex STRIDE (not a byte count); buffer is NumVertices*stride bytes
    //   @8  VertexElementData.Items     @12 VertexDeclaration.Count (bytes)  @16 VertexDeclaration.Items
    //   @20 Bones.Count (ushorts)       @24 Bones.Items
    public static unsafe void WriteRuntimeVertexData(Node vdNode, W3DMeshVertexData* outputData, Tracker state)
    {
        uint numVertices = ParseUInt(vdNode.GetAttributeValue("NumVertices", "0"));
        uint stride = ParseUInt(vdNode.GetAttributeValue("VertexStride", "0"));
        byte[] ved = ParseBase64(vdNode.GetChildNode("VertexElementData", null)?.GetValue());
        byte[] vd = ParseBase64(vdNode.GetChildNode("VertexDeclaration", null)?.GetValue());
        ushort[] bones = ParseUShortList(vdNode.GetChildNode("Bones", null)?.GetValue());

        uint numVerticesOut = numVertices;
        state.InplaceEndianToPlatform(&numVerticesOut);
        outputData->NumVertices = (int)numVerticesOut;

        uint strideOut = stride;
        state.InplaceEndianToPlatform(&strideOut);
        outputData->VertexElementData.Count = strideOut; // = per-vertex stride, as BuildVertexData stores it

        using (Tracker.Context context = state.Push((void**)&outputData->VertexElementData.Items, 1u, (uint)ved.Length))
        {
            for (int i = 0; i < ved.Length; ++i)
            {
                outputData->VertexElementData.Items[i] = ved[i];
            }
        }

        uint vdCount = (uint)vd.Length;
        state.InplaceEndianToPlatform(&vdCount);
        outputData->VertexDeclaration.Count = vdCount;
        using (Tracker.Context context = state.Push((void**)&outputData->VertexDeclaration.Items, 1u, (uint)vd.Length))
        {
            for (int i = 0; i < vd.Length; ++i)
            {
                outputData->VertexDeclaration.Items[i] = vd[i];
            }
        }

        uint bonesCount = (uint)bones.Length;
        state.InplaceEndianToPlatform(&bonesCount);
        outputData->Bones.Count = bonesCount;
        using (Tracker.Context context = state.Push((void**)&outputData->Bones.Items, 2u, (uint)bones.Length))
        {
            for (int i = 0; i < bones.Length; ++i)
            {
                ushort v = bones[i];
                state.InplaceEndianToPlatform(&v);
                outputData->Bones.Items[i] = v;
            }
        }
    }

    private static byte[] ParseBase64(Value value)
    {
        string text = value?.GetText();
        if (string.IsNullOrWhiteSpace(text))
        {
            return Array.Empty<byte>();
        }
        return Convert.FromBase64String(text.Trim());
    }
}
