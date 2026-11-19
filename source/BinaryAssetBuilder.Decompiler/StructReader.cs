using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Xml.Linq;
using BinaryAssetBuilder.Decompiler.Containers;
using Relo;

namespace BinaryAssetBuilder.Decompiler
{
    // The generic binary -> XML read-walk. It is the structural inverse of the compiler's marshal/Compact
    // path: for a struct type T it walks TypeLayout.Get(T).Fields (same field map, declaration order) and reads
    // each field at its on-disk (x86) offset, following the relocation graph for pointer fields. Values are
    // rendered by inverting the primitive Marshaler overloads; container generics are read by their fixed
    // on-disk shapes. No per-type decompile code is needed — one walker reads every type.
    public sealed class StructReader
    {
        private readonly AssetInput _asset;
        private readonly TypeRegistry _registry;   // reserved for Phase 4 (polymorphic modules)
        private readonly XNamespace _ns;
        private readonly SchemaIndex _schema;
        private readonly System.Collections.Generic.IReadOnlyDictionary<string, Type> _enumsByName;
        private readonly ReferenceResolver _resolver;
        private readonly StringHashTable _strings;

        public StructReader(AssetInput asset, TypeRegistry registry, XNamespace ns,
            SchemaIndex schema, System.Collections.Generic.IReadOnlyDictionary<string, Type> enumsByName,
            ReferenceResolver resolver, StringHashTable strings)
        {
            _asset = asset;
            _registry = registry;
            _ns = ns;
            _schema = schema;
            _enumsByName = enumsByName;
            _resolver = resolver;
            _strings = strings;
        }

        // A pending AssetReference attribute and its recorded import index, so we can order references within an
        // element by that index. The compiler assigns import indices in XML document order (SelectDescendants ->
        // each element's attributes in order), so to reproduce EA's exact index values our emitted AssetReference
        // attributes must appear in ascending recorded-index order within their element.
        private readonly struct RefAttr
        {
            public readonly XAttribute Attribute;
            public readonly uint Index;
            public RefAttr(XAttribute a, uint i) { Attribute = a; Index = i; }
        }

        // Read a whole struct instance into `target` (attributes + child elements appended to it). This is one
        // XML element; AssetReference attributes collected during the walk (including inlined base chains) are
        // reordered by import index at the end.
        public void ReadStruct(Type t, uint baseOff, XElement target)
        {
            var refs = new System.Collections.Generic.List<RefAttr>();
            ReadStructInto(t, baseOff, target, refs);
            if (refs.Count > 1)
            {
                foreach (RefAttr r in refs) r.Attribute.Remove();
                foreach (RefAttr r in refs.OrderBy(r => r.Index)) target.Add(r.Attribute);
            }
        }

        private void ReadStructInto(Type t, uint baseOff, XElement target, System.Collections.Generic.List<RefAttr> refs)
        {
            TypeLayout layout = TypeLayout.Get(t);
            if (layout.Fields == null)
            {
                return; // scalar/empty (e.g. BaseAssetType Size=4) — nothing to emit
            }
            // Every struct's own bytes must lie within the instance. If a base offset lands past the end, the
            // walk has desynced (foreign/mismatched schema) — bail to the raw fallback instead of reading garbage.
            _asset.CheckRange(baseOff, layout.SizeX86, "struct " + t.Name);
            // Attributes the XSD declares for this type (null => schema unavailable/unknown => emit unfiltered).
            HashSet<string> attrSet = _schema?.GetDeclaredAttributeNames(t.Name);
            foreach (TypeLayout.FieldLayout f in layout.Fields)
            {
                ReadField(f, baseOff + f.X86Off, target, attrSet, refs);
            }
        }

        // Emit an attribute only if the schema declares it for the current type (or the schema is unavailable).
        // Struct fields the XSD omits are always at their compile-default in real data, so skipping them keeps
        // the recompile byte-exact and avoids "attribute not declared" validation errors.
        private static void SetAttr(XElement target, HashSet<string> attrSet, string name, string value)
        {
            if (attrSet == null || name == "id" || attrSet.Contains(name))
            {
                target.SetAttributeValue(name, value);
            }
        }

