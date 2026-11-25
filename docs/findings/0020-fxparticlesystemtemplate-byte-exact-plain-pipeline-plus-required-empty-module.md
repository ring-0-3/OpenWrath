# 0020 — FXParticleSystemTemplate round-trips byte-exact via the plain data pipeline (+ a required-but-null module decompiler fix)

**Status:** Verified · 2026-11-25

> About **our own tools** (the XmlCompiler type registry, the decompiler's generic struct-walker, the schema
> index). The first **content-pipeline data type** (particles) to reach the byte-exact ground-truth bar. Like
> [0019](0019-w3dcontainer-hierarchy-collisionbox-byte-exact-plain-pipeline.md) it carries **no lossy/typeless
> block**, so it needed **no runtime pass-through and no in-code schema binding** — just one line of type
> registration. The one non-trivial piece is a *decompiler* fix for a schema-required element whose binary field
> is null (the reworked-laser / beam family).

## Context — a plain data type that was only ever un-registered

`FXParticleSystemTemplate` (TypeId `0x28E7FD7F`) was in COVERAGE's "Not modeled" list, but the model and the full
marshaler suite **already existed** in the tree — `SageBinaryData/FXParticleSystem*.cs` (the template + its
polymorphic module families: Physics / Draw / Volume / Velocity / Update / Event) and
`BinaryAssetBuilder.XmlCompiler/Marshaler.FXParticleSystem*.cs`. The only missing piece was the **registration**:
the type was commented out in the XmlCompiler `Plugin.Initialize()` foreach. So this is an ordinary data type that
round-trips through the generic pipeline exactly like the existing 34 — registration + the pre-existing marshalers +
the reflection-built decompiler `TypeRegistry` — **not** a frontier blob. The brief's Phase-1 prediction held.

## Harvested identity (from shipped data, never guessed — and version-matched)

- **TypeId `0x28E7FD7F` = `FastHash("FXParticleSystemTemplate")`** — verified by reproducing the shared one-way
  formula (`Core/Hashing/FastHash`) in-script; the same reproduction matches the known W3DMesh `0xC2B1A262` /
  ArmorTemplate `0x3A6C5E8E`. TypeId is the name-hash, game-independent.
- **TypeHash `0xA0C56702`** — **harvested from the shipped KW `static_common` manifest**, where it is the
  TypeHash on **all 1674** FX asset entries (a single distinct value, no schema variants).

