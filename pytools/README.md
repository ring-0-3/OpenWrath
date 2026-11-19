# pytools — SAGE/Kane's Wrath stream & archive utilities

Small, dependency-free Python 3 helpers for the parts of the mod pipeline that sit *around* the compiler and
decompiler: reading/writing `.big` archives, (de)compressing RefPack, and inspecting/splicing compiled asset
streams. They complement the C# compiler (`BinaryAssetBuilder`) and decompiler (`bab-decompile`).

All are standalone scripts (no third-party packages). Run with `python3 pytools/<name>.py …`.

## Archive (EA BIG4)
| Tool | What it does |
|------|--------------|
| `biglist.py` | List the entries (name/offset/size) in a BIGF/BIG4 archive. |
| `bigextract.py` | Extract named raw-stored entries from a BIG4 archive to disk. |
| `pack_big.py` | Write a BIG4 archive (including the 8-byte EA footer the engine requires). |
| `big_replace.py` | Replace one entry in a BIG4 in place, copying the rest byte-for-byte and preserving the original footer. |
| `verify_packer.py` | Round-trip test: read a real BIG, repack it, assert byte-identical (packer self-check). |

## Compression
| Tool | What it does |
|------|--------------|
| `refpack.py` | EA RefPack/QFS decompressor (handles the classic and the KW `0x90` size-prefixed variant). |

## Compiled stream / manifest
| Tool | What it does |
|------|--------------|
| `manifest_names.py` | Dump `(TypeId, InstanceId, Name)` for every asset in a v5 manifest. |
| `manifest_refs.py` | Dump the names of the assets a given asset references. |
| `extract_asset.py` | Pull one asset's instance/relo/imp chunks from a linked stream and show its relocation graph. |
| `splice_asset.py` | Replace one asset in a linked stream (rebuilds the manifest/bin/relo/imp + reference buffer). |

## XML
| Tool | What it does |
|------|--------------|
| `clean_decompiled.py` | Normalize captured decompiled XML (strip BOM/header/hex-dump, lowercase boolean literals). |

## Where they fit
A typical mod build is: **decompile** (`bab-decompile`) → edit XML → **compile** (`tools/kw-compile.sh`) →
**splice** the new asset into the target stream (`splice_asset.py`) → **repack** the `.big`
(`big_replace.py`). The archive/manifest tools are for inspecting and verifying each step. See `../SETUP.md`.