        private void ReadField(TypeLayout.FieldLayout f, uint off, XElement target, HashSet<string> attrSet, System.Collections.Generic.List<RefAttr> refs)
        {
            FieldInfo fi = f.Field;
            if (fi == null)
            {
                return;
            }
            Type ft = fi.FieldType;
            string name = fi.Name;

            // --- base / id-carrier structs: contribute layout bytes but no XML (id lives on the element) ---
            if (ft == typeof(SageBinaryData.BaseInheritableAsset) || ft == typeof(SageBinaryData.BaseAssetType))
            {
                return;
            }

            // --- a polymorphic module's dispatch marker (ModuleData.TypeId): never emitted — validation
            //     re-stamps it from the module's element name on recompile. (ModuleData.id is emitted below.)
            if (fi.DeclaringType == typeof(SageBinaryData.ModuleData) && name == "TypeId")
            {
                return;
            }

            // --- pointer fields: the slot holds the on-disk offset of the pointee (a relocation). GameObject
            //     reaches almost all of its content through pointers (module lists, sub-structs, string lists). ---
            if (f.Kind == TypeLayout.Kind.Pointer && ft.IsPointer)
            {
                ReadPointerField(ft.GetElementType(), off, name, target, attrSet, refs);
                return;
            }

            // --- enums: written by name ---
            if (ft.IsEnum)
            {
                SetAttr(target, attrSet, name, RenderEnum(ft, off, f.X86Size));
                return;
            }

            // --- container generics (List / PolymorphicList / String / AssetReference / DataBlob) ---
            if (ft.IsGenericType)
            {
                Type gtd = ft.GetGenericTypeDefinition();
                if (gtd == typeof(Relo.List<>))
                {
                    ReadList(ft.GetGenericArguments()[0], off, name, target, attrSet);
                    return;
                }
                if (gtd == typeof(String<>))
                {
                    ReadString(ft.GetGenericArguments()[0], off, name, target, attrSet);
                    return;
                }
                if (gtd == typeof(PolymorphicList<>))
                {
                    ReadPolymorphicList(ft.GetGenericArguments()[0], off, name, target);
                    return;
                }
                if (gtd == typeof(AssetReference<>) || gtd == typeof(AssetReference<,>))
                {
                    EmitReference(target, attrSet, name, off, refs);
                    return;
                }
                if (gtd == typeof(TypedAssetId<>))
                {
                    SetAttr(target, attrSet, name, RenderTypedAssetId(off));
                    return;
                }
            }

            if (ft == typeof(DataBlob))
            {
                ReadDataBlob(off, name, target, attrSet);
                return;
            }

            // --- bit-flag bitset structs (e.g. LocomotorSurfaceBitFlags) -> space-separated token attribute ---
            if (IsBitFlagsStruct(ft))
            {
                SetAttr(target, attrSet, name, RenderBitFlags(ft, off, f.X86Size));
                return;
            }

            // --- scalar / known wrapper value types -> attribute ---
            string scalar = RenderScalar(ft, off, f);
            if (scalar != null)
            {
                SetAttr(target, attrSet, name, scalar);
                return;
            }

            // --- raw fixed buffer (non-bitflag) -> hex spans (rare; refined if a round-trip needs it) ---
            if (f.Kind == TypeLayout.Kind.FixedBuffer)
            {
                SetAttr(target, attrSet, name, RenderFixedBufferRaw(off, f.X86Size));
                return;
            }

            // --- nested struct ---
            if (f.Kind == TypeLayout.Kind.Nested)
            {
                if (name == "Base")
                {
                    // The polymorphic / inheritance base chain is marshaled onto the SAME node
                    // (Marshal(node, (BaseType*)objT)) — inline its fields into the current element, sharing the
                    // reference collector so base-chain references order together with this element's.
                    ReadStructInto(ft, off, target, refs);
                }
                else
                {
                    // A distinct nested value struct (Color3f, Coord2D, RealRange, ...) is a child element
                    // whose sub-fields are its attributes.
                    var child = new XElement(_ns + name);
                    ReadStruct(ft, off, child);
                    target.Add(child);
                }
            }
        }

