# Setup — building and running the toolchain

This repository ships **only our MIT-licensed code** (a Linux-native SAGE/Kane's Wrath asset **compiler**
and **decompiler**). It contains **no EA game content and no SDK schemas** — you supply those from your own
legally-owned game install and the Kane's Wrath Mod SDK. This page explains exactly what to provide and where
to point it, so anyone (including us) can reproduce a working setup from scratch.

---

## 1. Prerequisites

- **Linux** (no Wine/VM needed).
- **.NET SDK 8.0 or newer.** The projects target `net8.0`. If your installed runtime is a newer major
  (e.g. .NET 10), run with `DOTNET_ROLL_FORWARD=LatestMajor` (shown below) — no downgrade required.
- `python3` (used only by `tools/roundtrip.sh` for the byte-compare).

Check: `dotnet --version`

---

## 2. Data you must supply (not in this repo)

These are **EA / Mod-SDK material** — owned by EA, redistributed by the community SDK. We do not ship them.
Obtain them from your own copy of the **Kane's Wrath Mod SDK** and your installed game.

| What | Put it at (default) | Override with | Needed for |
|------|--------------------|---------------|------------|
| **XSD schema tree** (`CnC3Types.xsd` + includes) | `schemas/kw/xsd/` | `KW_SCHEMA` (path to `CnC3Types.xsd`) | compile **and** decompile (field shape, enums, refType) |
| **SDK asset XML** (`KanesWrathXMLFiles/`) | `~/kw-mod-sdk/KanesWrathXMLFiles` | `KW_DATAROOT` | compiling the game's source XML; the round-trip harness |
| **Base-stream manifests** (for cross-stream refs) | `~/kw-mod-sdk/base-manifests/` | `KW_BASEMANIFESTS` | resolving references into base-game streams (audio/art) |

### Where these come from
- **Schemas + SDK XML:** the Kane's Wrath Mod SDK (community mirrors exist, e.g. a `KanesWrath-MODSDK`
  repo; the upstream `BinaryAssetBuilder` project also carries a schema tree). Copy its `xsd` tree into
  `schemas/kw/xsd/` (or point `KW_SCHEMA` at your `CnC3Types.xsd`).
- **Base-stream manifests:** extract and RefPack-decompress the `.manifest` files from your installed game's
  base `.big` streams (`global_common_2`, `static_common_2`, `global_english_2`, …). These are used purely
  to type/resolve cross-stream references; they are never merged into output.

> None of the above is required just to **build** the code — only to **run** a compile/decompile against
> real assets.

---

## 3. Build

```bash
cd source
dotnet build BinaryAssetBuilder.sln -c Debug -p:Platform=x64
# or just the pieces you need:
dotnet build BinaryAssetBuilder/BinaryAssetBuilder.csproj   -c Debug -p:Platform=x64   # compiler
dotnet build bab-decompile/bab-decompile.csproj            -c Debug -p:Platform=x64   # decompiler CLI
```

Outputs land in `Debug/` (`BinaryAssetBuilder.dll`, `bab-decompile.dll`, …).

If your installed .NET major is newer than the target, prefix runtime commands with:
```bash
export DOTNET_ROLL_FORWARD=LatestMajor DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
```

---

## 4. Run

**Note:** the compiler resolves its input path *relative to the data root* (`-dr`). Pass the source as a
dataroot-relative path (e.g. `GlobalData/Armor.xml`), not an absolute path.

### Compile (authoring XML → binary asset stream)
```bash
dotnet Debug/BinaryAssetBuilder.dll GlobalData/Armor.xml \
  -dr:"$KW_DATAROOT" -od:/tmp/out \
  -sp:"$KW_SCHEMA" \
  -rm:"$KW_BASEMANIFESTS/global_common_2.manifest;$KW_BASEMANIFESTS/static_common_2.manifest;$KW_BASEMANIFESTS/global_english_2.manifest" \
  -sc:false -bc:false
# produces a .manifest + per-asset .asset files under /tmp/out
```

### Decompile (binary asset stream → authoring XML)
```bash
dotnet Debug/bab-decompile.dll decompile /tmp/out/<path>/<name>.manifest \
  --assets /tmp/out/<path>/<name>/assets \
  --schema "$KW_SCHEMA" \
  --rm "$KW_BASEMANIFESTS/global_common_2.manifest;$KW_BASEMANIFESTS/static_common_2.manifest;$KW_BASEMANIFESTS/global_english_2.manifest" \
  --stringhashes /path/to/StringHashes.xml \
  --combined decompiled.xml
# --stringhashes is optional but needed to recover module-tag / id strings (see roundtrip harness for how
#   the compiler is asked to emit it, via -scd:<cachedir>)
```

### Verify losslessness (the correctness gate)
`tools/roundtrip.sh` compiles a source file, decompiles it, recompiles the decompiled XML, and asserts the
instance/relocation/import bytes are **identical** — per asset, keyed off the manifest:
```bash
export KW_DATAROOT=~/kw-mod-sdk/KanesWrathXMLFiles
export KW_BASEMANIFESTS=~/kw-mod-sdk/base-manifests
export KW_SCHEMA=.../schemas/kw/xsd/CnC3Types.xsd   # or leave default if schemas/ is populated

tools/roundtrip.sh GlobalData/Armor.xml       # -> total=207 byte_exact=207 fail=0 missing=0
tools/roundtrip.sh GlobalData/Weapon.xml      # -> 456/456
tools/roundtrip.sh GDI/Structures/GDIConstructionYard.xml   # -> 1/1 (a GameObject)
```
A type is "byte-exact" only if it prints `fail=0 missing=0`. This harness is how reliability is *proven*
rather than asserted.

---

## 5. Reproducing our reported results

With the three data inputs above in place, the following should round-trip byte-exact:
`GlobalData/Armor.xml` (207), `GlobalData/Locomotor.xml` (79), `GlobalData/AttributeModifier.xml` (78),
`GlobalData/Weapon.xml` (456), and GameObjects such as `GDI/Structures/GDIConstructionYard.xml`,
`GDI/Structures/GDIWallHub.xml`. Broader per-type coverage is tracked by the corpus sweep (run the harness
across the full `KanesWrathXMLFiles` tree).
