#!/usr/bin/env python3
"""Tests for the openwrath modkit CLI.

CI-safe: uses ONLY synthetic fixtures (fake directory trees + hand-built byte blobs in a tmpdir).
No EA/game content, no real install, no machine-specific path. Where a real end-to-end check would
need the EA SDK / game data (the .NET compiler, a real .big), we test the LOGIC AROUND that step
and say so in the test docstring.

Runs with pytest if available, else as a plain script:  python3 modkit/tests/test_openwrath.py
(The CLI file is named `openwrath` with no .py extension, so it is loaded by path via importlib.)
"""
import argparse
import contextlib
import importlib.util
import io
import os
import struct
import sys
import tempfile
from pathlib import Path


@contextlib.contextmanager
def _muted():
    """Silence a command's stdout chatter so the test log stays readable."""
    with contextlib.redirect_stdout(io.StringIO()):
        yield

HERE = Path(__file__).resolve().parent
OPENWRATH = HERE.parent / "openwrath"


def _load_module():
    # The CLI file has no .py extension, so give importlib an explicit source loader.
    from importlib.machinery import SourceFileLoader
    loader = SourceFileLoader("openwrath_cli", str(OPENWRATH))
    spec = importlib.util.spec_from_loader("openwrath_cli", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


ow = _load_module()

# Game facts (mirror the CLI constants so fixtures build the paths detection expects).
GAME_DIR_NAME = ow.GAME_DIR_NAME
WINE_DOCS_NAME = ow.WINE_DOCS_NAME


# --- tiny env sandbox --------------------------------------------------------------------
class Sandbox:
    """A tmp HOME + redirected config/XDG + overridable WSL mount, restored on exit."""

    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="openwrath-test-"))
        self.home = self.tmp / "home"
        self.home.mkdir(parents=True)
        self._saved_env = {k: os.environ.get(k) for k in
                           ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME")}
        self._saved_attr = {k: getattr(ow, k) for k in ("CONFIG_PATH", "WSL_MNT", "is_wsl")}
        os.environ["HOME"] = str(self.home)
        os.environ["XDG_CONFIG_HOME"] = str(self.tmp / "config")
        os.environ["XDG_DATA_HOME"] = str(self.tmp / "data")
        os.environ["XDG_CACHE_HOME"] = str(self.tmp / "cache")
        # CONFIG_PATH is computed at import time; redirect it to this sandbox.
        ow.CONFIG_PATH = self.tmp / "config" / "openwrath" / "config.toml"
        ow.is_wsl = lambda: False            # default: native Linux; WSL tests opt in

    def set_wsl(self, mnt: Path):
        ow.is_wsl = lambda: True
        ow.WSL_MNT = mnt

    def close(self):
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        for k, v in self._saved_attr.items():
            setattr(ow, k, v)
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)


# --- fixture builders --------------------------------------------------------------------
def make_native_steam(root: Path, *, with_mods=True) -> dict:
    """A fake native-Linux Steam/Proton layout: install + prefix + mods."""
    steam = root / ".local/share/Steam"
    install = steam / "steamapps/common" / GAME_DIR_NAME
    install.mkdir(parents=True)
    (install / "CNC3EP1.exe").write_text("stub")
    (install / "CNC3EP1_english_1.3.SkuDef").write_text("stub")
    pfx = steam / "steamapps/compatdata/24810/pfx"
    mods = pfx / "drive_c/users/steamuser/Documents" / WINE_DOCS_NAME / "Mods"
    if with_mods:
        mods.mkdir(parents=True)
    else:
        pfx.mkdir(parents=True)
    return {"steam": steam, "install": install, "pfx": pfx, "mods": mods}