        // ---- containers ----------------------------------------------------------------------------------

        private void ReadList(Type elem, uint off, string name, XElement target, HashSet<string> attrSet)
        {
            uint count = _asset.ReadSlot(off);
            uint itemsOff = _asset.ReadSlot(off + 4);
            if (count == 0 || !_asset.ReloFroms.Contains(off + 4))
            {
                return; // empty list -> emit nothing
            }
            uint stride = TypeLayout.Get(elem).SizeX86;
            _asset.CheckRange(itemsOff, (long)count * stride, "list<" + elem.Name + ">");
            Type elemGtd = elem.IsGenericType ? elem.GetGenericTypeDefinition() : null;
            if (elemGtd == typeof(TypedAssetId<>))
            {
                // List<TypedAssetId> (e.g. ObjectFilter.IncludeThing, GameObject.EquivalentTo): each item is a
                // separate child element whose TEXT content is the referenced asset name (GetChildNodes + text).
                for (uint i = 0; i < count; i++)
                {
                    target.Add(new XElement(_ns + name, RenderTypedAssetId(itemsOff + i * stride) ?? ""));
                }
            }
            else if (elemGtd == typeof(AssetReference<>) || elemGtd == typeof(AssetReference<,>))
            {
                // List<AssetReference> (e.g. UpgradeMux.TriggeredBy): each item is a child element whose TEXT is
                // the referenced name. Each is an import (index -> name); emitted in list (document) order.
                for (uint i = 0; i < count; i++)
                {
                    uint slot = itemsOff + i * stride;
                    string val = _asset.ImportFroms.Contains(slot) ? RenderReferenceName(_asset.ReadSlot(slot)) : "";
                    target.Add(new XElement(_ns + name, val));
                }
            }
            else if (IsScalarLike(elem))
            {
                // List<scalar> is authored as whitespace-joined text in a single attribute.
                var sb = new StringBuilder();
                for (uint i = 0; i < count; i++)
                {
                    if (i > 0) sb.Append(' ');
                    sb.Append(RenderScalarLike(elem, itemsOff + i * stride));
                }
                SetAttr(target, attrSet, name, sb.ToString());
            }
            else
            {
                for (uint i = 0; i < count; i++)
                {
                    var child = new XElement(_ns + name);
                    ReadStruct(elem, itemsOff + i * stride, child);
                    target.Add(child);
                }
            }
        }

        private void ReadString(Type charType, uint off, string name, XElement target, HashSet<string> attrSet)
        {
            string s = ReadStringValue(charType, off);
            if (s == null)
            {
                return; // empty/absent
            }
            // Some string fields are XSD child elements with text content, not attributes (e.g.
            // GameObject.DisplayName = <DisplayName>text</DisplayName>). If the schema declares the name as an
            // attribute, emit an attribute; otherwise (set but not a declared attribute) it is a text element.
            if (attrSet != null && !attrSet.Contains(name))
            {
                target.Add(new XElement(_ns + name, s));
            }
            else
            {
                SetAttr(target, attrSet, name, s);
            }
        }

        // Read a Relo.String<T> ({int Length; ptr Target}) at `off`; null if the string is empty/absent.
        private string ReadStringValue(Type charType, uint off)
        {
            int length = (int)_asset.ReadSlot(off);
            uint targetOff = _asset.ReadSlot(off + 4);
            if (length == 0 || !_asset.ReloFroms.Contains(off + 4))
            {
                return null; // empty string -> matches an omitted attribute
            }
            _asset.CheckRange(targetOff, charType == typeof(sbyte) ? length : (long)length * 2, "string");
            return charType == typeof(sbyte)
                ? Encoding.ASCII.GetString(_asset.Instance, (int)targetOff, length)
                : Encoding.Unicode.GetString(_asset.Instance, (int)targetOff, length * 2);
        }