⚠ **Version trap avoided (the `0016` version-blindness class).** The commented
`Plugin.GetExtendedTypeInformation` scaffold lists `FXParticleSystemTemplate` with TypeHash `0xA148D511` — but that
whole switch is the **TiberiumWars** type table (its `ArmorTemplate` entry is `0x9CDD1086`, which is the *TW*
ArmorTemplate hash per the `#if TIBERIUMWARS` arm of the foreach; KW's is `0x6D59C409`). Trusting the scaffold would
have stamped the **wrong-game** TypeHash. The registered value is the harvested **KW** one.

**On TypeHash and the comparator (the comparator's own blind spot).** `compare-stream.py` matches by
`(TypeId, InstanceId)` and **wildcards TypeHash / InstanceHash**, so the harvested TypeHash is **not** verified by
the byte-exact gate — it is *harvested-not-oracle-verified*. The engine *does* check TypeHash at load
([0010](0010-insert-must-match-target-stream-type-schema-hash.md) /
[0016](0016-static-mod-stream-is-complete-replacement-not-overlay.md)), so a wrong value would be byte-exact-green
yet crash in-game; the harvest above is the only guarantee. `ProcessingHash` is the build-internal `num ^ TypeHash`
convention `CreateTypeInfo` applies to all 34 existing types — not shipped data, no magic relationship implied.

## The one non-trivial piece — a required element whose binary field is null (decompiler)

**First-diff.** Of a seed-7 sample, `RedeemerLaserGlow3` failed to recompile: *"element 'FXParticleSystemTemplate'
has invalid child element 'Update' … expected 'Velocity'."* Its shipped binary has a **null `Velocity` pointer**
(no emission-velocity module), so the generic walker — which omits a null pointer field — emitted no `<Velocity>`.
But the XSD declares `Physics` / `Draw` / `Volume` / `Velocity` as `minOccurs="1"` (**required elements**) while
their *inner* module choice (`FXParticleVelocityModule` = `<xs:choice minOccurs="0">`) is optional. So EA's authoring
XML for such a system carried an **empty** `<Velocity/>` wrapper, which the compiler's `MarshalSinglePolymorphic`
reads as *0 child nodes → leave the pointer null*. Omitting the element both **fails XSD validation** on recompile
and loses EA's authoring shape.

Across the corpus this affects **35** systems — essentially the **reworked-laser / beam family** (Redeemer lasers &
glows, particle-beam cores/threads, railgun cores/threads, tib-agitation beams, buzzer death): 19 have a null
`Velocity`, 22 a null `Physics`, a couple a null `Update` (`Update` is `minOccurs="0"`, so it needs no wrapper).

**Fix (decompiler, schema-driven, general).** When a **pointer field is null** and (a) its pointee is an
`IPolymorphic` single module **and** (b) the schema marks that child element **required** for the current type,
`StructReader.ReadPointerField` now emits an **empty wrapper** `<Velocity/>` instead of nothing. It keys on the
element being *schema-required* (new `SchemaIndex.GetRequiredElementNames`, which reads `minOccurs` — absent ⇒ XSD
default 1 ⇒ required — and folds the extension base), **never on a field name or instance id**. The empty wrapper
compiles straight back to the null pointer (`MarshalSinglePolymorphic` sees 0 children), so it is byte-exact.

- **Why it generalizes, not overfits.** The rule is "a schema-required single polymorphic-module element whose
  binary pointer is null is emitted empty." It would produce correct bytes for any unsampled system with a null
  required module (the sample proves it on 35), and for any *other* type with the same shape — e.g.
  `GameObject.Body` is also `minOccurs="1"` + `IPolymorphic`; the change is correct there too (and inert, since no
  shipped `static_common` GameObject has a null Body). It can only ever *fix or no-op*, never regress: before the
  fix such a case emitted nothing and **failed XSD validation**, so it was never byte-exact to begin with.
- **Boundary.** It fires only for the `IPolymorphic`-single null-pointer path. The allocated-empty
  **PolymorphicList** wrapper (e.g. an empty `<Behaviors/>`) is a *separate, pre-existing* rule (`emitEmpty: true`)
  and is untouched.

## What was added / changed (3 owned files; no BYO/EA file edited)

- **`XmlCompiler/Plugin.cs`** — one foreach entry: `(typeof(FXParticleSystemTemplate), 0xA0C56702u, false)` with a
  comment recording the harvest + the version-trap it avoids. Routing is the default `#all` → XmlCompiler
  (`BinaryAssetBuilder.cfg`), so no cfg change.
- **`Decompiler/SchemaIndex.cs`** — `RequiredElements` per complexType (minOccurs-aware) + `GetRequiredElementNames`
  (base-chain folded), mirroring the existing `GetDeclaredElementNames`. Purely additive.
- **`Decompiler/StructReader.cs`** — the empty-required-module-wrapper emit in the null-pointer branch of
  `ReadPointerField`.

No new marshaler, no runtime pass-through, no in-code schema binding, **no edit to any schema / game data / stream**
(invariant 1).

## Verification (oracle-backed, 2026-11-25)

`tools/roundtrip.sh --from-binary` / `bab-decompile decompile-stream --type 0x28e7fd7f` + `compare-stream.py
--type 0x28e7fd7f` against the shipped `static_common` stream
(`~/cnc-kw-godmod/ea-roundtrip/eastream/static_common.manifest`).

| Measure | Result |
|---|---|
| Whole-corpus decompile | **1674 ok, raw=0** (single TypeHash `0xA0C56702`) |
| Seed-7 random sample (150) | **150/150 BYTEEXACT** (sizeok_valdiff=0, sizediff=0, missing=0) |
| Required-null-module edge class (all 35) | **35/35 BYTEEXACT** (Redeemer/laser/beam/railgun, empty `<Velocity/>`/`<Physics/>`) |

**Zero value-diffs** — no StringHash / weak-reference residual surfaced for this type (`ParticleTexture`,
`Drawable`, `SlaveSystem`, `PerParticleAttachedSystem`, `EmitterSound` references all resolve via `-rm` and
round-trip byte-exact, imports buffers included).

**Polymorphic-module variant coverage** (distinct variants present in `static_common`, by family — all exercised by
the samples above):

| Family | Variants sampled byte-exact |
|---|---|
| Physics  | Default (1634), Swarm (18) |
| Draw     | Gpu (1048), Default (373), Trail (138), RenderObject (75), Lightning (26), Streak (10), Swarm (4) |
| Volume   | Cylinder (930), Point (297), Line (197), Sphere (167), Box (41), Lightning (27), Spline (15) |
| Velocity | Ortho (1360), Outward (226), Spherical (38), Cylindrical (18) |
| Update   | Default (1597), RenderObject (75) |
| Event    | Collision (32), Life (3) |

**No regression:** closed-loop `Armor.xml` **207/207** and `Weapon.xml` **456/456** byte-exact; ground-truth
`W3DAnimation` (`ABBHIVE_D2AN`) and `W3DMesh` (`ABBHIVEBLD_SKN.ABBHIVEA`) still byte-exact; `schema-selftest` both
binding guards PASS; GameObject unaffected by the decompiler change (verified: 0 empty single-module wrappers across
1045 instances; the 2 empty `<Behaviors/>` are the pre-existing allocated-empty-list rule and their SIZEOK_VALDIFF
is the documented module-id StringHash residual, not this change).

## Scope / honesty

- Only `static_common` is sampled. The seed-7 150 + the exhaustive 35 edge cases are strong positive evidence for
  the model, **not** a whole-corpus guarantee.
- **TypeHash is harvested-not-oracle-verified** (comparator wildcard; see above).
- **Unsampled branches** (no shipped instance in `static_common` to compare against, so defensive-not-verified):
  the `FXParticleEmissionVolumeTerrainFire` volume variant (`0xE0E03E35`) and a `FXParticleEmissionVelocityHemisphere`
  (`0xB7B54FC2`) have **no** instance here; any marshaler variant not in the table above is unexercised. The
  big-endian / Xenon path is untouched.
- The decompiler's required-empty-wrapper rule is verified on the FX single-module case (and reasoned inert for
  GameObject); its correctness on a *future* type with a null required polymorphic module whose compiler marshaler
  does **not** reduce an empty element to a null pointer would need its own check — the rule assumes the
  `MarshalSinglePolymorphic` 0-children ⇒ null contract, which holds for all current `IPolymorphic` single fields.

## Credit

The reworked-laser / particle-beam effects are exactly the kind of community-moddable content named in
`docs/design/community-mods-as-frontier-reference.md`; here they appear as **EA's own shipped** beam systems and
served as the natural edge-case corpus (null required module) that forced the decompiler fix. No community content
was used or shipped.
