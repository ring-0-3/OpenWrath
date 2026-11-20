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
modkit/openwrath detect     # auto-discover your KW install / prefix / mods / SDK; writes the config
modkit/openwrath show       # print the resolved config and flag anything missing or moved
```

`detect` finds your Steam (Flatpak or native), the KW install + Proton prefix (even on other
drives — it reads `libraryfolders.vdf`), your Mods folder, and the active launcher SkuDef.
Bring-your-own paths (your SDK, the master StringHashes table) are yours to point it at.

See `config.example.toml` for the full schema.

## Status / roadmap

- [x] `detect` / `show` — environment discovery + config
- [ ] `bake` — compile a mod's XML overrides and splice them into a target stream (base game or
      an existing mod), repack the big, auto-backup, install. Wraps the whole hand-run pipeline.
- [ ] `trace` — walk a unit → weapons → projectiles → effects so you know *what asset to mod*.
- [ ] `stringhashes` — (re)generate the master StringHashes table from your own SDK.