        // A pointer field: the slot at `off` holds the on-disk offset of the pointee (recorded as a relocation),
        // or 0 when the pointer is null. We dispatch on the pointee type and read it at the followed offset,
        // reusing the same readers as the inline (value-field) forms.
        private void ReadPointerField(Type elem, uint off, string name, XElement target, HashSet<string> attrSet, System.Collections.Generic.List<RefAttr> refs)
        {
            if (!_asset.ReloFroms.Contains(off))
            {
                return; // null pointer -> emit nothing
            }
            uint to = _asset.ReadSlot(off);

            if (elem.IsGenericType)
            {
                Type gtd = elem.GetGenericTypeDefinition();
                if (gtd == typeof(PolymorphicList<>)) { ReadPolymorphicList(elem.GetGenericArguments()[0], to, name, target); return; }
                if (gtd == typeof(Relo.List<>)) { ReadList(elem.GetGenericArguments()[0], to, name, target, attrSet); return; }
                if (gtd == typeof(String<>)) { ReadString(elem.GetGenericArguments()[0], to, name, target, attrSet); return; }
                // Pointer to a single reference/id wrapper (e.g. WeaponTemplate.FireSound*) -> attribute at the
                // followed offset, where the import index / id hash lives.
                if (gtd == typeof(AssetReference<>) || gtd == typeof(AssetReference<,>)) { EmitReference(target, attrSet, name, to, refs); return; }
                if (gtd == typeof(TypedAssetId<>)) { SetAttr(target, attrSet, name, RenderTypedAssetId(to)); return; }
            }

            // A pointer to a polymorphic module base (e.g. GameObject.Body / .AI) = a single module, wrapped in
            // an element named after the field (<Body><ActiveBody .../></Body>).
            if (typeof(IPolymorphic).IsAssignableFrom(elem))
            {
                var wrapper = new XElement(_ns + name);
                if (EmitModule(to, wrapper))
                {
                    target.Add(wrapper);
                }
                return;
            }

            if (elem == typeof(DataBlob)) { ReadDataBlob(to, name, target, attrSet); return; }

            // A pointer to a scalar / wrapper value -> attribute at the followed offset.
            if (elem.IsEnum) { SetAttr(target, attrSet, name, RenderEnum(elem, to, TypeLayout.Get(elem).SizeX86)); return; }
            string scalar = RenderScalar(elem, to, null);
            if (scalar != null) { SetAttr(target, attrSet, name, scalar); return; }

            // A pointer to a plain nested struct (BuildableStatus, Coord3D, Geometry, ...) -> child element.
            var child = new XElement(_ns + name);
            ReadStruct(elem, to, child);
            target.Add(child);
        }

        // PolymorphicList<T> at `listOff` = {uint Count; ptr ItemsArray}. ItemsArray = Count 4-byte pointers,
        // each a relocation to a module item block whose offset 0 = the module's TypeId hash. Emits one wrapper
        // element (field name) containing a child element per module (name resolved from the type). Empty => none.
        private void ReadPolymorphicList(Type baseElem, uint listOff, string name, XElement target)
        {
            uint count = _asset.ReadSlot(listOff);
            uint arrOff = _asset.ReadSlot(listOff + 4);
            if (count == 0 || !_asset.ReloFroms.Contains(listOff + 4))
            {
                return; // empty list -> emit nothing
            }
            _asset.CheckRange(arrOff, (long)count * 4, "polylist<" + baseElem.Name + ">");
            _ = baseElem;
            var wrapper = new XElement(_ns + name);
            for (uint i = 0; i < count; i++)
            {
                uint slotOff = arrOff + i * 4;
                if (!_asset.ReloFroms.Contains(slotOff))
                {
                    continue; // null item pointer (shouldn't happen) -> skip
                }
                EmitModule(_asset.ReadSlot(slotOff), wrapper);
            }
            target.Add(wrapper);
        }

