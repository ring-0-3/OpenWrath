# Walkthrough: add a command to the modkit (`mod new` + `mod add`)

A complete, dry-run-tested walkthrough for your **first change to the codebase**. By the end you'll have added
two real subcommands to `modkit/openwrath` and, more importantly, you'll know the *pattern* for adding any
command — so later you can spend your energy on the problem, not the plumbing.

**What you'll build:** `openwrath mod new <project>` (scaffold a mod project) and
`openwrath mod add <project> <asset>` (pull an asset in as an editable override), which closes the loop:
`trace → add → edit a value → bake`.

> Every command and code block below was run for real first. There's one deliberate "gotcha" you'll hit when
> you test — it's called out so you learn *why* the code is written the way it is.

---

## 0. Orientation — the anatomy of a modkit command

`modkit/openwrath` is a single Python file. Every subcommand is just **two pieces**:

1. **A `cmd_*(args)` function** that does the work and returns an exit code. It reads the user's config with
   `read_config()`, asserts required keys with `_need(cfg, "sdk", ...)`, and prints to stdout.
2. **A parser registration in `main()`** — an `add_parser(...)` with its arguments and a
   `.set_defaults(func=cmd_*)` that wires the name to the function.

That's the whole pattern. A *mod project*, for reference, is just a folder with a `mod.toml`
(`[mod]` → `name` / `target` / `stream` / `sources`) and one or more override `.xml` files under `src/`.

Our two new commands sit under the existing `mod` group (next to `mod bake` / `mod revert`), so they're
`mod.add_parser(...)`, not `sub.add_parser(...)`.

**Prereq:** a working setup — `modkit/openwrath show` should be all `[ok]` (you need `sdk` for `mod add`).

---

## 1. Add three small helpers

`mod new` and `mod add` both read and write a project's `mod.toml`, and `mod add` needs to turn an SDK file path
into a `DATA:` include. Add these three helpers **just before `def cmd_mod_bake(args) -> int:`** in
`modkit/openwrath`:

```python
def _read_mod_spec(proj: Path) -> dict:
    """Load a project's [mod] table, or exit with a clear error if there's no mod.toml."""
    import tomllib
    toml = proj / "mod.toml"
    if not toml.exists():
        sys.exit(f"error: no mod.toml in {proj}. Create one with: openwrath mod new {proj.name}")
    return tomllib.loads(toml.read_text()).get("mod", {})


def _write_mod_spec(proj: Path, spec: dict) -> None:
    """Write a project's mod.toml from a [mod] spec dict (name / target / stream / sources)."""
    lines = ["[mod]"]
    for key in ("name", "target", "stream"):
        if spec.get(key) is not None:
            lines.append(f'{key} = "{spec[key]}"')
    srcs = spec.get("sources", [])
    lines.append("sources = [" + ", ".join(f'"{s}"' for s in srcs) + "]")
    (proj / "mod.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _data_relpath(cfg: dict, abspath: Path) -> str:
    """An SDK file's absolute path -> a `DATA:<relative>` include source (relative to the data root)."""
    sdk = Path(cfg["sdk"]).resolve()
    rel = Path(abspath).resolve().relative_to(sdk)
    return "DATA:" + str(rel).replace("\\", "/")
```

Why these: `tomllib` reads TOML but can't *write* it, so `_write_mod_spec` emits the few lines by hand (our
`mod.toml` is deliberately tiny). `_data_relpath` mirrors the include you wrote by hand in the first-mod guide —
`DATA:GlobalData/Weapon.xml` is just the SDK-relative path with a `DATA:` prefix.

## 2. Add `cmd_mod_new`

Right after those helpers:

```python
def cmd_mod_new(args) -> int:
    """Scaffold a new mod project: a mod.toml + an empty src/ dir."""
    proj = Path(args.project).resolve()
    if (proj / "mod.toml").exists():
        sys.exit(f"error: {proj / 'mod.toml'} already exists")
    (proj / "src").mkdir(parents=True, exist_ok=True)
    spec = {"name": args.name or proj.name,
            "target": args.target or "",
            "stream": args.stream,
            "sources": []}
    _write_mod_spec(proj, spec)
    print(f"created mod project: {proj}")
    print(f"  mod.toml  (name={spec['name']}, target={spec['target'] or '<<set me>>'}, stream={spec['stream']})")
    print("  src/      (empty)")
    print()
    if not spec["target"]:
        print("next: set `target` in mod.toml to the installed mod to bake into (e.g. SecondIsomer), then:")
    else:
        print("next:")
    print(f"  openwrath mod add {proj.name} <AssetName>   # pull an asset in as an editable override")
    return 0
```

