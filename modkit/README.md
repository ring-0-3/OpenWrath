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
modkit/openwrath init                  # guided setup: detect + confirm bring-your-own paths + write config
modkit/openwrath show                  # print the resolved config and flag anything missing or moved
modkit/openwrath trace <unit>          # walk a unit → weapons → projectiles → effects (what to mod)
modkit/openwrath uses <asset>          # reverse refs: what REFERENCES this asset (spot shared templates)
modkit/openwrath mod new <project>     # scaffold a mod project
modkit/openwrath mod add <project> <asset>  # pull an asset in as an editable override
modkit/openwrath mod check <project>   # pre-flight: dangling refs / unknown fields / schema drift (file:line)
modkit/openwrath mod bake <project>    # compile overrides + splice into the target stream + install
modkit/openwrath mod build-local <project>  # assemble a COMPLETE loadable static_mod overlay (LOCAL-ONLY)
modkit/openwrath mod activate <name>   # switch a built overlay on (backed-up, reversible master-SkuDef swap)
modkit/openwrath mod deactivate <name> # switch it off again
modkit/openwrath mod package <project> # build the zero-EA overlay DIFF (shareable via assemble-at-install)
modkit/openwrath mod revert <target>   # restore a target's big from the last openwrath backup
# Loadable base-game override mod on retail 1.3 is SOLVED — the proven recipe + builder: docs/findings/0017,
# modkit/lib/build_overlay.py (sparse differential + low-LOD twin + worldbuilder companion + 3 .version redirects).
```

### Edit a unit's texture / view a model in Blender

```sh
modkit/openwrath blender install              # symlink the add-on into Blender (then enable it in Preferences)
modkit/openwrath blender view <container>     # decode a shipped model + its textures and open it in Blender
modkit/openwrath texture override <project> --record <R> --image skin.png
                                              # encode a format-matched DDS + author a <Texture><Payload> override
modkit/openwrath texture override <project> --record <R> --solid FF00FF   # no encoder? a solid-colour smoke test
# then: mod build-local <project> --install → mod activate <name> → launch KW.  See the tutorial:
#   docs/tutorials/edit-a-unit-texture-in-blender.md
```

Texture **editing** is the **§4 frontier — stated-tier, never byte-exact** (EA's DXT compressor isn't
bit-reproducible); the in-game render is the oracle. The overlay it builds is **LOCAL-ONLY** and **not** inherently
C&C-Online/replay-safe (a record overlay changes stream identity). DDS encoding uses an **external** encoder you
install (`nvcompress` recommended), never a hand-rolled compressor. The reliable route is a `Texture` **record
overlay** (findings 0030/0031) — the loose-file `add-search-path` route does **not** work for record-backed unit
skins on retail 1.3 (finding 0029).

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
- [x] `mod new` / `mod add <asset>` — scaffold a project and pull an asset in as an editable override
      (from the SDK source, so it reads cleanly even for types the decompiler can't walk from the stream),
      closing the loop: `trace` → `add` → edit a value → `bake`. `mod add` also **warns at add time** if the
      asset's type is schema-drifted in the target stream, so you learn it then rather than at bake time.
- ✅ **Loadable base-game override mod — SOLVED (`docs/findings/0017`).** A tiny overlay that overrides base
      gameplay on **retail 1.3** was verified **in-game** (a WeaponTemplate's fire-rate / ClipSize / AttackRange all
      applied, no crash). Recipe: a **sparse differential** (complete entry list, data only for your edits, `\x02`
      defer to `static_common_2`) + **low-LOD twin** (`static_l_mod`→`static_mod`) + **WorldBuilder companion**
      (`worldbuilder_mod`) + **three `.version` redirect files** (`_mod\n`) + **the base's max-chunk header kept**
      (the final crash) + unique per-stream checksum. Builder codified + verified byte-exact:
      `modkit/lib/build_overlay.py` (+ `retag_checksum.py`). ⚠ Only **one** overlay owns the static family, so two
      overlay mods are mutually exclusive — combine their diffs into one overlay to stack them.
- [~] `mod package` — builds the **zero-EA overlay diff** (only your declared overrides; a hard gate refuses any
      undeclared/EA asset; sliced `inheritFrom` bases carry their `<Defines>` macro context; fsync +
      integrity-verified — `docs/findings/0015`, `0007`). **Shareable deliverable (go-forward):** the strict zero-EA
      diff **+ a bundled recipient-side assembler** that rebuilds the full overlay (per `0017`) from the recipient's
      **own** `static_common_2`/`worldbuilder_2` — ships *nothing* EA-derived. A full ~6 MB **drop-in** is possible
      but **LOCAL-ONLY** (carries EA-derived entry-list metadata), never presented as shareable. Design:
      `docs/design/diff-plus-assemble-at-install.md`.
- [x] `mod check` — pre-flight validation: **dangling references** and **unknown fields / schema errors** with
      `file:line` messages, plus per-type **schema drift** vs the target. Runs **automatically before a bake**
      (skip with `--no-check`), or on its own: `openwrath mod check <project>`. Dangling-ref severity is
      **scope-driven**: a missing ref to a type OpenWrath *models* (lives fully in the gameplay streams the check
      loads) is an **error**; a ref to an unmodeled type (Texture / W3D / audio, whose streams are outside the
      check's reference scope) is an **unverifiable warning** — so it never false-aborts on runtime art imports,
      and *self-heals* (those refs promote to errors automatically once their types are modeled).
- [x] `uses` — reverse reference walk (what REFERENCES an asset), so you spot shared templates before editing one.
- [x] `mod build-local` — assemble a **COMPLETE, loadable `static_mod` overlay** locally from the running patch's
      overlay + your overrides (the `0017` complete-entry-list assembler; **LOCAL-ONLY**, never shareable). Auto-orders
      forward `ProjectileNugget` refs so projectile mods just work (`docs/findings/0011`); supports a `[strings]`
      table for custom unit names/tooltips without a CSF compiler (`modkit/lib/csf.py`).
- [x] `mod activate` / `deactivate` — reversible, backed-up (`.openwrath-orig`), idempotent master-SkuDef swap, with
      online-safety + `0017` mutual-exclusivity + game-running guards. Closes the edit→build→**run** loop.
- ✅ **Edit a unit's texture → in-game (DONE, confirmed in-game — `docs/findings/0029`/`0030`/`0031`).**
      `texture override` reads a shipped `Texture` record's format, encodes a **format-matched** DDS (via an external
      encoder — `nvcompress`/`nvtt_export`/`texconv`, never hand-rolled; `--solid` is a no-encoder smoke test), and
      authors a `<Texture><Payload>` override; `texture encode` is the standalone step. Delivered as a **record
      overlay** (`build-local`) — EA's own method; the loose-file `add-search-path` route does **not** work for
      record-backed unit skins on 1.3 (`0029`). **Stated-tier, never byte-exact; LOCAL-ONLY; not online-safe.**
- ✅ **Blender integration — viewer + byte-exact exporter (DONE — `docs/findings/0026`/`0028`).** `blender install`
      (symlink the add-on), `blender model` / `view` (decode a model + its textures and open it). The add-on is a
      **thin front-end to the CLI** — no forked format logic. Imports geometry + skeleton + real textures; **exports**
      an *unmodified* model back **byte-exact** (gated by `tools/blender-roundtrip-gate.sh`), edited content stated-tier.
- [ ] base-game-target guard — default to mod targets; require an explicit flag + warning to splice base-game
      streams (avoids C&C:Online / replay desync).
- [ ] installable command — a `pipx`-installable `openwrath` that locates or fetches the compiler, so setup is
      "install + init" rather than "clone + build".
