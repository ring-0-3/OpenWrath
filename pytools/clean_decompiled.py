#!/usr/bin/env python3
# Clean a WrathEd-captured decompiled asset XML:
#  - strip UTF-8 BOM
#  - drop the leading "Generated in:" status line + blanks (keep from <?xml)
#  - drop the trailing "Asset Dump:" / hex section (keep through </AssetDeclaration>)
#  - lowercase boolean attribute values ="True"->="true", ="False"->="false"
# usage: clean_decompiled.py <raw.xml> <clean.xml>
import sys, re

raw, out = sys.argv[1], sys.argv[2]
data = open(raw, "rb").read()
# strip BOM
if data[:3] == b"\xef\xbb\xbf":
    data = data[3:]
text = data.decode("utf-8", "replace")

start = text.find("<?xml")
if start < 0:
    start = text.find("<AssetDeclaration")
end_tag = "</AssetDeclaration>"
end = text.find(end_tag)
assert start >= 0 and end >= 0, (start, end)
body = text[start:end + len(end_tag)]

# lowercase boolean attr values
body = body.replace('="True"', '="true"').replace('="False"', '="false"')

# normalize to end with single newline
body = body.rstrip() + "\n"
open(out, "w", encoding="utf-8").write(body)
print(f"wrote {out}  ({len(body)} bytes)")
# quick sanity: count remaining True/False attr values
rem = len(re.findall(r'="(?:True|False)"', body))
print(f"  remaining True/False attr values: {rem}")
