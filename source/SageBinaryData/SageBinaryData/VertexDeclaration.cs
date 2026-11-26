namespace SageBinaryData
{
    // The Direct3D 9 vertex-declaration ABI codes (D3DDECLTYPE / D3DDECLMETHOD / D3DDECLUSAGE) that a shipped
    // W3DMeshVertexData's declaration is built from. Single source of truth (CLAUDE.md invariant 3): the W3X
    // compiler packer (W3DMeshProcessor.BuildVertexDeclaration_Windows) WRITES these, and the decompiler's semantic
    // decode (StructReader.ReadSemanticVertexData) READS them back — both reference this one definition rather than
    // re-declaring the codes. These are a fixed external ABI (d3d9types.h), not re-derivable EA format knowledge.
    public enum VertexElementType : byte
    {
        FLOAT1,
        FLOAT2,
        FLOAT3,
        FLOAT4,
        D3DCOLOR,
        UBYTE4,
        SHORT2,
        SHORT4,
        UBYTE4N,
        SHORT2N,
        SHORT4N,
        USHORT2N,
        USHORT4N,
        UDEC3,
        DEC3N,
        FLOAT16_2,
        FLOAT16_4,
        UNUSED
    }

    public enum VertexElementMethod : byte
    {
        DEFAULT,
        PARTIALU,
        PARTIALV,
        CROSSUV,
        UV,
        LOOKUP,
        LOOKUPPRESAMPLED
    }

    public enum VertexElementUsage : byte
    {
        POSITION,
        BLENDWEIGHT,
        BLENDINDICES,
        NORMAL,
        PSIZE,
        TEXCOORD,
        TANGENT,
        BINORMAL,
        TESSFACTOR,
        POSITIONT,
        COLOR,
        FOG,
        DEPTH,
        SAMPLE
    }
}
