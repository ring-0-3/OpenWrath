# 0007 — A `.big` repack must be fsynced + integrity-verified before install, or a truncated archive ships silently

**Status:** Verified (bug found + fixed) · 2026-11-20

## Context

Baking a mod ends by repacking the mod's `.big` archive (original entries copied verbatim, the modded stream
files swapped in) and copying it over the installed one. A bake reported success, the modded assets verified
correct immediately after — and then the install was found **corrupt**: the live `.big` was physically
**922 MB** when its own file table said it should be **1863 MB**. Truncated at ~half.

## Finding — three compounding failures

1. **The repack's bytes were only in the page cache, not durably on disk.** `big_replace.py` wrote the new
   archive but never `flush()` + `os.fsync()`-ed it. The immediate post-bake verification *passed* because the
   OS served the full data from cache; once the cache was evicted, reads hit a short file on disk.
2. **The bake ignored the repack's exit code.** `subprocess.run([... big_replace ...])` was called without
   checking `returncode`; the next line only tested `if not newbig.exists()`. A repack that failed *after*
   writing a partial file would leave that partial on disk and the bake would sail on and install it.
3. **Nothing verified the installed archive.** A BIG4 is complete iff no file-table entry's data extends past
   the end of the file — a cheap header-only check. It wasn't being done, so a truncated big was trusted.

The file table (written first, at the archive head) was intact and described the full 1863 MB layout; only the
data payload past 922 MB was missing. That's the signature of a short/partial write, not a bad index — which is
exactly why a naive "does the file open / does the header parse" check would have called it fine.

## Evidence

Diagnosed by comparing the live big's table max-offset (`1863303318`) to its actual size (`922943488`) —
table said 1863 MB, disk had 922 MB. The backup (made before the first-ever bake) checked out complete
(`maxEnd == fileSize`) and restored cleanly. Fix landed in `modkit/lib/big_replace.py` (fsync + size assert)
and `modkit/openwrath` (exit-code check, post-install integrity verify, auto-rollback).

## How to apply — the durability/verify discipline for any archive write

- **fsync before claiming success.** For any file another step will immediately trust, `flush()` + `os.fsync()`
  before returning. "The bytes are written" (to cache) ≠ "the bytes are on disk."
- **Never trust an exit code you didn't check.** A tool that writes incrementally and fails late leaves a
  partial artifact; `returncode != 0` must abort the caller before that partial is used.
- **Verify the artifact structurally before install, and re-verify what landed.** For a BIG4: assert no entry's
  `offset + size` exceeds the file size. Do it on the freshly-repacked file *and* again after copying it into
  place.
- **Keep a known-good backup and auto-roll-back.** If the post-install check fails, restore the backup instead
  of leaving a corrupt install. Refuse to bake *from* a corrupt base, and refuse to restore *from* a corrupt
  backup. (A single backup slot that is never overwritten preserves the last-known-good — that is what made
  recovery possible here.)
- **A passing check right after writing can be a cache artifact.** If correctness matters, verify by a path
  that forces a real disk read (or after fsync), not one the cache can answer.

## See also

- [0006](0006-new-assets-need-stream-insert.md) — the insert feature whose larger repack surfaced this.
- `modkit/lib/big_replace.py`, `modkit/openwrath` (`big_is_complete`, the bake install/verify/rollback block).
