# SteelFlow 3D manualQa

Verdict: **PASS** for the assigned frontend and browser scope. Verified on macOS ARM64 in Google Chrome, 2026-10-24 14:56 KST. No ULW loop plan exists, so the caller's evidence directory `docs/evidence` is used.

Final command `npm run test:e2e`: **10 passed, 0 failed, 0 skipped, 0 flaky**, 64.501 seconds. Every scenario captured an empty uncaught-browser-errors array. Actual backend and frontend processes were launched on `127.0.0.1:8001` and `127.0.0.1:5174`, using a fresh temporary SQLite file. The operator's port 8000 database was not used. Default browser viewport was 1440×1000; mobile was 390×844.

`npm test -- --reporter=json --outputFile=docs/evidence/frontend-tests.json`: **5 passed**, Vitest 5.0.5. The three store cases test stale-response ordering, outage recovery, and duplicate-command protection. The two React Testing Library cases exercise coil → shipment → order navigation and location/clear-selection interaction.

Criterion references: AC1 local startup; AC2 rendered 3D, orbit and selection; AC3 accurate coil relationships; AC4 three distinct deterministic scenarios; AC5 reproducible reset; AC7 no uncaught browser errors; AC8 usable without AI; F3 searchable orders/timeline; F8 simulation controls; F9 accessible 2D fallback. Backend mass-balance and audit invariants are covered by the separate backend test report, outside this assigned browser/frontend matrix.

## surfaceEvidence

Each S01–S10 invocation below ran as part of the final `npm run test:e2e`, without retries. The referenced test title uniquely identifies the actual scenario within `tests/demo.spec.ts`.

| scenario id | criterion reference | surface | exact invocation | verdict | artifactRefs |
| --- | --- | --- | --- | --- | --- |
| S01 | AC1, AC2, AC3, AC7 | Chrome 3D canvas | `npm run test:e2e` → `3D factory renders, orbit and zoom respond, and no browser exception occurs`; clear selection, hover/click visible yard coil C-1006, verify inspector, drag orbit and wheel zoom | PASS | R-browser, T01, I01 |
| S02 | F3, AC7 | Chrome orders search | `npm run test:e2e` → `search finds a customer order and empty search is explained`; search Northstar, search nonexistent ID, clear | PASS | R-browser, T02, I02 |
| S03 | AC3, F3, F9 | Chrome 2D inventory and inspector | `npm run test:e2e` → `accessible inventory selection exposes the exact coil relationships`; select C-1005, compare detail with typed live API, follow shipment timeline then order | PASS | R-browser, T03, I03 |
| S04 | AC4, AC5 | Chrome scenario controls plus live responses | `npm run test:e2e` → `three scenarios differ at the same tick and reset reproduces each baseline`; all three scenarios advanced to tick 8, reset, replay to tick 8 | PASS | R-browser, T04, I04, I05, I06 |
| S05 | F8, AC7 | Chrome and backend clock | `npm run test:e2e` → `play, speed and pause are owned by the backend and continue without a page`; select 4×, play, close page, observe tick advance, reopen, pause, confirm stable tick | PASS | R-browser, T05, I07 |
| S06 | F9, AC7 | Chrome 390×844 | `npm run test:e2e` → `mobile 2D fallback remains navigable without horizontal page overflow`; select C-1001, verify lot; measured document width 390 = viewport width 390 | PASS | R-browser, T06, I08 |
| S07 | AC1, AC7 | Chrome with blocked API network | `npm run test:e2e` → `backend unavailable state is explicit and retry restores the live demo`; abort `/api/v1/**`, reload, verify warning, restore network, Retry | PASS | R-browser, T07, I09 |
| S08 | AC8 | Chrome, real local rules and network log | `npm run test:e2e` → `disabled AI requires no provider request and core recovery rules remain available`; RECOVERY works with enabled=false/available=false and no external requests | PASS | R-browser, T08 |
| S09 | AC7, F9 | Chrome WebGL loss | `npm run test:e2e` → `WebGL context loss leaves core inventory and controls usable`; real `WEBGL_lose_context.loseContext()`, click fallback Open 2D inventory, advance simulation | PASS | R-browser, T09, I10 |
| S10 | AC2–5, AC7–8, F3, F8–9 | Chrome recorded operator route | `npm run test:e2e` → `operator demo recording follows the complete synthetic recovery narrative`; coil inspection, 2D, Delay, Recovery, play/pause, events and reset | PASS | R-browser, T10, V01, V02, I11 |
| U01 | AC7, F8 | Vitest/RTL | `npm test -- --reporter=json --outputFile=docs/evidence/frontend-tests.json` | PASS | R-unit |

Reset comparisons intentionally exclude audit run IDs while comparing orders, lots, coils, inventory, shipments, assignments, KPIs and risks. All scenario paths are driven through real UI controls and validated against actual backend responses.

## adversarialCases

