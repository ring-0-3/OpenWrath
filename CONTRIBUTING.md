# Contributing

Thanks for wanting to help open up Kane's Wrath modding. A few things make contributing here smooth — and keep
the project honest and legal.

## Setup

See **[SETUP.md](SETUP.md)**. In short: install the .NET SDK, supply your own game data / SDK schemas (this
repo ships none — bring-your-own), `source tools/dev-env.sh`, and build.

## How correctness is proven (please don't skip this)

The project's core promise is that the decompiler is **lossless**, and that's verified mechanically, not
claimed:

- **`tools/roundtrip.sh <source.xml>`** (closed-loop) — compile → decompile → recompile → assert the bytes are
  identical to what our compiler produced. Proves the decompiler is a faithful inverse of the compiler. A change
  is only "correct" if this stays green.
- **`tools/roundtrip.sh --from-binary <stream.manifest>`** (ground-truth) — decompile a *shipped* stream,
  recompile, and byte-compare to the bytes the game actually ships, bucketed per type. This is the stronger
  measure and the one the coverage matrix reports.
- **`tools/corpus-roundtrip.sh`** + **`tools/coverage-report.py`** — run the closed-loop check across many source
  files as a self-consistency monitor. The authoritative fidelity numbers come from the ground-truth gate; see
  [docs/reference/COVERAGE.md](docs/reference/COVERAGE.md) for the per-type matrix, method, and sampled instances.

If you touch the decompiler, run the harness on the types you affect and keep the regression set byte-exact
(ArmorTemplate, WeaponTemplate, LocomotorTemplate, AttributeModifier, and the construction-yard GameObjects
closed-loop). **Never** modify the compile side (`Relo/`, `Marshaler.*.cs`, `SageBinaryData`, `Core`) to make a
decompiler test pass — the compiler is the byte-exact oracle; changing it invalidates the measurement.

## CI

`.github/workflows/ci.yml` builds the compiler and decompiler on every push/PR. It deliberately does **not**
run the round-trip harness: that needs real game data, which can't live in CI or in this repo. Run the harness
locally (or on a self-hosted runner with your own data) as the data-dependent gate.

## The StringHashes gap

A few values are stored only as one-way hashes (module `id` tags, `StringHash` fields). To recover the
originals during decompilation, build a master table with **`tools/build-stringhashes.sh <cache-dir> <files…>`**
and pass `--stringhashes <cache-dir>/StringHashes.xml` to `bab-decompile`. Without it, those render as hex
(binary-safe but not human-readable).

## Scope & legality

This is interoperability tooling. It ships **no EA content** and must stay that way — don't commit game assets,
SDK schemas, `.big`/stream files, or binaries. Keep machine-specific paths in the git-ignored
`tools/dev-env.local`. Art/asset *compilers* (textures, meshes, audio) are a separate planned effort — see
[ROADMAP.md](ROADMAP.md).
