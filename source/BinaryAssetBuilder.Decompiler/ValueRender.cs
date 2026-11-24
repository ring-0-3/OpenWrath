using System.Globalization;

namespace BinaryAssetBuilder.Decompiler
{
    // Single source for primitive value -> XSD-safe text rendering, shared by StructReader and the
    // type-specific readers (e.g. W3DAnimationReader). Keeping one copy means the round-trip spelling
    // (especially the infinity/NaN edge cases) can't drift between readers.
    internal static class ValueRender
    {
        // Float -> shortest round-trippable text. xs:float rejects .NET's "Infinity"/"-Infinity" spellings,
        // and float.Parse rejects XSD's "INF"; emit an out-of-range magnitude BOTH accept and that parses back
        // to the same ±infinity bit pattern. NaN is spelled identically by both. Finite floats format
        // shortest-round-trippable by default on .NET Core.
        public static string Float(float v)
        {
            if (float.IsPositiveInfinity(v)) return "1e39";
            if (float.IsNegativeInfinity(v)) return "-1e39";
            if (float.IsNaN(v)) return "NaN";
            return v.ToString(CultureInfo.InvariantCulture);
        }
    }
}