| scenario id | criterion reference | adversarial class | expected behavior | verdict | artifactRefs |
| --- | --- | --- | --- | --- | --- |
| A01 | AC7, F8 | stale asynchronous response | Late polling response cannot replace the result of a completed simulation command | PASS | R-unit |
| A02 | F8 | repeated mutation | A second command during a pending command does not send another mutation | PASS | R-unit |
| A03 | AC7 | backend outage and recovery | Retain last confirmed snapshot in store, expose outage, recover on retry | PASS | R-unit, T07 |
| A04 | AC7, F9 | unavailable WebGL context | Explicit fallback and usable 2D/step controls without uncaught exception | PASS | T09, I10 |
| A05 | F9 | narrow viewport | Inventory remains operable and page does not overflow horizontally | PASS | T06, I08 |
| A06 | AC8 | unavailable optional AI | Disabled/default unavailable provider causes no external request; recovery rules remain usable | PASS | T08 |
| A07 | F3 | unmatched search input | Clear empty result and recovery when input cleared | PASS | T02, I02 |
| A08 | F8 | browser departure | Authoritative simulation continues after the page closes and can be paused after reopening | PASS | T05 |
| A09 | scope | real ERP operation | not_applicable: this synthetic local demo contains no real ERP integration or operational command path | not_applicable | R-browser |

## artifactRefs

Paths are relative to the repository root. All PASS references were verified to point to non-empty artifacts.

| id | kind | description | path |
| --- | --- | --- | --- |
| R-browser | test report | Final 10/10 result, exact timings, empty error arrays, mobile measurements | `docs/evidence/playwright-results.json` |
| R-unit | test report | Final 5/5 Vitest/RTL result | `docs/evidence/frontend-tests.json` |
| T01 | browser action trace | Render, hover, mesh selection, orbit and zoom | `docs/evidence/traces/demo-3D-factory-renders-or-58e54-no-browser-exception-occurs.zip` |
| T02 | browser action trace | Search and empty state | `docs/evidence/traces/demo-search-finds-a-custom-d163c-d-empty-search-is-explained.zip` |
| T03 | browser action trace | Linked coil detail and timeline | `docs/evidence/traces/demo-accessible-inventory--be32b-he-exact-coil-relationships.zip` |
| T04 | browser action trace | All scenario/reset/replay comparisons | `docs/evidence/traces/demo-three-scenarios-diffe-5c16d-et-reproduces-each-baseline.zip` |
| T05 | browser action trace | Backend-owned clock with page closed | `docs/evidence/traces/demo-play-speed-and-pause--09334-and-continue-without-a-page.zip` |
| T06 | browser action trace | Mobile viewport and layout measurement | `docs/evidence/traces/demo-mobile-2D-fallback-re-1517d-ut-horizontal-page-overflow.zip` |
| T07 | browser action trace | Connection failure and recovery | `docs/evidence/traces/demo-backend-unavailable-s-65fd4-etry-restores-the-live-demo.zip` |
| T08 | browser action trace | AI-disabled recovery and request observation | `docs/evidence/traces/demo-disabled-AI-requires--9e709-very-rules-remain-available.zip` |
| T09 | browser action trace | Real context loss and 2D fallback | `docs/evidence/traces/demo-WebGL-context-loss-le-389ae-ventory-and-controls-usable.zip` |
| T10 | browser action trace | Complete operator narrative | `docs/evidence/traces/demo-operator-demo-recordi-82da8-ynthetic-recovery-narrative.zip` |
| I01 | screenshot | Rendered overview and C-1006 selected through canvas | `docs/evidence/10-scene-coil-picking.png` |
| I02 | screenshot | Explained empty order search | `docs/evidence/03-search-empty.png` |
| I03 | screenshot | C-1005 current links in 2D inventory | `docs/evidence/04-inventory-coil.png` |
| I04 | screenshot | NORMAL tick 8 | `docs/evidence/05-normal-tick8.png` |
| I05 | screenshot | DELAY tick 8, 2 at-risk orders, 67% outlook | `docs/evidence/05-delay-tick8.png` |
| I06 | screenshot | RECOVERY tick 8 | `docs/evidence/05-recovery-tick8.png` |
| I07 | screenshot | Confirmed paused state | `docs/evidence/06-paused.png` |
| I08 | screenshot | Mobile full-page inventory layout | `docs/evidence/07-mobile-inventory.png` |
| I09 | screenshot | Explicit unavailable-backend state | `docs/evidence/08-backend-unavailable.png` |
| I10 | screenshot | 2D remains usable after WebGL loss | `docs/evidence/09-webgl-fallback.png` |
| I11 | decoded video frame | Verified MP4 frame at 15 seconds, Recovery insight | `docs/evidence/demo-video-frame.png` |
| V01 | video | Primary fallback: 31.000 seconds, 1440×1000, H.264/yuv420p, no audio, faststart, 1,048,203 bytes | `docs/evidence/steelflow-demo.mp4` |
| V02 | video | Original Chrome recording: 31.000 seconds, 1440×1000, VP9, 4,488,478 bytes | `docs/evidence/steelflow-demo.webm` |

Video conversion actually executed: `ffmpeg -y -hide_banner -loglevel error -i docs/evidence/steelflow-demo.webm -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -movflags +faststart -an docs/evidence/steelflow-demo.mp4`. Codec, dimensions, duration and absence of audio were verified with `ffprobe`; a frame at 15 seconds was decoded and visually inspected.

## Resolved findings and limits

Initial setup needed Playwright FFmpeg installation and localhost execution outside the restricted bind sandbox. First real browser run found mobile page overflow and a Drei Html removal exception after WebGL loss. The owners fixed the scrolling container and stable Html portal; final uninstrumented tests passed. Initial failure and diagnostic evidence remains in `docs/evidence/initial-browser-failures/`. A capture-only scroll race occurred during a concurrent source edit; final frozen-source full run passed without retries.

This evidence covers Chromium on this Apple Silicon host, not Safari/Firefox or an exhaustive assistive-technology audit. Visual inspection confirmed the overview, selected coil, delay view, mobile layout and decoded video frame. No product code was changed by the verification agent.