def make_wsl_tree(mnt: Path, *, library_vdf=False) -> dict:
    """A fake WSL /mnt tree: Windows Steam + game + a Windows-user Mods dir. Optionally a
    libraryfolders.vdf that points the install onto another (translated) drive."""
    steam = mnt / "c/Program Files (x86)/Steam"
    steam.mkdir(parents=True)
    if library_vdf:
        # Install lives on D: -> /mnt/d. The .vdf stores a Windows path with escaped backslashes.
        (steam / "steamapps").mkdir(parents=True)
        (steam / "steamapps/libraryfolders.vdf").write_text(
            '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"D:\\\\SteamLibrary"\n\t}\n}\n')
        install = mnt / "d/SteamLibrary/steamapps/common" / GAME_DIR_NAME
    else:
        install = steam / "steamapps/common" / GAME_DIR_NAME
    install.mkdir(parents=True)
    (install / "CNC3EP1.exe").write_text("stub")
    (install / "CNC3EP1_english_1.3.SkuDef").write_text("stub")
    mods = (mnt / "c/Users/Gamer/Documents" / WINE_DOCS_NAME / "Mods")
    mods.mkdir(parents=True)
    # Built-in accounts that must be skipped:
    (mnt / "c/Users/Public/Documents" / WINE_DOCS_NAME / "Mods").mkdir(parents=True)
    return {"steam": steam, "install": install, "mods": mods}


def make_byo_fixtures(root: Path) -> dict:
    """Fake bring-your-own material under a base dir, so init's auto-search finds it."""
    sdk = root / "kw-mod-sdk/KanesWrathXMLFiles"
    sdk.mkdir(parents=True)
    (sdk / "GlobalData").mkdir()
    (sdk / "GlobalData/Armor.xml").write_text(
        '<?xml version="1.0"?><AssetDeclaration/>')
    schema = root / "kw-mod-sdk/xsd/CnC3Types.xsd"
    schema.parent.mkdir(parents=True)
    schema.write_text('<?xml version="1.0"?><xs:schema/>')
    bm = root / "kw-mod-sdk/base-manifests"
    bm.mkdir(parents=True)
    (bm / "static_common_2.manifest").write_bytes(b"\x00" * 48)
    (bm / "global_common_2.manifest").write_bytes(b"\x00" * 48)
    sh = root / "kw-mod-sdk/StringHashes.xml"
    sh.write_text('<AssetDeclaration xmlns="uri:ea.com:eala:asset">'
                  '<StringHashTable id="TheStringTable">'
                  '<StringAndHash Hash="1" Text="Foo" /></StringHashTable></AssetDeclaration>')
    return {"sdk": sdk, "schema": schema, "base_manifests": bm, "stringhashes": sh}


