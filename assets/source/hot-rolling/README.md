# Original hot-rolling miniatures

T20 owns exactly the 21 `existing_bindings` variants whose `allowed_families` includes `hot-rolling` (21 placements, 12 kinds). `recipe.json` records every key; no CUT-SLAB, stainless or titanium variants are borrowed.

All models, PBR finishes and geometry are directly authored. The reference artwork A/B/C was viewed before modelling. The warm stone foundation, teal/blue machinery, machined steel and yellow safety details follow that direction. Public process concepts come from the coverage registry and `docs/FACTORY_PROCESS_REFERENCES.md`; dimensions, transmissions and clearances are synthetic, not plant specifications.

Use the pinned executable in `assets/toolchain.json`:

```text
Blender --background --factory-startup --python-exit-code 1 --python scripts/assets/build.py -- --family hot-rolling --out NEW_ROOT --render
node assets/source/hot-rolling/verify.mjs --root NEW_ROOT --stamp
```

The family entry is `assets/source/hot-rolling/build.py`; output roots must be new. It writes the family-local fragment, sources and GLBs. Shared dispatch and top-level manifest installation are separately serialized. Each source `.blend` is editable; three actual geometry LODs retain every node, part, pivot and socket. Cylinder and edge segmentation decrease, never operating meaning.

T61 `mechanical_follower` drives each independently pivoted stand/table/wrapper roller from its canonical numeric scalar, with authored multi-slot Blender tracks in the same driver clip and 73 matching samples. Negative ratios use their actual direction and range. No wall clock, independent animation loop, new server function or material mesh is embedded in a machine GLB.

`tests/fixtures/hot-rolling` uses explicit authorized synthetic T58 samples and one selectable material entity. Wound strip and laid wire ring paths are material geometry. This verifies machinery and contact only; BILLET-to-rod/coil business transformation, production scheduling and the full factory remain T18/T31 and later integration responsibilities. Pause/blocked retain the exact approved sample; the cooling bed transfers to a fixed receiving surface before its empty rack returns.
