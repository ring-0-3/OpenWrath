# openwrath modkit

A developer-facing CLI for making Kane's Wrath mods with the OpenWrath toolchain — so modding
is a few commands, not tribal knowledge of where everything lives and which byte goes where.

It's a thin, config-driven layer over the OpenWrath compiler/decompiler and the stream-surgery
tools. It does not replace them; it drives them.

## Principles

- **No hardcoded paths.** Nothing about any one machine is baked in. Your setup is discovered
  (`openwrath detect`) or read from a per-user config. The only literals in the code are facts
  about the *game* (its Steam appid, its install-folder name) — never a personal path.
- **Ships zero game data.** openwrath operates on your own install and SDK, which you own. It
  bundles no EA assets, schemas, or streams.
- **Config lives outside any repo** — `~/.config/openwrath/config.toml` (XDG) — so there is
  nothing to gitignore and no path ever lands in version control.

## Quickstart

```sh
modkit/openwrath init                # guided setup: detect + confirm bring-your-own paths + write config
modkit/openwrath show                # print the resolved config and flag anything missing or moved
modkit/openwrath mod bake <project>  # compile a mod's overrides + splice them into its target stream + install
modkit/openwrath mod revert <target> # restore a target's big from the last openwrath backup
```

**`init` is the one command to start with.** It runs auto-detection, then for each bring-your-own
path it searches the usual places, offers what it finds (just press Enter to accept), validates
whatever you type, and — if an item is missing but openwrath can produce it — offers to run the
generator (`gen-stringhashes`, `extract-manifests`) on the spot. It is idempotent: re-running keeps
your good values. For CI or scripts, `openwrath init --non-interactive` (also auto-selected when
stdin is not a TTY) accepts every detected/validated default without prompting and never blocks.

`detect` is the non-interactive discovery pass on its own: it finds your Steam (Flatpak, native, or
Windows-side **under WSL**), the KW install + Proton prefix (even on other drives — it reads
`libraryfolders.vdf`), your Mods folder, and the active launcher SkuDef. Bring-your-own paths (your
SDK, the master StringHashes table) are yours to point it at. A *mod* is bring-your-own: the modkit
is the capability and bundles no mod content or game data.

### Producing the bring-your-own data

Two of the bring-your-own inputs can be generated from material you already own:

```sh
modkit/openwrath gen-stringhashes            # compile your SDK with -scd and merge every emitted
                                             #   StringHashes.xml into one master table (XDG data dir)
modkit/openwrath extract-manifests           # pull + RefPack-decompress the base-stream manifests
                                             #   (global_common_2 / static_common_2 / global_english_2)
                                             #   out of your installed game's .big archives
```

Both default their output to `$XDG_DATA_HOME/openwrath/` (i.e. `~/.local/share/openwrath/`) and write
the resulting path back into your config. Neither ships any game data — they read only your own
install/SDK. `gen-stringhashes` needs `sdk` + `schema` configured; `extract-manifests` needs the game
install detected. Use `--out` / `--source` to override paths.

### Windows Subsystem for Linux (WSL)

Detection also works when the game is installed on the Windows side and you run openwrath from a WSL
distro. It finds Steam under `/mnt/<drive>/Program Files (x86)/Steam` (and library folders from
`libraryfolders.vdf`, translating `C:\…` paths to `/mnt/c/…`), the install under
`steamapps/common/`, and the Mods folder in the Windows user's Documents
(`/mnt/c/Users/<you>/Documents/…/Mods`). There is no Proton/Wine prefix in this mode — the game is a
native Windows app. Native-Linux (Flatpak/Proton) detection is unchanged.

See `config.example.toml` for the full schema.

## Status / roadmap

- [x] `init` — guided, idempotent setup wizard over `detect` + bring-your-own confirmation/validation;
      `--non-interactive` / non-TTY safe. Offers to run the generators below for missing producible inputs.
- [x] `detect` / `show` — environment discovery + config (Flatpak, native, and **WSL** / Windows-side)
- [x] `gen-stringhashes` — build the master StringHashes.xml from your own SDK (`-scd` compile + union merge).
- [x] `extract-manifests` — extract + RefPack-decompress the base-stream manifests from your installed game.
- [x] `mod bake` — compile a mod's XML overrides and apply them to a target stream (base game or an existing
      mod): assets already in the stream are **replaced** (splice), brand-new assets are **inserted**
      (append-only, existing assets stay byte-identical — see `docs/findings/0006`), then repack the big,
      auto-backup, install. The repack is fsynced and the installed big is integrity-verified, with
      auto-rollback from backup if anything is off (`docs/findings/0007`). Wraps the whole hand-run pipeline.
- [x] `mod revert` — restore a target's big from the last openwrath backup (backup + result both verified).
- [x] `schema` — show a stream's per-type schema fingerprints (TypeHash) and where they **drift** from our
      compiler. A mod stream built against a different schema version carries a different hash for a type;
      INSERTing a new asset of such a type crashes on load, so `mod bake` now **guards** inserts against drift
      (clean abort, nothing installed) and offers `--adopt-schema` to stamp the stream's hash where the drift is
      hash-only. Drift that also changes layout can't be authored with our retail schema. See
      `docs/findings/0010`.
- [x] `trace` — walk a unit → weapons → projectiles → effects (outgoing reference tree; cycle-safe,
      `--depth` / `--type`) so you know *what asset to mod*.
- [ ] `mod new` / `mod add <asset>` — scaffold a project and pull an asset in as an editable override
      (decompiled from the SDK source), closing the loop: `trace` → `add` → edit a value → `bake`.
- [ ] `mod package` — produce a self-contained, shareable mod (its own big + SkuDef) a player can drop into
      `Mods/` and run with no OpenWrath installed.
- [ ] `mod check` — pre-flight validation (dangling references, unknown fields, schema drift) with file/line
      messages, run automatically before a bake.
- [ ] base-game-target guard — default to mod targets; require an explicit flag + warning to splice base-game
      streams (avoids C&C:Online / replay desync).
- [ ] installable command — a `pipx`-installable `openwrath` that locates or fetches the compiler, so setup is
      "install + init" rather than "clone + build".