Nothing exotic — make the `src/` dir, write a `mod.toml`, print next steps. Leaving `target` empty is fine;
`mod bake` already errors clearly if it isn't set by bake time.

## 3. Add `cmd_mod_add` — the interesting one

This is where a real design decision lives. We pull the asset's XML from the **SDK source**, *not* by
decompiling the installed binary. Why: the decompiler has read-gaps on some stream-compiled assets (you saw
`inspect <weapon>` desync to a `<RawAsset>`), but the SDK authoring XML always reads cleanly. We reuse the exact
engine `inspect --source` uses: `grep` the SDK for the id, then `_find_toplevel_block` to extract the asset.

Add after `cmd_mod_new`:

```python
def cmd_mod_add(args) -> int:
    """Pull an asset into a project as an editable override, taken from the SDK *source*
    (not the installed binary — the SDK form always reads and sidesteps decompiler read-gaps)."""
    import subprocess
    proj = Path(args.project).resolve()
    spec = _read_mod_spec(proj)
    cfg = read_config()
    (sdk,) = _need(cfg, "sdk")
    inst, want_type = args.asset, args.type

    # Locate the asset's authoring XML in the SDK — same engine as `inspect --source`.
    r = subprocess.run(["grep", "-rlF", f'id="{inst}"', sdk], capture_output=True, text=True)
    files = [f for f in r.stdout.splitlines() if f]
    if not files:
        sys.exit(f"error: no SDK source under {sdk} declares id=\"{inst}\". Try: openwrath find {inst}")
    files.sort(key=lambda f: ("/maps/" in f.lower(), f))   # prefer authoring files over maps
    hit = None
    for fp in files:
        lines = Path(fp).read_text(encoding="utf-8", errors="replace").splitlines()
        found = _find_toplevel_block(lines, inst, want_type)
        if found:
            tag, start, end = found
            hit = (fp, tag, lines[start:end + 1])
            break
    if not hit:
        hint = f" of type '{want_type}'" if want_type else ""
        sys.exit(f"error: found id=\"{inst}\" in the SDK but no enclosing top-level asset{hint} "
                 f"(it may only appear as a nested reference).")
    fp, tag, body = hit
    inc = _data_relpath(cfg, Path(fp))

    srcrel = f"src/{inst}.xml"
    out = proj / srcrel
    if out.exists() and not args.force:
        sys.exit(f"error: {out} already exists (pass --force to overwrite).")
    override = "\n".join([
        '<?xml version="1.0" encoding="utf-8"?>',
        '<AssetDeclaration',
        '\txmlns="uri:ea.com:eala:asset"',
        '\txmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        '\txmlns:xi="http://www.w3.org/2001/XInclude"',
        '\txmlns:xai="uri:ea.com:eala:asset:instance">',
        '',
        '\t<Tags/>',
        '\t<Includes>',
        f'\t\t<Include type="instance" source="{inc}" />',
        '\t</Includes>',
        '',
        f'\t<!-- Override {tag} "{inst}" in place. inheritFrom itself keeps every original field,',
        '\t     so you only list what you change below. (The current definition was printed when',
        f'\t     this file was created; re-print it any time with `openwrath inspect {inst}`.) -->',
        f'\t<{tag} id="{inst}" inheritFrom="{inst}">',
        '\t\t<!-- e.g. change an attribute or add a child element here -->',
        f'\t</{tag}>',
        '',
        '</AssetDeclaration>',
        '',
    ])
    out.write_text(override, encoding="utf-8")

    srcs = spec.get("sources", [])
    if srcrel not in srcs:
        srcs.append(srcrel)
        spec["sources"] = srcs
        _write_mod_spec(proj, spec)

    print(f"added {tag} \"{inst}\" to {proj.name}")
    print(f"  wrote {srcrel}  (inheritFrom-self override — edit the body, then `openwrath mod bake {proj.name}`)")
    print(f"  from  {fp}")
    print()
    print("current definition (copy the field you want to change into the override body):")
    print("\n".join("    " + l for l in body))
    return 0
```

The generated override is exactly the proven first-mod shape: `id="X" inheritFrom="X"` + the base `<Include>` +
an empty body you fill in. We register it in the project's `sources` so `mod bake` picks it up, and we print the
current definition so you can see what's there to change.

