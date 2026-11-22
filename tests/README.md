# Tests

One command runs everything:

```sh
tests/run.sh
```

It runs both suites, prints a combined pass/fail/skip summary, and exits nonzero if anything
failed. It needs **neither pytest nor the .NET SDK**, and it passes on a machine with **no EA /
game data**: every test uses synthetic fixtures (fake directory trees and hand-built byte blobs)
inside isolated temp directories with a throwaway `$HOME`. Your real `tools/dev-env.local`, your
real `~/.config/openwrath/config.toml`, and your SDK data are never read or written.

## What runs

### 1. Python modkit suite — `modkit/tests/test_openwrath.py`
Covers the `openwrath` CLI: config read/write round-trip, Steam/Proton install + mods detection
(native **and** WSL, including `libraryfolders.vdf` drive translation), `init` (non-interactive +
idempotent), the StringHashes collect/merge/write logic, RefPack decompression against a
byte-faithful stream, and `extract-manifests` against a synthetic BIG4 archive. Runs as a plain
script (no pytest needed); it is also pytest-compatible if you have it.

### 2. Shell suite — `tests/test_shell.sh`
Covers the onboarding scripts `tools/setup.sh` and `tools/dev-env.sh`, always against **copies**
in a throwaway repo tree so the real `tools/dev-env.local` is never touched:

- `bash -n` **and** `zsh -n` syntax check of both scripts.
- `setup.sh --help` exits 0 and prints its usage banner.
- `setup.sh` does not hang on a non-TTY (`</dev/null`) and returns.
- `setup.sh --non-interactive --no-build` detects a synthetic SDK/schema/manifests tree,
  validates it, and writes a correct `dev-env.local` (asserts the literal `$HOME`-folded contents
  **and** that the file re-sources through `dev-env.sh` to the right paths).
- `dev-env.sh` path resolution: env overrides win, the three vars export correctly, and the
  report distinguishes present (`[ok]`) vs missing (`[MISS]`) inputs.
- `dev-env.sh` WSL fallback is **non-destructive**: forcing WSL (via a fake `uname`) with no `/mnt`
  leaves the native `$HOME` defaults intact.
- `dev-env.sh` **and** `setup.sh` WSL pickup: with a fake `/mnt/<drive>/...` SDK tree, they fill
  the data paths from the Windows side. These two assertions run inside a `bwrap` sandbox (because
  the scripts hard-code `/mnt`); see below.

## Excluded from CI (need a real environment)

These are intentionally **skipped**, not failed or faked:

- **`setup.sh`'s real `dotnet build` + round-trip.** The suite always passes `--no-build`, so the
  `dotnet build source/BinaryAssetBuilder.sln` step and the `tools/roundtrip.sh GlobalData/Armor.xml`
  smoke test never run here. They need the .NET SDK **and** real SDK data. Run `tools/setup.sh`
  yourself to exercise them.
- **`gen-stringhashes` actually compiling.** The Python suite tests the collect/merge/write logic
  around the compiler; the real compile needs the EA Mod SDK + .NET and is not run.
- **`extract-manifests` against a real `.big`.** Tested against a synthetic BIG4 + literal RefPack
  stream only; no real game archive is read.
- **The WSL `/mnt` pickup assertions when `bwrap` is unavailable.** `dev-env.sh`/`setup.sh` hard-code
  `/mnt`, so the "picks up Windows-side paths" assertions bind a fake `/mnt` with `bubblewrap`. If
  `bwrap` isn't installed, those two shell assertions `SKIP` (the non-destructive WSL fallback is
  still proven without it, and the Python suite covers the WSL detection logic in full).
