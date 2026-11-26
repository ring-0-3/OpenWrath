"""Thin wrapper around the OpenWrath ``bab-decompile`` CLI.

The add-on reimplements **no** W3D format logic (``docs/design/blender-integration.md``):
every byte→XML conversion goes through this one shell-out. This module knows only how
to *invoke* the CLI and where it put its output files — never what the bytes mean.

The caller supplies all paths (manifest, reference manifests, schema, stringhashes,
and the ``bab-decompile`` command itself). Nothing is hard-coded to a machine.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CliConfig:
    """Everything needed to run ``bab-decompile``. All user-supplied.

    ``bab_cmd`` is the launcher: either a native ``bab-decompile`` on PATH, or
    ``["dotnet", "/path/to/Debug/bab-decompile.dll"]``.
    """

    bab_cmd: list[str]
    manifest: str
    schema: Optional[str] = None
    ref_manifests: list[str] = field(default_factory=list)   # joined with ';'
    stringhashes: Optional[str] = None

    @classmethod
    def from_env_or_fields(cls, bab_cmd, manifest, schema="", ref_manifests="",
                           stringhashes="") -> "CliConfig":
        cmd = bab_cmd if isinstance(bab_cmd, list) else _split_cmd(bab_cmd)
        rms = [r for r in ref_manifests.replace(";", "\n").splitlines() if r.strip()]
        return cls(
            bab_cmd=cmd,
            manifest=manifest,
            schema=schema or None,
            ref_manifests=rms,
            stringhashes=stringhashes or None,
        )


def _split_cmd(s: str) -> list[str]:
    import shlex
    return shlex.split(s)


class DecompileError(RuntimeError):
    pass


def resolve_bab_cmd(hint: str = "") -> list[str]:
    """Best-effort locate a usable bab-decompile launcher.

    Order: explicit hint -> ``bab-decompile`` on PATH -> ``dotnet <repo>/Debug/bab-decompile.dll``
    discovered by walking up from this file. Returns the launcher as an argv list.
    """
    if hint:
        return _split_cmd(hint)
    found = shutil.which("bab-decompile")
    if found:
        return [found]
    here = os.path.dirname(os.path.abspath(__file__))
    cur = here
    for _ in range(6):
        cand = os.path.join(cur, "Debug", "bab-decompile.dll")
        if os.path.isfile(cand):
            dotnet = shutil.which("dotnet") or "dotnet"
            return [dotnet, cand]
        cur = os.path.dirname(cur)
    # Last resort: assume it's on PATH under the plain name; the run will error clearly.
    return ["bab-decompile"]


# --------------------------------------------------------------------------- #
# THE single source of truth for "how to invoke bab-decompile for semantic mesh".
#
# Every consumer — this add-on's on-demand resolver, the `openwrath blender` modkit
# command, and blender/tests/make_fixture.sh — routes through build_decode_argv()
# so the decode invocation is constructed in exactly ONE place (CLAUDE.md invariant 3
# / blender-integration.md §3: never a second/third copy of the bab-decompile command).
# --------------------------------------------------------------------------- #

def build_decode_argv(bab_cmd, manifest, outdir, *, subcommand="decompile-stream",
                      only=None, type_hex=None, semantic_mesh=True,
                      schema=None, ref_manifests=None, stringhashes=None) -> list:
    """Construct the argv for a bab-decompile decode. ``bab_cmd`` is the launcher
    (list, e.g. ``["dotnet", ".../bab-decompile.dll"]`` or ``["bab-decompile"]``).

    ``subcommand`` is ``decompile-stream`` (writes ``<Type>.<name>.xml``, needed for a
    linked stream) or ``decompile`` (writes ``<name>.xml``). ``ref_manifests`` may be a
    list or a ';'-joined string. ``--semantic-mesh`` is on by default — editable mesh
    geometry is the whole point of the Blender tier (and the re-pack gate)."""
    cmd = bab_cmd if isinstance(bab_cmd, list) else _split_cmd(bab_cmd)
    argv = list(cmd) + [subcommand, manifest, "--outdir", outdir]
    if only:
        argv += ["--only", only]
    if type_hex:
        argv += ["--type", type_hex]
    if semantic_mesh:
        argv.append("--semantic-mesh")
    if ref_manifests:
        rm = ref_manifests if isinstance(ref_manifests, str) else ";".join(ref_manifests)
        if rm:
            argv += ["--rm", rm]
    if schema:
        argv += ["--schema", schema]
    if stringhashes:
        argv += ["--stringhashes", stringhashes]
    return argv


# --------------------------------------------------------------------------- #
# THE single source of truth for "how to invoke the compiler (BinaryAssetBuilder)".
#
# The exporter's round-trip gate (tools/blender-roundtrip-gate.sh) and any consumer that
# recompiles exported authoring XML route through build_compile_argv() so the compile
# command is constructed in exactly ONE place — mirroring build_decode_argv (CLAUDE.md
# invariant 3). The flags are identical to tools/mesh-repack-gate.sh's recompile step
# (-dr/-od/-sp/-rm, -sc:false -bc:false), so the exporter drives the SAME packer the
# 0025 re-pack gate validated — never a second compile path.
# --------------------------------------------------------------------------- #

def build_compile_argv(bab_cmd, xml, *, dataroot, outdir, schema,
                       ref_manifests=None, state_cache=False, byte_cache=False) -> list:
    """Construct the argv for a BinaryAssetBuilder compile of a single authoring XML.

    ``bab_cmd`` is the launcher (list, e.g. ``["dotnet", ".../BinaryAssetBuilder.dll"]``).
    ``ref_manifests`` may be a list or a ';'-joined string. ``state_cache`` / ``byte_cache``
    map to ``-sc`` / ``-bc`` (both off for a clean one-shot compile, as the gate uses)."""
    cmd = bab_cmd if isinstance(bab_cmd, list) else _split_cmd(bab_cmd)
    argv = list(cmd) + [xml, f"-dr:{dataroot}", f"-od:{outdir}", f"-sp:{schema}"]
    if ref_manifests:
        rm = ref_manifests if isinstance(ref_manifests, str) else ";".join(ref_manifests)
        if rm:
            argv.append(f"-rm:{rm}")
    argv += [f"-sc:{'true' if state_cache else 'false'}",
             f"-bc:{'true' if byte_cache else 'false'}"]
    return argv


def compile_asset(bab_cmd, xml, *, dataroot, outdir, schema, ref_manifests=None,
                  timeout: int = 600) -> subprocess.CompletedProcess:
    """Compile one authoring XML via :func:`build_compile_argv` / the shared env. The single
    place the compiler subprocess is spawned (symmetric to :func:`run_decode`)."""
    os.makedirs(outdir, exist_ok=True)
    argv = build_compile_argv(bab_cmd, xml, dataroot=dataroot, outdir=outdir,
                              schema=schema, ref_manifests=ref_manifests)
    try:
        return subprocess.run(argv, capture_output=True, text=True,
                              timeout=timeout, env=_decode_env())
    except FileNotFoundError as e:
        raise DecompileError(
            f"could not launch the compiler ({argv[0]!r}): {e}."
        ) from e


def _decode_env() -> dict:
    env = dict(os.environ)
    env.setdefault("DOTNET_ROLL_FORWARD", "LatestMajor")
    env.setdefault("DOTNET_CLI_TELEMETRY_OPTOUT", "1")
    env.setdefault("DOTNET_NOLOGO", "1")
    return env


def run_decode(argv, *, timeout: int = 600) -> subprocess.CompletedProcess:
    """Run a decode argv (from :func:`build_decode_argv`), raising DecompileError if
    the launcher is missing. The single place the subprocess is spawned."""
    try:
        return subprocess.run(argv, capture_output=True, text=True,
                              timeout=timeout, env=_decode_env())
    except FileNotFoundError as e:
        raise DecompileError(
            f"could not launch bab-decompile ({argv[0]!r}): {e}. "
            f"Set the CLI command in the import dialog / config."
        ) from e


def decompile_asset(cfg: CliConfig, asset_name: str, outdir: str,
                    *, semantic_mesh: bool = True, timeout: int = 600) -> str:
    """Decompile ONE asset by name into ``outdir``; return the written XML path.

    Thin wrapper over :func:`build_decode_argv` / :func:`run_decode` (the shared decode
    invocation) using the ``decompile`` subcommand (writes ``<name>.xml``)."""
    os.makedirs(outdir, exist_ok=True)
    argv = build_decode_argv(
        cfg.bab_cmd, cfg.manifest, outdir, subcommand="decompile",
        only=asset_name, semantic_mesh=semantic_mesh,
        schema=cfg.schema, ref_manifests=cfg.ref_manifests, stringhashes=cfg.stringhashes,
    )
    proc = run_decode(argv, timeout=timeout)

    out_xml = os.path.join(outdir, asset_name + ".xml")
    if not os.path.isfile(out_xml):
        raise DecompileError(
            "bab-decompile did not produce "
            f"{asset_name}.xml (rc={proc.returncode}).\n"
            f"cmd: {' '.join(argv)}\n"
            f"stdout:\n{proc.stdout[-2000:]}\n"
            f"stderr:\n{proc.stderr[-2000:]}"
        )
    return out_xml


# --------------------------------------------------------------------------- #
# Command-line entry so a shell consumer (make_fixture.sh) routes through the SAME
# build_decode_argv() instead of re-encoding the invocation:
#     python3 -m openwrath_import.cli decode --bab "dotnet /…/bab-decompile.dll" \
#         --manifest S.manifest --outdir OUT --only NAME --schema X --rm "a;b" [--type HEX]
# --------------------------------------------------------------------------- #

def _main(argv=None) -> int:
    import argparse
    import sys

    p = argparse.ArgumentParser(prog="openwrath_import.cli",
                                description="shared bab-decompile decode invocation")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("decode", help="decode asset(s) via bab-decompile (semantic mesh)")
    d.add_argument("--bab", required=True, help="launcher, e.g. 'dotnet /path/bab-decompile.dll'")
    d.add_argument("--manifest", required=True)
    d.add_argument("--outdir", required=True)
    d.add_argument("--subcommand", default="decompile-stream",
                   choices=["decompile", "decompile-stream"])
    d.add_argument("--only")
    d.add_argument("--type", dest="type_hex")
    d.add_argument("--schema")
    d.add_argument("--rm", help="';'-separated reference manifests")
    d.add_argument("--stringhashes")
    d.add_argument("--no-semantic-mesh", action="store_true")

    c = sub.add_parser("compile", help="compile one authoring XML via BinaryAssetBuilder")
    c.add_argument("--bab", required=True, help="launcher, e.g. 'dotnet /path/BinaryAssetBuilder.dll'")
    c.add_argument("--xml", required=True)
    c.add_argument("--dataroot", required=True)
    c.add_argument("--outdir", required=True)
    c.add_argument("--schema", required=True)
    c.add_argument("--rm", help="';'-separated reference manifests")
    a = p.parse_args(argv)

    if a.cmd == "compile":
        proc = compile_asset(a.bab, a.xml, dataroot=a.dataroot, outdir=a.outdir,
                             schema=a.schema, ref_manifests=a.rm)
        if proc.returncode != 0:
            sys.stderr.write(proc.stdout[-2000:] + proc.stderr[-2000:])
        return proc.returncode

    os.makedirs(a.outdir, exist_ok=True)
    cmd = build_decode_argv(
        a.bab, a.manifest, a.outdir, subcommand=a.subcommand, only=a.only,
        type_hex=a.type_hex, semantic_mesh=not a.no_semantic_mesh,
        schema=a.schema, ref_manifests=a.rm, stringhashes=a.stringhashes,
    )
    proc = run_decode(cmd)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout[-2000:] + proc.stderr[-2000:])
    return proc.returncode


if __name__ == "__main__":
    import sys
    sys.exit(_main())
