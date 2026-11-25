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
        public void ReadStruct(Type t, uint baseOff, XElement target) => ReadStruct(t, baseOff, target, null);

        // `schemaName` is the authoring element name this struct is being emitted under (the field name the parent
        // recursed through). It lets anonymous inline complexTypes — whose C# struct name (t.Name) is not a schema
        // type — be resolved by the "@elem:<name>" fallback below. For named types t.Name resolves first, so the
        // fallback never fires and behavior is unchanged.
        public void ReadStruct(Type t, uint baseOff, XElement target, string schemaName)
        {
            var refs = new System.Collections.Generic.List<RefAttr>();
            ReadStructInto(t, baseOff, target, refs, schemaName);
            if (refs.Count > 1)
            {
                foreach (RefAttr r in refs) r.Attribute.Remove();
                foreach (RefAttr r in refs.OrderBy(r => r.Index)) target.Add(r.Attribute);
            }
            ReorderChildElementsToSchema(t, schemaName, target);
            EmitIdIfRequired(t, target);
        }

        // Declared CHILD-ELEMENT names, falling back to the "@elem:<schemaName>" key when the C# type name is not a
        // named schema type (anonymous inline complexType, e.g. AABTree.TreePolyIndices). This fallback exists only
        // to classify a scalar List<T> the XSD declares as a repeated child element (e.g. AABTree's <P>) — without
        // it the walker emits that list as an attribute the validator rejects. It is deliberately NOT mirrored for
        // attribute names or sequence order: element *names* are not globally unique (a few inline types share a
        // name, e.g. two different "Upgrade"/"Heuristic" shapes), and first-wins on those keys would be wrong for
        // attribute filtering (could drop a real attribute) or reordering. For anonymous types attrSet therefore
        // stays null (SetAttr emits every field, as it did before this change — byte-safe since undeclared fields
        // are at marshal-default) and no reorder is attempted (their struct order already matches the sequence).
        private HashSet<string> DeclaredElems(Type t, string schemaName)
        {
            HashSet<string> byType = _schema?.GetDeclaredElementNames(t.Name);
            if (byType != null || schemaName == null)
            {
                return byType;
            }
            return _schema?.GetDeclaredElementNames("@elem:" + schemaName);
        }

        // Nested structs that extend BaseAssetType (e.g. MicrophoneSettings inside AudioSettings) require the XSD
        // 'id' attribute even as child elements. The id is validation-only: BaseAssetType marshals to nothing, so
        // the 4-byte Base slot stays 0 and any id value is byte-identical. The binary does not store the authored
        // id, so emit the element's own name (matching EA's authoring, e.g. <TacticalMicSettings id="TacticalMic..">
        // ). The top-level asset element already has its id set (from the instance name) before the walk, so the
        // null-check skips it; value structs (Color3f, Coord2D, ...) have no BaseAssetType field and are skipped.
        private void EmitIdIfRequired(Type t, XElement target)
        {
            if (target.Attribute("id") != null)
            {
                return;
            }
            TypeLayout.FieldLayout[] fields = TypeLayout.Get(t).Fields;
            if (fields == null || fields.Length == 0)
            {
                return;
            }
            FieldInfo f0 = fields[0].Field;
            if (f0 == null || f0.Name != "Base" || f0.FieldType != typeof(SageBinaryData.BaseAssetType))
            {
                return;
            }
            HashSet<string> attrSet = _schema?.GetDeclaredAttributeNames(t.Name);
            if (attrSet != null && attrSet.Contains("id"))
            {
                target.SetAttributeValue("id", target.Name.LocalName);
            }
        }

        // The walker emits child elements in struct-field (binary layout) order, which for most types already
        // matches the XSD sequence. A few types (e.g. Mouse, MultiplayerSettings) declare their elements in a
        // different sequence than the struct lays them out; the compiler validates children against the XSD
        // sequence and would reject the struct-order XML. Reorder known elements into XSD-sequence order. Because
        // the XSD sequence is exactly the order the original source XML had (and the order the compiler assigns
        // import indices in), this is byte-faithful: for types whose struct order already matches, it's a no-op.
        // Elements not named in the schema sequence keep their original slots.
        private void ReorderChildElementsToSchema(Type t, string schemaName, XElement target)
        {
            _ = schemaName; // reorder is keyed by named type only; anonymous inline types keep struct order (which
                            // already matches their sequence), avoiding a first-wins misorder on shared element names.
            System.Collections.Generic.List<string> order = _schema?.GetOrderedElementNames(t.Name);
            if (order == null || order.Count == 0)
            {
                return;
            }
            var rank = new System.Collections.Generic.Dictionary<string, int>(StringComparer.Ordinal);
            for (int i = 0; i < order.Count; i++)
            {
                if (!rank.ContainsKey(order[i])) rank[order[i]] = i;
            }
            var elems = target.Elements().ToList();
            if (elems.Count < 2)
            {
                return;
            }
            var known = elems.Where(e => rank.ContainsKey(e.Name.LocalName)).ToList();
            if (known.Count < 2)
            {
                return;
            }
            // Stable sort of the known elements by XSD rank (repeated names keep their relative order).
            var sortedKnown = known.OrderBy(e => rank[e.Name.LocalName]).ToList();
            bool changed = false;
            for (int i = 0; i < known.Count; i++)
            {
                if (!ReferenceEquals(known[i], sortedKnown[i])) { changed = true; break; }
            }
            if (!changed)
            {
                return;
            }
            foreach (XElement e in elems) e.Remove();
            int ki = 0;
            foreach (XElement e in elems)
            {
                target.Add(rank.ContainsKey(e.Name.LocalName) ? sortedKnown[ki++] : e);
            }
        }

        private void ReadStructInto(Type t, uint baseOff, XElement target, System.Collections.Generic.List<RefAttr> refs, string schemaName = null)
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
            // Keyed by the C# type name only (no element-name fallback — see DeclaredElems for why).
            HashSet<string> attrSet = _schema?.GetDeclaredAttributeNames(t.Name);
            // Child-element names for this type (for fields the XSD expects as elements, not attributes).
            // Save/restore around the recursive walk so nested structs don't clobber the parent's set.
            HashSet<string> savedElems = _curElems;
            string savedTypeName = _curTypeName;
            _curElems = DeclaredElems(t, schemaName);
            // The C# struct name, used to resolve a field's declared child-element schema type via the XSD
            // (e.g. SubObject.RenderObject -> RenderObjectReference, a reference-choice). For the named types that
            // carry reference-choice fields t.Name is the schema type name, so this resolves directly.
            _curTypeName = t.Name;
            foreach (TypeLayout.FieldLayout f in layout.Fields)
            {
                ReadField(f, baseOff + f.X86Off, target, attrSet, refs);
            }
            _curElems = savedElems;
            _curTypeName = savedTypeName;
        }

        // Emit an attribute only if the schema declares it for the current type (or the schema is unavailable).
        // Struct fields the XSD omits are always at their compile-default in real data, so skipping them keeps
        // the recompile byte-exact and avoids "attribute not declared" validation errors.
        // Declared child-element names of the struct currently being walked (set by ReadStructInto). A field the
        // XSD expects as a child element rather than an attribute is emitted as <name>value</name> instead of
        // being dropped by the attribute filter.
        private HashSet<string> _curElems;

        // The C# struct name currently being walked (set by ReadStructInto). Lets an AssetReference field look up
        // its declared child-element schema type to detect a reference-choice (SubObject.RenderObject).
        private string _curTypeName;

        private void SetAttr(XElement target, HashSet<string> attrSet, string name, string value)
        {
            if (attrSet == null || name == "id" || attrSet.Contains(name))
            {
                target.SetAttributeValue(name, value);
            }
            else if (_curElems != null && _curElems.Contains(name))
            {
                // e.g. FXShaderConstantTexture.Value — an AssetReference the XSD declares as a <Value> element.
                target.Add(new XElement(_ns + name, value));
            }
            // else: field not declared as attribute or element for this type -> at compile-default; safe to omit.
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

            // --- W3DMesh packed vertex data: the W3DMeshMarshalerHelper.VertexData field is a typeless `void*`
            //     the generic walker can't follow (it would emit an empty <VertexData/> and lose every vertex).
            //     In a shipped mesh it points at a packed W3DMeshVertexData (the compile-time output of
            //     W3DMeshProcessor), which — like W3DAnimation's compressed channels — cannot be reproduced by
            //     re-running the (lossy) packer. So we emit the packed block verbatim as a runtime <VertexData>
            //     form; the compiler writes it straight back (Marshaler.W3DMeshRuntime), byte-exact. ---
            if (fi.DeclaringType == typeof(SageBinaryData.W3DMeshMarshalerHelper) && name == "VertexData")
            {
                ReadRuntimeVertexData(off, target);
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
                    // An inline String<> ({int Length; ptr Target}) authored as "" compiles to Length=0 with a
                    // NON-null Target (a relocation at off+4) — an *allocated* empty string, distinct from an
                    // omitted field (Length=0, null Target, no relocation). Emit "" only in the allocated case so
                    // the recompile reproduces that relocation; otherwise drop it (same rule as the pointer-to-
                    // String path in ReadPointerField).
                    ReadString(ft.GetGenericArguments()[0], off, name, target, attrSet,
                        emitEmpty: _asset.ReloFroms.Contains(off + 4));
                    return;
                }
                if (gtd == typeof(PolymorphicList<>))
                {
                    ReadPolymorphicList(ft.GetGenericArguments()[0], off, name, target);
                    return;
                }
                if (gtd == typeof(AssetReference<>) || gtd == typeof(AssetReference<,>))
                {
                    // Reference-wrapper structs (AudioFileRefWithWeight, MultisoundSubsoundRef) hold the asset
                    // reference in their first field, named "Base". The compiler marshals the element node itself
                    // as that AssetReference (reading node text, e.g. Marshaler.Audio.cs casts the node to
                    // AssetReference<AudioFile>*), with sibling fields (Weight) as attributes. So the reference
                    // must be emitted as the element's text content, not an attribute named "Base" (which the XSD
                    // does not declare and SetAttr would drop — losing the import on recompile).
                    if (name == "Base")
                    {
                        EmitReferenceAsText(target, off);
                    }
                    else if (TryEmitReferenceChoice(target, name, off))
                    {
                        // Emitted as a typed choice wrapper (e.g. <RenderObject><Mesh>name</Mesh></RenderObject>).
                    }
                    else
                    {
                        EmitReference(target, attrSet, name, off, refs);
                    }
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
                    ReadStruct(ft, off, child, name);
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
                // A List<scalar> has two authoring shapes in the XSD. Most are a single attribute whose type is a
                // whitespace-separated list (e.g. AnimationSoundClientBehavior.Frame : SageIntListMin1). A few are
                // declared instead as a repeated child element, one scalar per occurrence (e.g.
                // HordeContainModuleData.RankToReleaseWhenAttacking : SageInt maxOccurs="unbounded") -- there a
                // single whitespace-joined value fails the element's scalar Pattern facet. Pick the shape the XSD
                // declares: a repeated element when the name is a declared child element and not a declared
                // attribute (matching SetAttr's attribute-wins precedence); otherwise the whitespace-joined
                // attribute. When the schema is unavailable, _curElems is null and we keep the attribute form.
                if (_curElems != null && _curElems.Contains(name) && (attrSet == null || !attrSet.Contains(name)))
                {
                    for (uint i = 0; i < count; i++)
                    {
                        target.Add(new XElement(_ns + name, RenderScalarLike(elem, itemsOff + i * stride)));
                    }
                }
                else
                {
                    var sb = new StringBuilder();
                    for (uint i = 0; i < count; i++)
                    {
                        if (i > 0) sb.Append(' ');
                        sb.Append(RenderScalarLike(elem, itemsOff + i * stride));
                    }
                    SetAttr(target, attrSet, name, sb.ToString());
                }
            }
            else
            {
                for (uint i = 0; i < count; i++)
                {
                    var child = new XElement(_ns + name);
                    ReadStruct(elem, itemsOff + i * stride, child, name);
                    target.Add(child);
                }
            }
        }

        private void ReadString(Type charType, uint off, string name, XElement target, HashSet<string> attrSet, bool emitEmpty = false)
        {
            string s = ReadStringValue(charType, off);
            if (s == null)
            {
                // Inline empty string = absent (null pointer), emit nothing. But a string reached through a
                // NON-null pointer (emitEmpty) is an *allocated* empty string (e.g. DestinationPlayer="") that the
                // binary carries as a relocation — it must emit ="" so the recompile reproduces that relocation.
                if (!emitEmpty)
                {
                    return;
                }
                s = string.Empty;
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
                // Null pointer -> normally emit nothing. EXCEPTION: a single polymorphic-module pointer
                // (e.g. FXParticleSystemTemplate.Velocity / .Physics, GameObject.Body) whose XSD element is
                // REQUIRED (minOccurs >= 1) while its inner module choice is itself optional (minOccurs=0).
                // EA's authoring XML for such a null field carried an EMPTY wrapper (<Velocity/>); omitting it
                // would fail XSD validation on recompile. The empty wrapper compiles straight back to the null
                // pointer (Marshaler.MarshalSinglePolymorphic sees 0 child nodes and leaves the pointer null),
                // so it is byte-exact. Fully schema-driven: keys on the element being schema-required for the
                // current type, never on a field name. (A required NON-module pointer is left as-is.)
                if (typeof(IPolymorphic).IsAssignableFrom(elem)
                    && _schema?.GetRequiredElementNames(_curTypeName)?.Contains(name) == true)
                {
                    target.Add(new XElement(_ns + name));
                }
                return;
            }
            uint to = _asset.ReadSlot(off);

            if (elem.IsGenericType)
            {
                Type gtd = elem.GetGenericTypeDefinition();
                // A pointer to a PolymorphicList reached here is itself a relocation (past the null guard above),
                // so EA allocated the list header. An EMPTY allocated list ({Count=0, Items=null}) must still emit
                // its wrapper element so the recompile re-allocates the 8-byte header and reproduces the field
                // relocation (same allocated-empty rule as the pointer-to-String path); a non-empty list emits its
                // items as usual.
                if (gtd == typeof(PolymorphicList<>)) { ReadPolymorphicList(elem.GetGenericArguments()[0], to, name, target, emitEmpty: true); return; }
                if (gtd == typeof(Relo.List<>)) { ReadList(elem.GetGenericArguments()[0], to, name, target, attrSet); return; }
                if (gtd == typeof(String<>)) { ReadString(elem.GetGenericArguments()[0], to, name, target, attrSet, emitEmpty: true); return; }
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

            // A pointer to a bit-flag bitset struct (e.g. SpecialPowerTemplate.MetaGameDependencies) -> the flag
            // tokens at the followed offset. A null pointer returned above = omitted field, so the tokens are
            // only ever emitted when EA actually allocated the block (no default leak on recompile).
            if (IsBitFlagsStruct(elem)) { SetAttr(target, attrSet, name, RenderBitFlags(elem, to, TypeLayout.Get(elem).SizeX86)); return; }

            // A pointer to a scalar / wrapper value -> attribute at the followed offset.
            if (elem.IsEnum) { SetAttr(target, attrSet, name, RenderEnum(elem, to, TypeLayout.Get(elem).SizeX86)); return; }
            string scalar = RenderScalar(elem, to, null);
            if (scalar != null) { SetAttr(target, attrSet, name, scalar); return; }

            // A pointer to a plain nested struct (BuildableStatus, Coord3D, Geometry, ...) -> child element.
            var child = new XElement(_ns + name);
            ReadStruct(elem, to, child, name);
            target.Add(child);
        }

        // PolymorphicList<T> at `listOff` = {uint Count; ptr ItemsArray}. ItemsArray = Count 4-byte pointers,
        // each a relocation to a module item block whose offset 0 = the module's TypeId hash. Emits one wrapper
        // element (field name) containing a child element per module (name resolved from the type). Empty => none.
        private void ReadPolymorphicList(Type baseElem, uint listOff, string name, XElement target, bool emitEmpty = false)
        {
            uint count = _asset.ReadSlot(listOff);
            uint arrOff = _asset.ReadSlot(listOff + 4);
            if (count == 0 || !_asset.ReloFroms.Contains(listOff + 4))
            {
                if (emitEmpty)
                {
                    target.Add(new XElement(_ns + name)); // allocated-empty list -> emit the wrapper (no items)
                }
                return; // empty list
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
            ReadStruct(moduleType, itemOff, child, elemName);
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

        // Emit the packed runtime W3DMeshVertexData the `void* VertexData` slot points at, as a <VertexData>
        // element the compiler's W3DMesh runtime pass-through writes straight back (byte-exact). On-disk block
        // (x86, 28 bytes), produced by W3DMeshProcessor.BuildVertexData:
        //   @0  NumVertices (int)
        //   @4  VertexElementData.Count  — the per-vertex STRIDE, not a byte count (BuildVertexData sets Count =
        //       vertexDataSize); the interleaved buffer is NumVertices * stride bytes.
        //   @8  VertexElementData.Items (ptr)
        //   @12 VertexDeclaration.Count (bytes)   @16 VertexDeclaration.Items (ptr)
        //   @20 Bones.Count (ushorts)             @24 Bones.Items (ptr)
        // A null pointer (no relocation at `off`) = a mesh with no vertex data -> emit nothing; the compiler then
        // reproduces the null VertexData (no <VertexData> and no authoring <Vertices>).
        private void ReadRuntimeVertexData(uint off, XElement target)
        {
            if (!_asset.ReloFroms.Contains(off))
            {
                return; // null VertexData pointer
            }
            uint to = _asset.ReadSlot(off);
            _asset.CheckRange(to, 28, "W3DMeshVertexData header");

            uint numVertices = _asset.ReadSlot(to);
            uint stride = _asset.ReadSlot(to + 4);
            uint vedOff = _asset.ReadSlot(to + 8);
            uint vdCount = _asset.ReadSlot(to + 12);
            uint vdOff = _asset.ReadSlot(to + 16);
            uint bonesCount = _asset.ReadSlot(to + 20);
            uint bonesOff = _asset.ReadSlot(to + 24);

            long vedBytes = (long)numVertices * stride; // the interleaved buffer length

            var vd = new XElement(_ns + "VertexData");
            vd.SetAttributeValue("NumVertices", numVertices.ToString(CultureInfo.InvariantCulture));
            // The stride is carried explicitly (not derived as bytes/NumVertices) so a zero-vertex block still
            // round-trips its VertexElementData.Count exactly.
            vd.SetAttributeValue("VertexStride", stride.ToString(CultureInfo.InvariantCulture));
            vd.Add(new XElement(_ns + "VertexElementData", ReadBlobBase64(vedOff, vedBytes, "W3DMesh VertexElementData")));
            vd.Add(new XElement(_ns + "VertexDeclaration", ReadBlobBase64(vdOff, vdCount, "W3DMesh VertexDeclaration")));
            vd.Add(new XElement(_ns + "Bones", _asset.RenderUShortList(bonesOff, bonesCount, "W3DMesh Bones")));
            target.Add(vd);
        }

        private string ReadBlobBase64(uint off, long count, string what)
        {
            if (count <= 0)
            {
                return string.Empty;
            }
            _asset.CheckRange(off, count, what);
            var bytes = new byte[count];
            Buffer.BlockCopy(_asset.Instance, (int)off, bytes, 0, (int)count);
            return Convert.ToBase64String(bytes);
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
            if (n == null)
            {
                return value.ToString(CultureInfo.InvariantCulture);
            }
            // SAGE enums whose authored/XSD name is not a valid C# identifier (e.g. "1", "2") use a placeholder
            // member name carrying the real name in a [Display(Name="...")] attribute — the same convention the
            // compiler's enum marshaler reads. Emit the Display name so the XSD enumeration accepts it.
            var display = enumType.GetField(n)
                ?.GetCustomAttribute<System.ComponentModel.DataAnnotations.DisplayAttribute>();
            return display?.Name ?? n;
        }

        // Delegates to the single source (ValueRender.Float) so the round-trip spelling can't drift between
        // this walker and the type-specific readers.
        private static string RenderFloat(float v) => ValueRender.Float(v);

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

        // Some AssetReference fields are declared in the XSD not as a bare attribute/element but as a "reference
        // choice": a child element whose type lists one wrapper element per allowed target type, each carrying an
        // xas:refType (e.g. SubObject.RenderObject : RenderObjectReference =
        // <choice><Mesh refType=W3DMesh/><CollisionBox refType=W3DCollisionBox/>). The on-disk import only records
        // the referenced instance; the wrapper to emit is chosen from that instance's ACTUAL type (via the manifest
        // References list + the type registry), then mapped to the choice element through the schema — never a
        // hardcoded element/type name. Returns false (caller falls back to the plain attribute form) when the field
        // is not a reference-choice or the wrapper can't be resolved, so non-choice references are unaffected.
        private bool TryEmitReferenceChoice(XElement target, string name, uint slotOff)
        {
            string choiceType = _schema?.GetChildElementType(_curTypeName, name);
            if (choiceType == null || !_schema.IsReferenceChoiceType(choiceType))
            {
                return false;
            }
            if (!_asset.ImportFroms.Contains(slotOff))
            {
                return true; // reference-choice field, but reference not set -> emit nothing (field omitted)
            }
            uint index = _asset.ReadSlot(slotOff);
            string referentType = null;
            if (index < (uint)_asset.References.Length)
            {
                (uint tid, uint _) = _asset.References[index];
                if (_registry.TryGet(tid, out Type rt))
                {
                    referentType = rt.Name;
                }
            }
            string wrapperElem = _schema.GetReferenceChoiceElement(choiceType, referentType);
            if (wrapperElem == null)
            {
                return false; // unknown referent type -> fall back to the plain form (honest, harness will flag)
            }
            var wrapper = new XElement(_ns + name, new XElement(_ns + wrapperElem, RenderReferenceName(index)));
            target.Add(wrapper);
            return true;
        }

        // Emit an AssetReference as the element's TEXT content (the reference-wrapper pattern — see the "Base"
        // field handling in ReadField). On recompile the reference-resolution pass reads the element node's value,
        // records the import, and rewrites it to "name\index", so the import buffer is reproduced byte-exact.
        private void EmitReferenceAsText(XElement target, uint slotOff)
        {
            if (!_asset.ImportFroms.Contains(slotOff))
            {
                return; // reference not set -> no text
            }
            uint index = _asset.ReadSlot(slotOff);
            target.Add(new XText(RenderReferenceName(index)));
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
