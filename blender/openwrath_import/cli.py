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


def decompile_asset(cfg: CliConfig, asset_name: str, outdir: str,
                    *, semantic_mesh: bool = True, timeout: int = 600) -> str:
    """Decompile ONE asset by name into ``outdir``; return the written XML path.

    Mirrors ``tools/mesh-repack-gate.sh``'s invocation:
      ``bab-decompile decompile <manifest> --only <NAME> --outdir <DIR>
        [--semantic-mesh] [--rm a;b;c] [--schema x] [--stringhashes h]``
    """
    os.makedirs(outdir, exist_ok=True)
    argv = list(cfg.bab_cmd) + [
        "decompile", cfg.manifest,
        "--only", asset_name,
        "--outdir", outdir,
    ]
    if semantic_mesh:
        argv.append("--semantic-mesh")
    if cfg.ref_manifests:
        argv += ["--rm", ";".join(cfg.ref_manifests)]
    if cfg.schema:
        argv += ["--schema", cfg.schema]
    if cfg.stringhashes:
        argv += ["--stringhashes", cfg.stringhashes]

    env = dict(os.environ)
    env.setdefault("DOTNET_ROLL_FORWARD", "LatestMajor")
    env.setdefault("DOTNET_CLI_TELEMETRY_OPTOUT", "1")
    env.setdefault("DOTNET_NOLOGO", "1")

    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout, env=env
        )
    except FileNotFoundError as e:
        raise DecompileError(
            f"could not launch bab-decompile ({argv[0]!r}): {e}. "
            f"Set the CLI command in the import dialog."
        ) from e

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