> **Note the comment wording** (`"... re-print it any time with \`openwrath inspect {inst}\`"`). The first draft
> said `openwrath inspect {inst} --source`, and that broke — see the gotcha in step 5.

## 4. Register both commands in `main()`

Find `r.set_defaults(func=cmd_mod_revert)` inside `main()` and add the two parsers right after it (these hang off
`mod`, the subparser group, so they become `mod new` / `mod add`):

```python
    n = mod.add_parser("new", parents=[common], help="scaffold a new mod project (mod.toml + src/)")
    n.add_argument("project", help="path to create for the mod project")
    n.add_argument("--target", help="installed mod to bake into (e.g. SecondIsomer); can be set later in mod.toml")
    n.add_argument("--stream", default="static_mod", help="target stream (default: static_mod)")
    n.add_argument("--name", help="mod name (default: the project dir name)")
    n.set_defaults(func=cmd_mod_new)
    ad = mod.add_parser("add", parents=[common],
                        help="pull an asset into a project as an editable override (from the SDK source)")
    ad.add_argument("project", help="path to the mod project dir (contains mod.toml)")
    ad.add_argument("asset", help="instance name, e.g. GDIMammothTank")
    ad.add_argument("--type", help="restrict to an asset type (disambiguates a shared name)")
    ad.add_argument("--force", action="store_true", help="overwrite an existing override file")
    ad.set_defaults(func=cmd_mod_add)
```

That's the whole feature. Two functions, one registration block.

## 5. Test it

```sh
cd ~/cnc-kw-bab

# 0. does it even parse, and are the commands wired?
python3 -c "import ast; ast.parse(open('modkit/openwrath').read()); print('OK')"
modkit/openwrath mod --help            # should list `new` and `add`

# 1. scaffold a throwaway project
modkit/openwrath mod new ~/cnc-kw-godmod/_test --target SecondIsomer

# 2. pull an asset in
modkit/openwrath mod add ~/cnc-kw-godmod/_test GDIMissileSoldierMissileLauncher
#    -> writes src/GDIMissileSoldierMissileLauncher.xml and prints the current definition
```

Now edit `~/cnc-kw-godmod/_test/src/GDIMissileSoldierMissileLauncher.xml` — replace the
`<!-- e.g. ... -->` line in the body with a real change:

```xml
		<FiringDuration MinSeconds="1.4s" MaxSeconds="1.5s" />
```

Then bake, verify, revert (close the game first — bake refuses while it's running):

```sh
modkit/openwrath mod bake ~/cnc-kw-godmod/_test
#    -> compiling ... (1 overrides) ... (1 replaced) ... ✓ baked + verified intact
modkit/openwrath inspect GDIMissileSoldierMissileLauncher | grep FiringDuration
#    -> <FiringDuration MinSeconds="1.4s" MaxSeconds="1.5s" />
modkit/openwrath mod revert SecondIsomer
```

### The gotcha (you may hit this; here's why)

The *first* version of the generated comment contained `openwrath inspect X --source`. The bake then failed with:

```
xml.etree.ElementTree.ParseError: not well-formed (invalid token): line 15, column 61
```

The cause: **an XML comment cannot contain a double hyphen `--`** — it's reserved for closing the comment, so
`--source` inside `<!-- ... -->` is illegal, and `mod bake`'s XML parse rejected the file before anything was
installed. That's why the comment in step 3 is worded to avoid `--`. Lesson worth keeping: when `mod bake`
throws an XML parse error, it's almost always your override's XML, and the line/column in the error points
straight at it.

## 6. Clean up

```sh
rm -rf ~/cnc-kw-godmod/_test
```

---

## Recap — the pattern you just learned

Adding *any* modkit command is the same three moves:

1. **Write a `cmd_*(args)` function** — read config (`read_config()` / `_need(...)`), do the work, print, return
   an exit code. Reuse existing helpers (`_find_toplevel_block`, `read_config`, …) instead of reinventing.
2. **Register it in `main()`** — `add_parser(...)` + its arguments + `.set_defaults(func=...)`. Subcommands of an
   existing group (like `mod`) hang off that group's subparser.
3. **Test the real path** — syntax check → `--help` → run it → (for anything that bakes) bake / verify / revert on
   a throwaway project.

That's the muscle memory. The next feature on the roadmap — `mod check`, `mod package` — is the same shape, just a
different body. Now the plumbing is boring and you can spend your attention on the interesting part.
