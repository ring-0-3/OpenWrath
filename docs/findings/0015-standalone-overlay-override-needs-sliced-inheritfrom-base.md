# 0015 — A zero-EA standalone overlay override needs a *sliced* single-asset inheritFrom base

**Status:** Verified · 2026-11-24

> About the **modkit/compiler authoring model**, not the game's data format. Underpins `openwrath mod package`.

## Context

`mod package` must emit a self-contained overlay stream (`static_mod`/`global_mod`) that carries **only the
user's own overrides/additions** and **imports** everything else from the base streams by id (chapter 4 overlay
model; zero-EA invariant). Unlike `mod bake` — which splices the user's assets into a target mod's *full* stream
(SI's `static_mod`, 43,994 assets) where every dependency is already present — a standalone overlay has nothing
but the base streams underneath it, so each dependency edge must resolve as an **import**, not an internal
relocation into a co-located copy.

## Finding — how an asset becomes *local* vs *import*, and why the obvious authoring forms fail

The compiler's output set is the closure from the **declared** instances over their references
(`AssetDeclarationDocument.AddOutputInstance`): a referenced instance is emitted **locally** iff
`ResolveReference` classifies it as non-`External`; otherwise it becomes an import. An instance is non-`External`
whenever it is loaded as a *tentative instance* — which is exactly what an EA `<Include type="instance">`
produces.

Measured on `GDIMissileSoldierMissileLauncher` (`inheritFrom` self, references its sibling
`…MissileWarhead` in the same `GlobalData/Weapon.xml`):

- **Whole-file EA include** (`<Include type="instance" source="DATA:GlobalData/Weapon.xml"/>`, what `mod add`
  writes) → overlay emits **2 assets**: the Launcher **and** the Warhead. The Warhead is pulled in local because
  the whole-file include made it a tentative instance, and the Launcher→Warhead edge becomes an **internal
  relocation**. Shipping that overlay redistributes an EA asset the user never touched. ✗ zero-EA.
- **No include, rely on `-bps`/`-rm`** → `Critical: … cannot be overriden because it is not of type
  BaseInheritableAsset`. Reference manifests resolve *imports*, they do **not** provide an inheritable instance. ✗
- **`<Include type="instance" source="…#xpointer(…)">`** → the EA include has no fragment support; it looks for a
  file literally named `…#xpointer(…)` and fails. ✗
- **`xi:include` with `xpointer` _inside_ `<Includes>`** → BAB marshals the `xi:include` element as an EA
  `<Include>` and throws on the missing `type` enum (`ArgumentException … ThrowInvalidEmptyParseArgument`). ✗
- **`xi:include` with `xpointer` selecting a top-level asset, placed at AssetDeclaration level** → **works, emits
  exactly 1 asset**, deps as imports (extends [0008] beyond module-child selection to top-level-asset selection).
  But the spliced node is the **unmodified base** asset — there is no way to layer the user's changes onto it. Add
  a top-level `inheritFrom` override of the same id and you get `Critical: Duplicate instance` ([0006]-style),
  because override/`inheritFrom` resolution requires the base in the **tentative** tier (`<Includes>`), not as a
  second self-instance. ✗ for overrides.

**Resolution:** emit only the user's declared assets by giving the compiler a **sliced, single-asset include** as
the tentative base: extract just the overridden instance's top-level block from its SDK source (reusing the
existing `_find_toplevel_block`, the same engine behind `inspect --source` / `mod add`), write it to a temp
single-asset `<AssetDeclaration>`, and `<Include type="instance">` *that*. The sibling dependency is then no
longer a tentative instance, so the Launcher→Warhead edge compiles as an **import**. Verified: the overlay emits
**exactly 1 asset** (`GDIMissileSoldierMissileLauncher`), Warhead + the other five refs all external.

`inheritFrom` **chains**: a base `B` that itself `inheritFrom`s `C` needs `C` sliced too — follow the chain
(BFS), slicing each ancestor not already declared in the mod. A base whose block carries **relative** `xi:include`
`href`s (common on GameObjects) breaks when the slice is compiled from a temp dir — rewrite non-aliased relative
`href`/`source` paths to absolute against the original SDK file's directory (`DATA:`/`ART:`/`AUDIO:`/`ROOT:`
aliases are left alone). **Macro context:** base values pervasively use the `=$MACRO` form (e.g.
`RadiusDamageAffects="=$GDI_IONCANNON_AUXILIARY_DAMAGE_AFFECTS"` — 4618 uses across 455 SDK files); the macro is
defined in the file's `<Defines>` block and/or a transitively-`<Include>`d defines file (`GlobalDefines.xml`).
The compiler's `ExpressionEvaluator` (`Core/ExpressionEvaluator.cs`, present and working — the startup
"Could not load ExpressionEvaluator from BinaryAssetBuilder.ExpressionEval.dll" is a red herring for a *separate*
native lib, like the Mvp.Xml notice in [0008]) substitutes these from the document's defines. Slicing the asset
alone drops that define set, so the raw macro name survives and fails the schema's enum facet — **slice-context
loss, not a port limitation** (a whole-file compile expands it fine). Fix: recursively harvest every reachable
`<Define>` row (own + included defines files, resolving `DATA:`/relative, skipping `ART:`/`AUDIO:`) and **inline
them** into the bases file — which carries the full reachable define set without re-including any asset/art file.

## Verified (byte-identity + two real mods)