        // Read one polymorphic module item at `itemOff`: offset 0 = FastHash(concrete C# struct name). Resolve to
        // the type, emit a child element named by the module's authoring (XSD element) name, and recurse. Returns
        // false (emitting a labelled comment) when the module type is unknown, so the rest of the asset survives.
        private bool EmitModule(uint itemOff, XElement wrapper)
        {
            uint hash = _asset.ReadSlot(itemOff);
            if (!_registry.TryGet(hash, out Type moduleType))
            {
                // Unknown module type (foreign/newer schema): emit a labelled placeholder and keep going, so the
                // rest of the GameObject still decompiles. Counted in the stream summary.
                var unknown = new XElement(_ns + "UnknownModule");
                unknown.SetAttributeValue("TypeId", "0x" + hash.ToString("x8", CultureInfo.InvariantCulture));
                unknown.SetAttributeValue("reason", "unknown-module");
                wrapper.Add(unknown);
                return true;
            }
            string elemName = _schema?.GetElementNameForType(moduleType.Name) ?? moduleType.Name;
            var child = new XElement(_ns + elemName);
            ReadStruct(moduleType, itemOff, child);
            wrapper.Add(child);
            return true;
        }

        private void ReadDataBlob(uint off, string name, XElement target, HashSet<string> attrSet)
        {
            uint dataOff = _asset.ReadSlot(off);
            uint size = _asset.ReadSlot(off + 4);
            if (size == 0 || !_asset.ReloFroms.Contains(off))
            {
                return;
            }
            _asset.CheckRange(dataOff, size, "datablob");
            var bytes = new byte[size];
            Buffer.BlockCopy(_asset.Instance, (int)dataOff, bytes, 0, (int)size);
            SetAttr(target, attrSet, name, Convert.ToBase64String(bytes));
        }

        // ---- value rendering (inverse of the primitive Marshaler overloads) ------------------------------

        // Returns the rendered string for scalars and known wrapper value types, or null if `ft` is not one
        // the renderer handles (so the caller can fall through to nested/container handling).
        private string RenderScalar(Type ft, uint off, TypeLayout.FieldLayout f)
        {
            // primitives
            if (ft == typeof(float)) return RenderFloat(BitConverter.ToSingle(_asset.Instance, (int)off));
            if (ft == typeof(int)) return BitConverter.ToInt32(_asset.Instance, (int)off).ToString(CultureInfo.InvariantCulture);
            if (ft == typeof(uint)) return BitConverter.ToUInt32(_asset.Instance, (int)off).ToString(CultureInfo.InvariantCulture);
            if (ft == typeof(short)) return BitConverter.ToInt16(_asset.Instance, (int)off).ToString(CultureInfo.InvariantCulture);
            if (ft == typeof(ushort)) return BitConverter.ToUInt16(_asset.Instance, (int)off).ToString(CultureInfo.InvariantCulture);
            if (ft == typeof(byte)) return _asset.Instance[(int)off].ToString(CultureInfo.InvariantCulture);
            if (ft == typeof(sbyte)) return ((sbyte)_asset.Instance[(int)off]).ToString(CultureInfo.InvariantCulture);
            if (ft == typeof(bool)) return _asset.Instance[(int)off] != 0 ? "true" : "false";

            // known SAGE wrapper value types (each inverts the matching primitive Marshaler overload)
            switch (ft.Name)
            {
                // Percentage: stored = parse * 0.01f  ->  emit pre-image * "%"
                case "Percentage": return RenderFloat(InvertScale(BitConverter.ToSingle(_asset.Instance, (int)off), 0.01f)) + "%";
                // Angle is stored in radians; the 'r' postfix selects multiplier 1.0, so the stored float is
                // the pre-image. The suffix is also required by the XSD Angle pattern. Likewise Time is stored
                // in seconds and the 's' postfix selects multiplier 1.0 (and satisfies the Time pattern).
                case "Angle": return RenderFloat(BitConverter.ToSingle(_asset.Instance, (int)off)) + "r";
                case "Time": return RenderFloat(BitConverter.ToSingle(_asset.Instance, (int)off)) + "s";
                // Velocity: stored = parse * SECONDS_PER_LOGICFRAME_REAL
                case "Velocity": return RenderFloat(InvertScale(BitConverter.ToSingle(_asset.Instance, (int)off), SecondsPerLogicFrame));
                // Duration: stored(frames) = ceil(ms * 5/1000). Lossy ms->frames; emit a canonical ms that
                // re-ceilings to the same frame count (binary-exact, original ms text unrecoverable).
                case "Duration": return InvertDuration(BitConverter.ToUInt32(_asset.Instance, (int)off));
                case "SageBool": return _asset.Instance[(int)off] != 0 ? "true" : "false";
                case "StringHash": return RenderStringHash(off);
            }
            return null;
        }

