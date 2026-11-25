# 0019 — W3DContainer / W3DHierarchy / W3DCollisionBox round-trip byte-exact via the ordinary pipeline

**Status:** Verified · 2026-11-25

> About **our own tools** (the W3X compiler marshalers, the decompiler's generic struct-walker, the schema index).
> Completes the W3D model graph's connective tissue. Unlike [0014](0014-runtime-w3danimation-dispatch-depends-on-schema-stamped-typeid.md)
> (W3DAnimation) and [0018](0018-w3dmesh-byte-exact-via-runtime-vertexdata-passthrough.md) (W3DMesh), these three
> carry **no lossy/typeless block**, so they needed **no runtime pass-through and no in-code schema binding** —
> just type registration + hand-written marshalers + one schema-driven decompiler refinement.

## Context — these are plain structural types

W3DMesh and W3DAnimation ship a compiled, lossy block (packed `W3DMeshVertexData` / compressed channels) that
cannot be re-derived, which forced a verbatim runtime pass-through. The three types here are ordinary sequential
structs (confirmed against `SageBinaryData/W3D.cs` and the KW XSD):

- **`W3DContainer`** (TypeId `0xF0F08712`) = `BaseRenderAssetType` + `AssetReference<W3DHierarchy> Hierarchy` (attr)
  + `List<SubObject> SubObject`.
- **`SubObject`** = `uint BoneIndex` + `AnsiString SubObjectID` + `AssetReference<BaseAssetType> RenderObject`.
- **`W3DHierarchy`** (TypeId `0x61D7EA40`) = `BaseAssetType` + `List<HierarchyPivot> Pivot`
  (`Name`, `Parent`, `Translation`, `Rotation`, 4×4 `FixupMatrix`).
- **`W3DCollisionBox`** (TypeId `0xE3181C04`) = `BaseRenderAssetType` + `Vector3 Center` + `Vector3 Extent`
  + `SageBool JoypadPickingOnly`. Pure POD.

So the expected path was the **ordinary pipeline**, and that is what it turned out to be — no mesh-style special
case. Reaching for a runtime pass-through here would have been overfitting the previous answer.

## Harvested identity (from shipped data, never guessed)

TypeId = `FastHash(typeName)` (verified: the formula reproduces the known W3DMesh `0xC2B1A262` / W3DAnimation
`0x2448AE30`). TypeHash was read straight from the shipped `static_common` manifest's per-asset entries:

| Type | TypeId | TypeHash (shipped) | instances in static_common |
|------|--------|--------------------|----------------------------|
| W3DContainer    | `0xF0F08712` | `0x909DD93F` | 1060 |
| W3DHierarchy    | `0x61D7EA40` | `0x3BC26A7A` |  940 |
| W3DCollisionBox | `0xE3181C04` | `0xC917E725` | 2701 |

**On TypeHash / ProcessingHash and the comparator.** `compare-stream.py` matches a recompiled asset to its shipped
original by **(TypeId, InstanceId)** only — TypeHash and InstanceHash are wildcarded — so neither the TypeHash nor
the ProcessingHash affects any *compared* byte (they feed only the asset header / InstanceHash, which the oracle
does not compare). This is also why 0018's W3DMesh registration (`TypeHash=0xC9D7E778`) was harmless even though
the shipped manifest stores `0x685DDFC2` for W3DMesh. Here the registered `TypeHash` is set to the **shipped**
value for honest fidelity; `ProcessingHash` is a build-internal value **not present in shipped data**, so it is set
equal to the harvested TypeHash as a non-arbitrary placeholder — **no magic relationship (e.g. `1 ^ TypeHash`) is
implied or relied on.**

**One consequence of the wildcard: the TypeHash's correctness rests on the harvest, not the oracle.** Because the
comparator never checks TypeHash, a future regression that corrupted it would still pass byte-exact here — yet the
**engine does check TypeHash at load** (findings [0010](0010-insert-must-match-target-stream-type-schema-hash.md) /
[0016](0016-static-mod-stream-is-complete-replacement-not-overlay.md)), so a wrong TypeHash would crash in-game
while this test stayed green. The harvested values above are correct; this note just makes that un-guarded-ness
explicit so a later edit doesn't silently break it.

## What was added / changed

- **Compiler registration.** `W3XCompiler/Plugin.GetExtendedTypeInformation`: three cases (harvested TypeId /
  TypeHash). `BinaryAssetBuilder.cfg` (an **owned, tracked** config, not a BYO file) already routed
  `W3DAnimation`/`W3DMesh` to the W3X plugin (since the original import `b7c0e56`); this adds `W3DContainer,
  W3DHierarchy, W3DCollisionBox` to that same route. `ProcessInstance`'s
  default branch then auto-dispatches `HandleType<T>` → `Marshaler.Marshal(Node, T*, Tracker)` with no new
  per-type handler.
- **Compiler marshalers** (`Marshaler.W3D.cs`): hand-written `Marshal` overloads for the three types and their
  sub-structs (`SubObject`, `HierarchyPivot`, the 4×4 `Matrix`), following the existing overload pattern. Fields
  are marshaled in struct-layout order so the appended string data and the imports buffer reproduce the shipped
  order. `BaseAssetType`/`BaseRenderAssetType` marshal to nothing (as before).
- **Decompiler — the one non-trivial piece: `SubObject.RenderObject` is a *reference choice*.** The XSD types
  `RenderObject` as `RenderObjectReference` = `<choice><Mesh xas:refType=W3DMesh/><CollisionBox
  xas:refType=W3DCollisionBox/></choice>`. The on-disk import only records the referenced *instance*, so the
  generic walker (which emits a bare `AssetReference`) produced `<RenderObject>name</RenderObject>`, which the XSD
  rejects. The fix emits the correct wrapper **chosen from the referenced asset's actual type** — read from the
  manifest `References` list + the type registry, then mapped to the choice element through the schema's
  `xas:refType` index. It is fully input-/schema-driven: **no hardcoded `Mesh`/`CollisionBox`/`W3DMesh` literal**
  in code. `SchemaIndex` gained `GetChildElementType`, `GetReferenceChoiceElement`, `IsReferenceChoiceType` (it now
  indexes each type's child-element `type=` and its `xas:refType`→element map); `StructReader.TryEmitReferenceChoice`
  does the emit, tracking the current struct name in `_curTypeName`. The guard keys on the *element's declared
  type* being a reference-choice, so the other `xas:refType` in the schema (`FXShaderConstantTexture.Value`, type
  `AssetReference` — not a choice) is unaffected.
- **Compiler read-back needs no new reference code.** The reference-resolution pass (`HandleAssetReferenceType`) is
  already schema-driven: it reads `xas:refType` from the `<Mesh>`/`<CollisionBox>` element, validates the referent
  derives from it, and rewrites the inner text to `name\index`. An element node's value is the concatenation of its
  descendant text, so the `SubObject` marshaler reads the reference with a plain
  `GetChildNode("RenderObject").GetValue()` — it never has to name the choice members.

## Verification (oracle-backed, 2026-11-25)

`tools/roundtrip.sh --from-binary` / `compare-stream.py --type` against the shipped `static_common` stream
(`~/cnc-kw-godmod/ea-roundtrip/eastream/static_common.manifest`). All three types decompile cleanly (`ok`, `raw=0`)
over the whole corpus (2701 / 940 / 1060). Reproducible random samples (seed 7) recompile byte-exact:

| Type | sample | result |
|------|--------|--------|
| W3DCollisionBox | 150 | **150/150 BYTEEXACT** (sizeok_valdiff=0, sizediff=0, missing=0) |
| W3DHierarchy    | 150 | **150/150 BYTEEXACT** (sizeok_valdiff=0, sizediff=0, missing=0) |
| W3DContainer    | 150 | **150/150 BYTEEXACT** (sizeok_valdiff=0, sizediff=0, missing=0) |

Spot-verified mixed cases byte-exact: `W3DCollisionBox:ABWARPBLD_SKN.OBBOX09`, `W3DHierarchy:GBFUE01`,
`W3DContainer:NUCIVTRNSPRTR05` (mesh sub-object), `W3DContainer:AUMOTHER_SKN` (82 sub-objects), and
`W3DContainer:ABBHIVEBLD_SKN` (both `<CollisionBox>` and `<Mesh>` sub-objects — the reference-choice discriminator).

**No regression:** closed-loop `Armor.xml` **207/207** and `Weapon.xml` **456/456** byte-exact; ground-truth
`W3DAnimation` (`ABBHIVE_D2AN`) and `W3DMesh` (`ABBHIVEBLD_SKN.ABBHIVEA`) still byte-exact; `schema-selftest`
passes both the animation and mesh binding guards.

## Scope / honesty

The seed-7 samples (150 each) are strong positive evidence for each type's model — **not** a whole-corpus
guarantee; only `static_common` is sampled, and the big-endian / Xenon path is untouched. Defensive-not-verified
branches (no shipped instance in `static_common` to compare against): a `W3DContainer` with an **empty**
`SubObject` list, and a `SubObject.RenderObject` referencing a type **other than** W3DMesh/W3DCollisionBox (none
exist in this stream — the choice has exactly those two members). If such instances appear in another stream,
those are the branches to re-check first.

## Reuse note

`SchemaIndex`'s new reference-choice index (`GetChildElementType` / `GetReferenceChoiceElement` /
`IsReferenceChoiceType`) and `StructReader.TryEmitReferenceChoice` are general: any future typed `xas:refType`
choice (should one appear) is handled by the same schema-driven path, no new per-type code.