- **No drift from the slice+inherit path.** A *no-change* self-override (`<WeaponTemplate id="X"
  inheritFrom="X"/>`) packages to instance data **byte-identical** (1136/1136 bytes) to the base `X` compiled in
  the same overlay/import context. The only on-disk difference from the **shipped** asset is that a reference to a
  base sibling is encoded as an **import** instead of an internal relocation — the defining property of an
  overlay, not a drift. The overlay decompiles `ok=1 raw=0` with the sibling resolved **by name**
  (`WarheadTemplate="GDIMissileSoldierMissileWarhead"`).
- **Simple override** (`missilerate`, 1 WeaponTemplate referencing a same-file Warhead): overlay emits **exactly
  1** asset; the whole-file include would have emitted 2 (Warhead embedded).
- **Complex mod** (`marv-ion`, 13 assets: GameObjects with `ART:`/relative-`xi:include` bases, `=$MACRO`
  WeaponTemplates, inheritFrom chains): overlay emits **exactly the 13 declared**; a plain whole-file compile
  emits **26** (13 base deps embedded). Gate passes, big is `big_is_complete` + fsynced, GameObject decompiles
  `ok=1`.

## The non-negotiable gate (verify, don't assert)

Slicing is the mechanism; the **guarantee** is a hard post-compile check: the set of emitted instance ids MUST
equal the user's declared set. Any extra id ⇒ an EA asset leaked in ⇒ **abort** (names listed). Any missing id ⇒
an override failed to compile ⇒ **abort**. A package can never silently ship EA content, because the gate refuses
it. Pairs with the big-integrity discipline ([0007]): fsync + `big_is_complete` on the packed archive.

## `mod check` dangling-ref severity is scope-driven (two-condition)

`mod check` resolves references against the gameplay reference manifests it loads (`-rm`: global_common_2 +
static_common_2). A reference the compiler reports as unknown is an **ERROR only when it is *verifiable here* —
its type is BOTH (a) modeled by OpenWrath (`our_type_hashes`) AND (b) present in the loaded reference scope**; only
then does the loaded set contain that type's full population, so a missing instance is genuinely dangling. A ref
to an unmodeled type, or to a modeled type whose owning stream isn't loaded (art / texture / audio live in art
bigs, not the gameplay streams), is **unverifiable → a WARNING**, never a false abort. This is deliberately
*scope*-driven, not a hardcoded art-type denylist, so it can't calcify into a blind spot.

The implementation combines both halves up front: `verifiable = our_type_hashes ∩ types-present-in-loaded-manifests`.
**Both halves are load-bearing** — modeling a type is necessary but *not sufficient*. When art types are modeled,
the promotion checklist to make their refs verifiable is: **(1)** model + register the type, **and** **(2)** add
its art streams to `mod check`'s reference scope. Do only (1) and a modeled-but-unloaded art ref would flip to a
false positive; the intersection guards against that (a modeled type absent from the loaded scope stays a warning),
but a type that *partially* appears in a loaded gameplay stream (e.g. a few shared `Texture`s in static_common) can
only be made fully correct by (2).

## The overlay LOAD HANDSHAKE — a `<family>.version` file names the postfix (in-game finding)

Byte-correct artifacts are necessary but **not sufficient**: a standalone big containing only
`data\static_mod.{manifest,bin,relo,imp}` crashed the retail game at skirmish load. Note this is **not**
finding [0005]'s signature — 0005 is a *silent no-op* ("the overlay is never consulted"); a **crash** means
the engine *did* engage the overlay and choked. TypeHash coherence was ruled out (our overlay's
`WeaponTemplate` hash `0x90aeab74` == retail `static_common`'s — no [0010] drift).

Observed in the one working self-contained mod (SecondIsomer): each mod stream ships a companion
**`data\<family>.version`** whose **content is the stream postfix** — `data\static.version` = `"_mod\n"`,
`data\static_l.version` = `"_mod\n"`, etc. **Hypothesis** (not verified): this is the engine's overlay
discovery handshake — for base family `static` it reads the `.version`, gets postfix `_mod`, and loads
`static_mod`. `mod package` now emits it to match SI byte-for-byte. **Caveat — this is NOT verified:** the
package crashed the game *both with and without* the `.version` file, so either the stream is engaged
regardless of `.version` (making it not the trigger), or the crash has a cause upstream of it. Treat the
`.version` handshake as a plausible-but-unconfirmed detail, not a settled mechanism.

**The in-game launch settled the loading model — and it is *replacement*, not coexistence:** the static `_mod`
stream REPLACES `static_common` and must be COMPLETE, so this zero-EA *partial* overlay is a correct **diff**,
not a loadable standalone mod. The full evidence (EA's 1.03 patch ships a complete `Static_mod`; the `.version`
postfix selects one stream per family; our version-correct zero-import leaf still crashes) and the four loadable
paths (diff-plus-assemble-at-install, local complete build, INI, bake-into-complete-stream) live in
**[0016](0016-static-mod-stream-is-complete-replacement-not-overlay.md)**. In short: what this finding's builder
produces is the **zero-EA diff**; turning it into something loadable is 0016's subject.

## Scope line honored

This is standard, legitimate mod output: an override is the user's authored derivative (base + their diffs) of a
game they own. "Zero EA content" means not bundling EA's *files/streams* or assets the user never touched — **not**
forbidding an override that inherits base field values. The gate enforces exactly that line: only
user-declared ids ship.

## See also

- [0005](0005-mods-must-live-in-one-target-stream.md), [0006](0006-new-assets-need-stream-insert.md),
  [0008](0008-xinclude-xpointer-not-honored.md), [0007](0007-big-repack-must-be-fsynced-and-verified.md).
- `docs/04-references-and-the-import-graph/README.md` — the overlay/import model.
- `modkit/openwrath` (`cmd_mod_package`), `modkit/README.md`.
</content>
</invoke>