        private bool IsScalarLike(Type t)
        {
            if (t.IsEnum || t.IsPrimitive) return true;
            // AnsiString / WideString are Relo.String<sbyte|char>; their runtime name is "String`1", not the
            // alias, so match the generic definition. A list of them is authored as whitespace-joined text.
            if (t.IsGenericType && t.GetGenericTypeDefinition() == typeof(String<>)) return true;
            switch (t.Name)
            {
                case "Percentage":
                case "SageBool":
                case "StringHash":
                    return true;
                default:
                    return false;
            }
        }

        private string RenderScalarLike(Type t, uint off)
        {
            if (t.IsEnum) return RenderEnum(t, off, TypeLayout.Get(t).SizeX86);
            if (t.IsGenericType && t.GetGenericTypeDefinition() == typeof(String<>))
            {
                return ReadStringValue(t.GetGenericArguments()[0], off) ?? "";
            }
            return RenderScalar(t, off, null) ?? "0";
        }

        // A bit-flag bitset struct: exactly one instance field, a `fixed uint Value[N]` span array, authored as
        // space-separated tokens. Detected structurally (not by name) because the suffix varies — "BitFlags"
        // (LocomotorSurfaceBitFlags) and "BitMask" (ObjectFilterRelationshipBitMask) are both bitsets.
        private static bool IsBitFlagsStruct(Type t)
        {
            if (!t.IsValueType || t.IsPrimitive || t.IsEnum || t.IsGenericType)
            {
                return false;
            }
            TypeLayout.FieldLayout[] fl = TypeLayout.Get(t).Fields;
            return fl != null && fl.Length == 1 && fl[0].Kind == TypeLayout.Kind.FixedBuffer;
        }

        // Decode the span array into the set bits, emitted as the paired enum's member names (space separated).
        // The XSD validates flag attributes against that enum, so names — not numeric indices — are required.
        // The enum is found via the schema (<xs:list itemType="Enum">); a missing mapping falls back to the
        // numeric index (which the harness will flag). Always emitted (even empty) so a non-zero schema default
        // cannot leak in on recompile.
        private string RenderBitFlags(Type flagsType, uint off, uint size)
        {
            // Resolve the paired enum's member names. The compiler parses each flag token through the C# enum and
            // uses its VALUE as the bit (see Marshaler.BitFlagsData.cs), so the C# enum is authoritative: prefer
            // Enum.GetName(value) when the enum is resolvable. The XSD enumeration-facet list is only a fallback —
            // some C# enums (e.g. ModelConditionFlagType with INVALID=-1) diverge from the facet order past a
            // point, and some XSD itemType names don't match any C# enum (KindOfType vs C# KindOf), where the
            // facet list (index == bit) is the right source.
            string itemEnum = _schema?.GetBitFlagItemEnum(flagsType.Name);
            Type enumType = null;
            if (itemEnum != null)
            {
                _enumsByName?.TryGetValue(itemEnum, out enumType);
            }
            System.Collections.Generic.List<string> xsdNames = _schema?.GetEnumValues(itemEnum);

            // The "ALL" token sets every span to 0xFFFFFFFF (Marshaler.BitFlagsData.cs). Reproduce it exactly:
            // all-bits-set round-trips as "ALL", whereas enumerating each bit would emit unnamed high bits as
            // numbers the XSD rejects.
            uint spans = size / 4;
            bool allSet = spans > 0;
            for (uint s = 0; s < spans; s++)
            {
                if (_asset.ReadSlot(off + s * 4) != 0xFFFFFFFFu) { allSet = false; break; }
            }
            if (allSet)
            {
                return "ALL";
            }

            var sb = new StringBuilder();
            for (uint s = 0; s < spans; s++)
            {
                uint span = _asset.ReadSlot(off + s * 4);
                for (int b = 0; b < 32; b++)
                {
                    if ((span & (1u << b)) == 0)
                    {
                        continue;
                    }
                    uint bit = s * 32 + (uint)b;
                    string token = enumType != null ? Enum.GetName(enumType, Enum.ToObject(enumType, bit)) : null;
                    if (token == null && xsdNames != null && bit < xsdNames.Count)
                    {
                        token = xsdNames[(int)bit];
                    }
                    token ??= bit.ToString(CultureInfo.InvariantCulture);
                    if (sb.Length > 0) sb.Append(' ');
                    sb.Append(token);
                }
            }
            return sb.ToString();
        }