# --- RefPack literal encoder (no compressor ships in lib/refpack.py; build a valid stream) ---
def refpack_encode_literal(data: bytes) -> bytes:
    """Encode `data` as a VALID RefPack stream using only literal runs + a terminator. Exercises
    the real lib/refpack.decompress against a byte-faithful stream (lib ships no compressor)."""
    out = bytearray([0x10, 0xFB])               # flags(no 0x80 -> 3-byte size), magic
    n = len(data)
    out += bytes([(n >> 16) & 0xFF, (n >> 8) & 0xFF, n & 0xFF])
    rem = n % 4
    bulk = n - rem
    i = 0
    while i < bulk:
        chunk = min(112, bulk - i)              # literal-run opcode max is 112 (ctrl<=0xFB)
        out.append(0xE0 | (((chunk - 4) // 4) & 0x1F))
        out += data[i:i + chunk]
        i += chunk
    out.append(0xFC | rem)                       # terminator carrying the last 0..3 bytes
    out += data[bulk:bulk + rem]
    return bytes(out)


def make_big(members: dict) -> bytes:
    """Build a minimal BIG4 archive (same layout bigextract/biglist read): members = {name: bytes}."""
    names = list(members)
    hdr = 16 + sum(8 + len(n.encode("latin1")) + 1 for n in names)
    table = bytearray()
    data = bytearray()
    for n in names:
        foff = hdr + len(data)
        payload = members[n]
        table += struct.pack(">II", foff, len(payload))
        table += n.encode("latin1") + b"\x00"
        data += payload
    out = bytearray(b"BIG4")
    out += struct.pack("<I", 16 + len(table) + len(data))   # archive size (LE)
    out += struct.pack(">I", len(names))                    # entry count (BE)
    out += struct.pack(">I", hdr)                           # header size (BE)
    out += table + data
    return bytes(out)


# --- tests -------------------------------------------------------------------------------
def test_config_roundtrip():
    sb = Sandbox()
    try:
        cfg = {"steam_root": "/x/steam", "sdk": "/x/sdk", "schema": "/x/CnC3Types.xsd"}
        ow.write_config(cfg)
        back = ow.read_config()
        assert back["steam_root"] == "/x/steam"
        assert back["sdk"] == "/x/sdk"
        assert back["schema"] == "/x/CnC3Types.xsd"
        # keys not set come back empty, never missing
        assert back.get("prefix", "") == ""
    finally:
        sb.close()


def test_detect_native():
    sb = Sandbox()
    try:
        lay = make_native_steam(sb.home)
        root, install, prefix = ow.find_install_and_prefix()
        assert install == lay["install"], (install, lay["install"])
        assert prefix == lay["pfx"]
        assert ow.find_mods_dir(prefix) == lay["mods"]
        assert ow.find_install_skudef(install).name == "CNC3EP1_english_1.3.SkuDef"
    finally:
        sb.close()


def test_detect_wsl():
    sb = Sandbox()
    try:
        mnt = sb.tmp / "mnt"
        mnt.mkdir()
        lay = make_wsl_tree(mnt)
        sb.set_wsl(mnt)
        root, install, prefix = ow.find_install_and_prefix()
        assert install == lay["install"], (install, lay["install"])
        assert prefix is None                 # no Proton prefix on WSL
        assert ow.find_mods_dir_wsl() == lay["mods"]
    finally:
        sb.close()


def test_detect_wsl_libraryfolders_translation():
    sb = Sandbox()
    try:
        mnt = sb.tmp / "mnt"
        mnt.mkdir()
        lay = make_wsl_tree(mnt, library_vdf=True)
        sb.set_wsl(mnt)
        # The install lives on D:\SteamLibrary; detection must translate that to /mnt/d.
        root, install, prefix = ow.find_install_and_prefix()
        assert install == lay["install"], (install, lay["install"])
        assert str(install).startswith(str(mnt / "d"))
    finally:
        sb.close()


def test_init_non_interactive():
    sb = Sandbox()
    try:
        make_native_steam(sb.home)
        byo = make_byo_fixtures(sb.home)
        with _muted():
            rc = ow.cmd_init(argparse.Namespace(non_interactive=True, yes=False))
        assert rc == 0
        cfg = ow.read_config()
        assert cfg["game_install"].endswith(GAME_DIR_NAME)
        assert cfg["mods_dir"].endswith("Mods")
        assert cfg["sdk"] == str(byo["sdk"])
        assert cfg["base_manifests"] == str(byo["base_manifests"])
        assert cfg["stringhashes"] == str(byo["stringhashes"])
        # schema may come from the fixture OR (via probe_byo) the repo's own schemas/ tree;
        # either way it must be a valid, on-disk CnC3Types.xsd.
        assert cfg["schema"].endswith("CnC3Types.xsd") and Path(cfg["schema"]).exists()
    finally:
        sb.close()


def test_init_idempotent():
    sb = Sandbox()
    try:
        make_native_steam(sb.home)
        make_byo_fixtures(sb.home)
        with _muted():
            ow.cmd_init(argparse.Namespace(non_interactive=True, yes=False))
        first = ow.read_config()
        with _muted():
            ow.cmd_init(argparse.Namespace(non_interactive=True, yes=False))
        second = ow.read_config()
        assert first == second, "re-running init changed a good config"
    finally:
        sb.close()


def test_stringhashes_merge_collect_write():
    """gen-stringhashes LOGIC: compiling needs the real EA SDK, so test the collection/merge/write
    around the compiler call using synthetic per-file cache/StringHashes.xml fixtures."""
    sb = Sandbox()
    try:
        caches = sb.tmp / "caches"
        (caches / "c0").mkdir(parents=True)
        (caches / "c1").mkdir(parents=True)
        tbl = ('<AssetDeclaration xmlns="uri:ea.com:eala:asset">'
               '<StringHashTable id="TheStringTable">{rows}</StringHashTable></AssetDeclaration>')
        (caches / "c0/StringHashes.xml").write_text(tbl.format(rows=(
            '<StringAndHash Hash="10" Text="Alpha" />'
            '<StringAndHash Hash="20" Text="Beta" />')))
        (caches / "c1/StringHashes.xml").write_text(tbl.format(rows=(
            '<StringAndHash Hash="20" Text="Beta" />'       # duplicate, same text
            '<StringAndHash Hash="20" Text="COLLIDE" />'    # collision -> first wins
            '<StringAndHash Hash="5" Text="Gamma" />')))    # unique
        merged = ow._collect_stringhashes(caches)
        assert merged == {5: "Gamma", 10: "Alpha", 20: "Beta"}, merged
        out = sb.tmp / "data/openwrath/StringHashes.xml"
        ow._write_stringhashes(out, merged)
        assert out.exists()
        # Reparse and confirm sorted-by-hash placement + content survive the write.
        reparsed = ow._merge_stringhashes([out])
        assert reparsed == merged
        text = out.read_text()
        assert text.index('Hash="5"') < text.index('Hash="10"') < text.index('Hash="20"')
    finally:
        sb.close()


def test_gen_stringhashes_errors_without_sdk():
    """No traceback when prerequisites are missing — a clean error pointing at init."""
    sb = Sandbox()
    try:
        ow.write_config({})            # empty config: no sdk/schema
        raised = False
        try:
            ow.cmd_gen_stringhashes(argparse.Namespace(out=None, source=None))
        except SystemExit as e:
            raised = True
            assert "init" in str(e)
        assert raised, "expected a clean SystemExit, not a traceback"
    finally:
        sb.close()


def test_refpack_roundtrip():
    """RefPack decompress against a byte-faithful literal-encoded stream (lib ships no compressor)."""
    sys.path.insert(0, str(ow.LIB))
    import refpack
    for blob in (b"", b"abc", b"abcd", os.urandom(300), bytes(range(256)) * 3):
        enc = refpack_encode_literal(blob)
        out, unsize = refpack.decompress(enc)
        assert out == blob, (len(out), len(blob))
        assert unsize == len(blob)


def test_extract_manifests():
    """extract-manifests: finding the base-stream member in a .big, RefPack-decompressing it, and
    placing it under base_manifests + updating the config. Uses a synthetic BIG4 + literal RefPack
    stream (no real game data)."""
    sb = Sandbox()
    try:
        lay = make_native_steam(sb.home)
        ow.write_config({"game_install": str(lay["install"])})
        # Put a compressed static_common_2.manifest and a STORED global_common_2.manifest in a .big.
        payload_sc = b"STATIC-COMMON-MANIFEST-BYTES" * 10
        payload_gc = b"\x00GLOBAL-COMMON-RAW" * 5         # does not start with a refpack magic
        big_bytes = make_big({
            "data\\static_common_2.manifest": refpack_encode_literal(payload_sc),
            "data\\global_common_2.manifest": payload_gc,
        })
        (lay["install"] / "KANEWRATH.big").write_bytes(big_bytes)
        out_dir = sb.tmp / "data/openwrath/base-manifests"
        with _muted():
            rc = ow.cmd_extract_manifests(argparse.Namespace(out=None))
        assert rc == 0
        assert (out_dir / "static_common_2.manifest").read_bytes() == payload_sc
        assert (out_dir / "global_common_2.manifest").read_bytes() == payload_gc
        cfg = ow.read_config()
        assert cfg["base_manifests"] == str(out_dir)
    finally:
        sb.close()


def test_extract_manifests_errors_without_install():
    sb = Sandbox()
    try:
        ow.write_config({})
        raised = False
        try:
            ow.cmd_extract_manifests(argparse.Namespace(out=None))
        except SystemExit as e:
            raised = True
            assert "init" in str(e) or "detect" in str(e)
        assert raised
    finally:
        sb.close()


def test_default_stringhashes_no_personal_path():
    """The removed baked-in personal path must not reappear: fall back only to the XDG default."""
    sb = Sandbox()
    try:
        assert ow._default_stringhashes({}) is None     # nothing configured, nothing produced yet
        xdg = Path(os.environ["XDG_DATA_HOME"]) / "openwrath" / "StringHashes.xml"
        xdg.parent.mkdir(parents=True, exist_ok=True)
        xdg.write_text("<x/>")
        assert ow._default_stringhashes({}) == str(xdg)
        import inspect
        assert "cnc-kw-godmod" not in inspect.getsource(ow._default_stringhashes)
    finally:
        sb.close()


# --- runner (used when pytest is absent) -------------------------------------------------
def _run_all():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            import traceback
            print(f"FAIL  {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())
