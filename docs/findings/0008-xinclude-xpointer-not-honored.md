# 0008 — The compiler doesn't honor `xi:include` **xpointer**, breaking units that splice module children

**Status:** FIXED · 2026-11-21 (found unfixed, fixed same day)

> Unlike findings 0001–0007 (truths about the game's *data format*), this was a defect in **our compiler**.

## Resolution (what actually fixed it)

**The original diagnosis below was wrong about the mechanism.** `Mvp.Xml` is a red herring — it does **not load
on .NET/Linux** (you see a benign `Could not load XIncludingReader from Mvp.Xml.dll` at startup), so
`XIncludingReaderWrapper.GetReader` returns null. The real XInclude work is done by a **custom resolver
`ResolveXIncludes` in `AssetDeclarationDocument.cs`** (called after `XmlDocument.Load`), which imported each
`href` target's whole `DocumentElement` and **never read the `xpointer`**.

Fix (one file, `AssetDeclarationDocument.cs`, ~+56 lines): in `ResolveXIncludes`, if the `xi:include` has an
`xpointer`, splice in **only the selected node-set** (new helper `SelectXPointerNodes` parses the
`xmlns(prefix=uri)` bindings into an `XmlNamespaceManager` and evaluates the `xpointer(xpath)` with
`SelectNodes`); if no `xpointer`, the original whole-document import path is unchanged, so plain `xi:include`
still pulls the full document. The KW XPointer surface is tiny and uniform — 302 occurrences, all
`xmlns(n=uri:ea.com:eala:asset) xpointer(/n:Wrapper/child::*)`, no `element()` scheme.

Build: canonical config is **`dotnet build -c Debug -p:Platform=x64 source/BinaryAssetBuilder.sln`**
(`AllowUnsafeBlocks` is gated on the x64 platform; a plain `-c Debug` fails `CS0227`).

**Verified:** `GDICommando` compiles and **round-trips byte-exact** (closed-loop); a non-xpointer weapon
round-trips byte-exact (no regression); the `CaptureBehavior` include's two modules land exactly once with no
nested `<Behaviors>`; plain (non-xpointer) includes still resolve. See the regression run in the session notes.

---

_Original analysis (kept for the record; the Mvp.Xml attribution was incorrect):_

## Context

Many stock GameObjects assemble their `<Behaviors>` partly from shared include files, using an `xi:include`
with an **xpointer** that selects just the *children* of the included file's `<Behaviors>` — so the wrapper is
stripped and only the modules are spliced in. Example, from `GDI/Units/GDICommando.xml`:

```xml
<Behaviors>
  ...
  <xi:include href="DATA:Includes/CaptureBehavior.xml"
      xpointer="xmlns(n=uri:ea.com:eala:asset) xpointer(/n:Behaviors/child::*)" />
</Behaviors>
```

`CaptureBehavior.xml` is itself `<Behaviors><CaptureBehavior .../></Behaviors>`; the xpointer picks
`/n:Behaviors/child::*` so only `<CaptureBehavior>` lands inside the host `<Behaviors>`.

## Finding

**Our XInclude path ignores the `xpointer` and splices in the *whole* included document — including its
`<Behaviors>` wrapper.** The result is `<Behaviors><Behaviors>…</Behaviors></Behaviors>`, which the schema
rejects:

```
Critical: The element Behaviors is not expected in Behaviors
```

So **any unit whose includes use an xpointer cannot be compiled** — e.g. `GDICommando` (and, by inheritance
pattern, likely a broad class of infantry/hero units). It blocks overriding those GameObjects at all, even for
a one-line change (we hit it trying to bump the Commando's locomotor speed; the weapon-only override, which
needs no GameObject compile, was unaffected).

## Evidence

- `GDICommando` compile fails with the error above; the offending directive is the xpointer `xi:include` shown
  above; removing the `GDICommando` GameObject override (keeping only `WeaponTemplate` overrides) compiles fine.
- The XInclude is wrapped in correctly: `AssetDeclarationDocument.Load` sets
  `reader = XIncludingReaderWrapper.GetReader(xmlReader, resolver) ?? xmlReader` (AssetDeclarationDocument.cs
  ~line 1317), and `Debug/Mvp.Xml.dll` **is** present — so includes *are* expanded; it's specifically the
  xpointer selection that isn't applied (the whole resource is pulled in instead of the xpointer node-set).

## How to fix (directions, not yet done)

Likely one of:
1. **Confirm/repair the `Mvp.Xml` XPointer path.** `Mvp.Xml.XInclude.XIncludingReader` is supposed to support
   the `xpointer()` scheme over XPath. Check whether this xpointer form (`xmlns(...) xpointer(/n:…/child::*)`)
   is actually evaluated, whether the namespace binding reaches the evaluator, and whether a failed/underused
   xpointer silently falls back to including the whole resource. A config or binding fix may be all it needs.
2. **Pre-process xpointer includes ourselves** before/instead of Mvp.Xml: for each `xi:include` carrying an
   `xpointer`, resolve `href`, parse the target, run the XPath (honoring the `xmlns(...)` prefix bindings), and
   splice the selected node-set in place of the include. This removes the Mvp.Xml dependency for this case.
3. **Replace the XInclude layer** with a small custom processor that implements `href` + `xpointer` (element()
   and xmlns()/xpointer(xpath) schemes) directly — the subset KW data actually uses is small.

**Validation:** after a fix, `GDICommando` (and the deferred Commando speed-boost override) must compile; spot
-check that the spliced modules appear exactly once (no `<Behaviors>` nesting) and that a known xpointer-using
unit round-trips. Add an xpointer-include unit to the compile corpus so this can't regress silently.

## Impact / coverage note

This is a **compiler coverage gap**, not a data-format fact: it narrows which *stock units* can be recompiled
or overridden. Worth surfacing in `docs/reference/COVERAGE.md` as a known limitation until fixed, and worth a
corpus test so we measure it.

## See also

- `source/BinaryAssetBuilder.Core/BinaryAssetBuilder/Core/XIncludingReaderWrapper.cs` (the Mvp.Xml shim),
  `…/SageXml/AssetDeclarationDocument.cs` (where the reader is wrapped).