        private string RenderEnum(Type enumType, uint off, uint size)
        {
            Type u = Enum.GetUnderlyingType(enumType);
            long value = u == typeof(byte) ? _asset.Instance[(int)off]
                : u == typeof(short) ? BitConverter.ToInt16(_asset.Instance, (int)off)
                : u == typeof(ushort) ? BitConverter.ToUInt16(_asset.Instance, (int)off)
                : u == typeof(uint) ? BitConverter.ToUInt32(_asset.Instance, (int)off)
                : BitConverter.ToInt32(_asset.Instance, (int)off);
            string n = Enum.GetName(enumType, Enum.ToObject(enumType, value));
            return n ?? value.ToString(CultureInfo.InvariantCulture);
        }

        private static string RenderFloat(float v)
        {
            // XSD xs:float rejects .NET's "Infinity"/"-Infinity" spellings, and float.Parse rejects XSD's
            // "INF". Emit an out-of-range magnitude that BOTH accept: it validates as a number and parses to
            // the same ±infinity bit pattern. NaN is spelled identically by both.
            if (float.IsPositiveInfinity(v)) return "1e39";
            if (float.IsNegativeInfinity(v)) return "-1e39";
            if (float.IsNaN(v)) return "NaN";
            // .NET Core formats finite floats shortest-round-trippable by default.
            return v.ToString(CultureInfo.InvariantCulture);
        }

        // Several wrapper types store `stored = (float)(float.Parse(text) * scale)` (Percentage: scale=0.01f;
        // Angle: deg->rad; etc.). To round-trip byte-exact we must emit a pre-image P whose compile reproduces
        // `stored` exactly. P = stored/scale is only approximate (float rounding), so probe the few neighbouring
        // representable floats and return the first that reproduces `stored` under the *same* float arithmetic.
        // Must match the compiler's constants exactly (Marshaler.cs): 1 logicframe = 1/5 s; 5 frames per 1000 ms.
        private const float SecondsPerLogicFrame = 1.0f / 5.0f;
        private const float LogicFramesPerMsec = 5.0f / 1000.0f;

        // Duration stores frames = ceil(ms * LogicFramesPerMsec). Find an integer ms whose recompile yields the
        // same frame count under the identical float arithmetic (ms = frames/LogicFramesPerMsec ~= frames*200).
        private static string InvertDuration(uint frames)
        {
            if (frames == 0)
            {
                return "0";
            }
            uint guess = (uint)Math.Round(frames / (double)LogicFramesPerMsec);
            for (int d = -2; d <= 2; d++)
            {
                long ms = (long)guess + d;
                if (ms < 0) continue;
                if ((uint)Math.Ceiling((uint)ms * LogicFramesPerMsec) == frames)
                {
                    return ms.ToString(CultureInfo.InvariantCulture);
                }
            }
            return guess.ToString(CultureInfo.InvariantCulture); // harness will flag if this ever misses
        }

