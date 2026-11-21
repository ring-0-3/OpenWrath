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
modkit/openwrath detect              # auto-discover your KW install / prefix / mods / SDK; writes the config
modkit/openwrath show                # print the resolved config and flag anything missing or moved
modkit/openwrath mod bake <project>  # compile a mod's overrides + splice them into its target stream + install
modkit/openwrath mod revert <target> # restore a target's big from the last openwrath backup
```

`detect` finds your Steam (Flatpak or native), the KW install + Proton prefix (even on other
drives — it reads `libraryfolders.vdf`), your Mods folder, and the active launcher SkuDef.
Bring-your-own paths (your SDK, the master StringHashes table) are yours to point it at. A *mod*
is bring-your-own: the modkit is the capability and bundles no mod content or game data.

See `config.example.toml` for the full schema.

## Status / roadmap

- [x] `detect` / `show` — environment discovery + config
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
- [ ] `trace` — walk a unit → weapons → projectiles → effects so you know *what asset to mod*.
- [ ] `stringhashes` — (re)generate the master StringHashes table from your own SDK.
