# Original transport miniature source

Run the pinned Blender executable through `scripts/assets/build.py --family transport --out NEW_ROOT --only truck-flatbed,crane-yard,receiving-cradle`. Outputs never overwrite an occupied root. Source recipes, exact contracts, .blend, three decreasing mesh LODs, provenance and exhaustive solid-node inventory accompany the exported GLBs.

This is currently a source-authoring candidate. `manifest.json` contains existing registered variants; `manifest-candidate.json` retains every authored variant including unregistered candidates. An unregistered candidate is not admitted by a generic substitute. `solid-inventory.json` is a proposed exhaustive classification tied to exact GLBs and requires independent review; it is not a trusted pass certificate.

All real equipment meshes are solids. The four coordinate diagnostic meshes are the sole proposed nonphysical exclusions, with exact names/reasons. No cab, grille, guard, hub, wheel, bolt or load deck is excluded. Compound boxes use actual evaluated vertex bounds, with only 0.02mm numeric enclosure allowance. Steering/rolling composition, dynamic wheel envelopes and actual full handling/departure paths need separate finite physical proof before admission.

Public function source for the eye-horizontal C-hook: https://www.caldwellinc.com/products/mill-duty/coil-handling/model-282 (accessed2026-10-30). No reference meshes/images/textures were downloaded or copied. All dimensions/materials are original synthetic design. C-hook bore contact differs from original material-bottom support datum; the source does not claim that unresolved custody transfer is supported by the current runtime.