        internal static float InvertScale(float stored, float scale)
        {
            float p = stored / scale;
            if ((float)(p * scale) == stored)
            {
                return p;
            }
            float up = p, down = p;
            for (int i = 0; i < 4; i++)
            {
                up = MathF.BitIncrement(up);
                if ((float)(up * scale) == stored) return up;
                down = MathF.BitDecrement(down);
                if ((float)(down * scale) == stored) return down;
            }
            return p; // give up (harness will flag); extremely rare
        }

        // StringHash stores FastHash(text) (case-SENSITIVE) of an arbitrary string — not an asset id — so it
        // cannot be resolved via the manifest name index. Emitting the raw hash is text-lossy AND does not
        // round-trip (the compiler would re-hash the "0x…" literal), so this is a genuine known-lossy edge
        // pending a StringHashes.xml reverse dump (built during a corpus compile). Documented, not faked.
        private string RenderStringHash(uint off)
        {
            uint h = _asset.ReadSlot(off);
            if (h == 0u)
            {
                return null; // unset -> omit attribute
            }
            // Recover the original (case-sensitive) string from the StringHashes.xml table if we have it.
            string text = _strings?.Lookup(h);
            if (text != null)
            {
                return text;
            }
            // Otherwise genuinely lossy (one-way hash, no reverse dump): emit hex, flagged by the harness.
            return "0x" + h.ToString("x8", CultureInfo.InvariantCulture);
        }

        // AssetReference<T>: the import slot at `slotOff` holds an INDEX into the asset's ReferencedInstances
        // list. Emit the referenced asset's authored name (recompiles byte-exact: validation rewrites it to
        // "name\<newindex>"). The compiler assigns that new index in XML document order, so the attribute is
        // recorded with its original index and the caller orders references within the element by it.
        private void EmitReference(XElement target, HashSet<string> attrSet, string name, uint slotOff, System.Collections.Generic.List<RefAttr> refs)
        {
            if (!_asset.ImportFroms.Contains(slotOff))
            {
                return; // reference not set -> no attribute
            }
            uint index = _asset.ReadSlot(slotOff);
            SetAttr(target, attrSet, name, RenderReferenceName(index));
            XAttribute attr = target.Attribute(name);
            if (attr != null)
            {
                refs.Add(new RefAttr(attr, index));
            }
        }

        private string RenderReferenceName(uint index)
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
            // Unresolvable reference: no byte-exact text exists (compile resolves by name). Emit a hex id so the
            // output is honest + the round-trip harness flags it as a known-lossy reference.
            return "0x" + index.ToString("x8", CultureInfo.InvariantCulture);
        }

        // TypedAssetId<T>: stores FastHash(name.ToLower()) directly (== the referenced asset's InstanceId), NOT
        // via the import table. Resolve by InstanceId -> authored name (recompiles byte-exact). 0 => unset.
        private string RenderTypedAssetId(uint off)
        {
            uint hash = _asset.ReadSlot(off);
            if (hash == 0u)
            {
                return null; // unset -> omit attribute
            }
            string name = _resolver?.ResolveByInstance(hash);
            if (name != null)
            {
                return name;
            }
            // Module tags (ModuleData.id) and other non-asset ids aren't in any manifest; recover them from the
            // StringHashes.xml table (hash == FastHash(text.ToLower()), matching TypedAssetId).
            string tag = _strings?.Lookup(hash);
            if (tag != null)
            {
                return tag;
            }
            // Unresolvable: known-lossy (hash is one-way; not in any manifest or hash table).
            return "0x" + hash.ToString("x8", CultureInfo.InvariantCulture);
        }

        private string RenderFixedBufferRaw(uint off, uint size)
        {
            var sb = new StringBuilder();
            for (uint i = 0; i < size; i += 4)
            {
                if (i > 0) sb.Append(' ');
                sb.Append("0x").Append(_asset.ReadSlot(off + i).ToString("x8", CultureInfo.InvariantCulture));
            }
            return sb.ToString();
        }
    }
}
