# 0026 — Blender read-only model importer (viewer): rigid exact, skinned via channel-0 bind, stated-tier

**Status:** Verified · 2026-11-26

> About **our own tooling** — a Blender add-on (`blender/openwrath_import/`) that is a *thin front-end to the
> OpenWrath CLI*, plus `openwrath blender` modkit commands. It is the first **viewer** tier, built on the
> semantic mesh decode + re-pack gate ([0025](0025-w3dmesh-repack-equality-gate.md)). It reimplements **no** W3D
> format logic (CLAUDE.md invariant 3 at ecosystem scale): every byte⇄XML conversion stays in `bab-decompile`;
> the add-on only translates the decompiled authoring XML into Blender datablocks. Shipped-model placement has
> **no byte oracle**, so this milestone is **stated-tier** — the decidable anchors are the geometry
> self-consistency gate (decode is bit-exact to the CLI), rigid placement, and symmetry.

## What was built

- **`blender/openwrath_import/`** — `w3x_xml.py` (the one source of XML-shape knowledge, pure stdlib, no `bpy`),
  `cli.py` (shells out to `bab-decompile` via the single `build_decode_argv`), `scene_builder.py` (XML → mesh /
  armature / bindings — the only `bpy` module), `__init__.py` (File > Import operator). A `W3DContainer` imports
  the whole model (hierarchy → armature, referenced meshes bound/placed); a `W3DHierarchy` or `W3DMesh` imports
  its part alone.
- **`openwrath blender install | model | view`** (modkit, config-driven) — `install` symlinks the add-on into
  Blender's addons dir (kills the hand-built/dangling-symlink error class); `model`/`view` decode a container +
  its refs from the user's own install (reusing `bigextract`/`refpack`/`ensure_stream_cache`) into a gitignored
  local dir. All three + `make_fixture.sh` route through the **one** `build_decode_argv` — no forked decode
  invocation (invariant 3).

## The decidable core: scene assembly = bind-pose application (no byte oracle, so proven by other means)

A shipped W3D sub-mesh's vertices are **not** in model space — they are authored relative to a bone, and the engine
draws them at the bind pose. The importer reconstructs that bind pose:

- **Rigid sub-object (no influences): `v_model = worlds[bone] @ v`** — the full bind world matrix (translation +
  rotation; all shipped pivot matrices are det +1, pure rigid). **Proven exact**: the container gate asserts each
  rigid part's world origin equals its pivot's world-matrix translation (Redeemer: 32/32 rigid parts, error 0.0),
  and the collision-hull extents cross-check.
- **Skinned sub-object: `v_model = worlds[channel-0 bone] @ v`** — see below.

`worlds` is one shared accumulator (`scene_builder._pivot_world_matrices`), reused by the importer **and** the
gate (no re-derivation).

## The skinned-placement bug and its fix (channel-0 reference bone)

**The mechanism (do not re-derive):** a skinned vertex's **position** is stored in its **channel-0** influence's
bone frame (the *first* `<BoneInfluences>` slot), **regardless of weight**. The influence **weights are
deformation-only** — they drive live skeletal animation away from the bind pose, not the bind *position*. So at
rest the vertex sits rigidly at `worlds[channel-0] @ v`.

**The bug:** the first implementation placed skinned verts by the **max-weight** bone (and even blended positions
via LBS `Σ w·worlds[b]·v`). For the ~0.5% of verts where channel-0 ≠ max-weight — e.g. the Redeemer leg-1 toe
`[(87, 0.0), (88, 1.0)]` (position lives in bone 87, weight 0; deform is bone 88) — this placed them in the wrong
bone's frame and **tore the 87↔88 seam ~10–15 u**. The tell was **asymmetry on a symmetric model**: leg 1 tore
while legs 2–4 were clean, because only leg 1 carried off-slot verts.

