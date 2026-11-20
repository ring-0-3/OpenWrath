#!/usr/bin/env python3
"""schema-struct-diff.py <Type>

Human-friendly front-end to the ground-truth debugging workflow. For a given asset type it
compares the fields EA's XSD declares against the fields our C# struct actually has (via its
on-disk layout), and for every MISSING field it also shows:
  - the field's TYPE as the XSD declares it, and
  - whether a matching C# type already exists, is a built-in/alias, or must be defined.

So a SIZEDIFF turns into a complete to-do list: which fields to add, of what type, and which
of those types you still need to create -- with nothing appearing out of nowhere.

  MISSING from struct = in the XSD, not our struct  -> the usual cause of a SIZEDIFF
  EXTRA in struct     = in our struct, not the XSD   -> inherited base / rename / check

Comment-aware: fields commented out in the XSD (<!-- ... -->) are ignored.

Usage:  tools/schema-struct-diff.py SpecialPowerTemplate
Requires: built Debug/bab-decompile.dll + the schemas/kw XSD tree (bring-your-own).
"""
import sys, os, re, glob, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# XSD primitive / alias types that map to a C# built-in and never need defining.
PRIMITIVE = {
    "SageReal": "float", "SageInt": "int", "SageUnsignedInt": "uint", "SageShort": "short",
    "SageBool": "SageBool", "Time": "Time", "Angle": "Angle", "Percentage": "Percentage",
    "Velocity": "Velocity", "xs:string": "AnsiString", "AssetId": "AnsiString",
    "xs:int": "int", "xs:unsignedInt": "uint", "xs:float": "float", "xs:boolean": "SageBool",
}


def struct_fields(typ):
    dll = os.path.join(ROOT, "Debug", "bab-decompile.dll")
    env = {**os.environ, "DOTNET_ROLL_FORWARD": "LatestMajor",
           "DOTNET_CLI_TELEMETRY_OPTOUT": "1", "DOTNET_NOLOGO": "1"}
    r = subprocess.run(["dotnet", dll, "layout", typ], cwd=ROOT, env=env,
                       capture_output=True, text=True)
    names, size = [], None
    for line in r.stdout.splitlines():
        s = line.strip()
        if s.startswith("@"):
            names.append(s.split()[-1])
        elif "SizeX86=" in s:
            size = s.split("SizeX86=")[-1].split()[0]
    return names, size


def xsd_fields(typ):
    """Return [(name, xsd_type), ...] in XSD order, comments stripped, plus the file path."""
    for f in glob.glob(os.path.join(ROOT, "schemas", "kw", "**", "*.xsd"), recursive=True):
        txt = open(f, encoding="utf-8", errors="replace").read()
        if f'complexType name="{typ}"' in txt:
            m = re.search(rf'<xs:complexType name="{re.escape(typ)}".*?</xs:complexType>', txt, re.S)
            block = re.sub(r'<!--.*?-->', '', m.group(0) if m else txt, flags=re.S)
            out, seen = [], set()
            for mm in re.finditer(r'<xs:(?:element|attribute)\s+name="([^"]+)"(?:\s+type="([^"]*)")?', block):
                n, t = mm.group(1), (mm.group(2) or "(untyped)")
                if n not in seen:
                    seen.add(n); out.append((n, t))
            return out, os.path.relpath(f, ROOT)
    return None, None


def defined_cs_types():
    s = set()
    for f in glob.glob(os.path.join(ROOT, "source", "SageBinaryData", "**", "*.cs"), recursive=True):
        txt = open(f, encoding="utf-8", errors="replace").read()
        for mm in re.finditer(r'\b(?:enum|struct|class)\s+([A-Za-z_]\w*)', txt):
            s.add(mm.group(1))
    return s


def type_status(xsd_type, defined):
    if xsd_type in defined:
        return "C# type exists ✓"
    if xsd_type in PRIMITIVE or xsd_type.startswith("xs:"):
        return f"built-in → {PRIMITIVE.get(xsd_type, xsd_type)}"
    if xsd_type.endswith("WeakRef"):
        return "weak-ref → TypedAssetId<…>"
    if xsd_type.endswith("Ref"):
        return "ref → AssetReference<…>"
    return "✗ NOT DEFINED — you define this type"


def main():
    if len(sys.argv) != 2:
        print("usage: tools/schema-struct-diff.py <Type>"); sys.exit(2)
    typ = sys.argv[1]
    sf, size = struct_fields(typ)
    xf, xpath = xsd_fields(typ)
    if not sf:
        print(f"no layout for '{typ}' (registered type? Debug/ built?)"); sys.exit(1)
    if xf is None:
        print(f"no XSD complexType found for '{typ}' under schemas/kw/"); sys.exit(1)
    defined = defined_cs_types()
    ss = set(sf); xnames = {n for n, _ in xf}
    missing = [(n, t) for n, t in xf if n not in ss]
    extra = [n for n in sf if n not in xnames]
    w = max((len(n) for n, _ in missing), default=0)
    wt = max((len(t) for _, t in missing), default=0)
    print(f"=== {typ}   (struct SizeX86={size};  xsd: {xpath}) ===")
    print(f"    struct fields={len(sf)}   xsd fields={len(xf)}   in both={len(ss & xnames)}\n")
    print("MISSING from struct  (field : XSD type : what C# type to use):")
    for n, t in missing:
        print(f"    + {n:<{w}}  {t:<{wt}}  [{type_status(t, defined)}]")
    if not missing:
        print("    (none)")
    print("\nEXTRA in struct  (not in XSD) — inherited base / rename / check:")
    print("\n".join(f"    - {n}" for n in extra) if extra else "    (none)")


if __name__ == "__main__":
    main()
