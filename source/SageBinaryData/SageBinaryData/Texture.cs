using Relo;
using System.Runtime.InteropServices;

namespace SageBinaryData
{
    // Shipped runtime Texture record (findings 0023/0024). Byte-inspected over all 1575 shipped static_common
    // instances: a 12-byte header then a LITERAL, complete D3D9 .dds file (128-byte header + full mip chain):
    //   @0x00  BaseAssetType Base   (= 0; the universal 4-byte zeroed AssetIdInfo slot every asset carries)
    //   @0x04  Payload.Data  (ptr)  (= 12; one 04000000 relocation -> the payload bytes)
    //   @0x08  Payload.Size  (uint) (= instanceSize - 12)
    //   @0x0C  DDS bytes
    // DataBlob is the shared {void* Data; uint Size} = PTR-THEN-LENGTH shape (NOT the List<byte> {Count,Items}
    // convention) — exactly the shipped field order, and it collapses to 4+4=8 x86 bytes so the header is 12.
    // The recon's "Flags@0x00" is this Base placeholder, not a separate field: the relocated payload pointer sits
    // at offset 4 (relo "04000000"), leaving no room for a Flags word before it. The payload is passed through
    // VERBATIM (the 0018 W3DMesh pattern — no DXT re-encode), so SHIPPED textures round-trip byte-exact; authoring
    // NEW textures is stated-tier (EA's DXT compressor + mip generator is not bit-reproducible) and out of scope.
    [StructLayout(LayoutKind.Sequential)]
    public struct Texture
    {
        [StructLayout(LayoutKind.Sequential)]
        public struct Factory
        {

        }
        public BaseAssetType Base;
        public DataBlob Payload;
    }

    // Shipped runtime OnDemandTexture record (findings 0023/0024). The lazy twin carries NO pixel payload in the
    // stream: all 123 shipped static_common instances are exactly 8 bytes, all zero, with rds=0 (no relocation).
    // Modeled as the BaseAssetType placeholder + a null payload pointer (4 + 4 = 8 x86 bytes); because the pointer
    // is never allocated it stays null -> no relocation, reproducing the 8-zero-byte shape. The engine streams the
    // actual pixels on demand, resolving them by the record's id/name (1:1 with the OnDemandTextureImage atlas
    // records of finding 0022).
    [StructLayout(LayoutKind.Sequential)]
    public struct OnDemandTexture
    {
        [StructLayout(LayoutKind.Sequential)]
        public struct Factory
        {

        }
        public BaseAssetType Base;
        public unsafe byte* Payload;
    }
}