**The fix** (`scene_builder.reference_bone` + `_assemble`): place a skinned vertex by its **channel-0** bone.
Decidably correct, not overfit:
- **Restores 4-fold leg symmetry** on the Redeemer (per-leg worst seam identical across all four quadrants) — a
  symmetric model reconstructing symmetrically is the proof.
- **Strictly better-or-equal**: of the 0.5% of verts where it differs from max-weight, **zero are worse**; for the
  other ~99.5% (channel-0 == max-weight) it is identical, so it cannot regress the common case.
- **Reduces to the proven rigid case** at a single influence (channel-0 = the only bone).
- Verified across `REDEEMER_BOTTOM`/`REDEEMER_TOP`, `NU_BUGGY`, `NUVENOM`.

**Residual (honest, stated-tier):** a genuine soft-blend vertex (e.g. one `0.73/0.27` vert on `REDEEMER_TOP`) has
**no single correct static position** — it is defined by the live-deforming rig. Channel-0 places it at its bind
home; the small offset is reported, never hidden. That is the live-deform tier, out of scope for a static viewer.

## Closing the gate coverage gap (why the first "verified" was wrong)

The skinned path was initially reported "verified" on a **centroid** placement check — which cannot see a *local*
seam tear (a few flung verts barely move the centroid). A human inspecting the real Redeemer foot from the right
angle found the tear the gate had greenlit. The gate now has a **per-vertex seam-continuity** check
(`tools`/`test_self_consistency.py`): for each skinned vertex, if a *different* influencing bone would place it
≥`SEAM_FACTOR`(3×) and > a few units closer to its mesh-neighbours, the reference choice is wrong and the seam
tears. Tiered honestly — a gross improvable gap (> `SEAM_FAIL` = 5 u) **FAILS**; a small soft-blend residual is
**bucketed + reported** (never widen `SEAM_FAIL` to hide a tear). Verified it **FAILS** the old max-weight rule
(gap 10.66) and **passes** channel-0 (gap 2.54, 1 residual vert).

**Methodology lessons (→ `docs/design/verification-blind-spots.md`):**
- A **centroid/aggregate** placement check is blind to **local** per-vertex defects — the same coverage §1 trap as
  an unsampled instance, inside a single asset. A "scene assembles" aggregate is not "every vertex is right."
- A **non-scale-invariant metric** (worst distance-from-neighbour) is confounded by a global scale change — it
  made a uniform-scale hypothesis look worse than it was and sent review down a dead end (`FixupMatrix` red
  herring: bone 98's anisotropic fixup *correlated* with a bent prong but was not causal; the cause was
  channel-0 ≠ max-weight). Judge scene-assembly fixes by **shape/symmetry** and the in-game reference, not
  absolute distance.

## Boundaries honored

- **No W3D format logic in Python** — all bytes via the CLI; the skin formula is scene assembly over the decoded
  influences + hierarchy (invariant 3, ecosystem scale).
- **Zero-EA** — decoded model XML goes to a gitignored `blender/tests/fixtures/local/`; only hand-authored
  synthetic fixtures (a unit cube + 2-bone skel) are committed. No `.bin`/`.manifest`/model-XML in git.
- **Stated-tier, never byte-exact** — README + [COVERAGE](../reference/COVERAGE.md) mark the viewer stated-tier;
  decode geometry is bit-exact to the CLI, scene assembly is stated (rigid exact, skinned channel-0 with the seam
  residual). Collision boxes default **off**, in their own hideable `<model>_Collision` collection.

## Unverified / next

- Live skeletal **deformation / animation** (the soft-blend residual's proper home) — `W3DAnimation` is still a
  compressed-channel byte pass-through, not keyframes; needs a semantic channel decode.
- Materials (`FXShaderMaterial`) and textures (DDS display) — not imported (v1 shows untextured, flagged in the
  import report).
- The **exporter** (staging step 3, gated on the 0025 re-pack gate) — authored geometry is stated-tier.
- Only `static_common`-sourced models sampled; big-endian/Xenon untouched.
