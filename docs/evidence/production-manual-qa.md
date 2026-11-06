# manualQa — production

2026-10-24 KST. No ulw-loop plan exists; caller evidence directory `docs/evidence` used. QA ownership: `tests/production.spec.ts` only; no product changes.

**Final verdict: PASS.** Before the equipment correction, full-suite invocation: `npm run test:e2e > docs/evidence/production-full-e2e.log 2>&1` (17 passed; 0 failed/skipped/flaky, 70.2s). After the equipment correction, exact final invocation: `npm run test:e2e -- tests/production.spec.ts > docs/evidence/production-final-e2e.log 2>&1` (8 production scenarios passed; 0 failed/skipped/flaky, 25.6s), plus `npm test > docs/evidence/production-final-unit-tests.log 2>&1` (5 passed). Chrome at http://127.0.0.1:5174 uses a fresh SQLite temp database and local backend 8001, AI disabled. No external operational system or personal data used.

## surfaceEvidence

Each P1–P8 ran as part of the exact final `npm run test:e2e -- tests/production.spec.ts` invocation above. Source line identifies the executable scenario; traces preserve actual browser action sequence.

| scenario id | criterion reference | surface | exact invocation / action sequence | verdict | artifactRefs |
|---|---|---|---|---|---|
| P1 | C1: eight stages + overview return | Chromium UI, 1440×1000 | `tests/production.spec.ts:47; 2D 공정 → each of eight 생산 공정 선택 buttons → 전체 공정` | PASS | T1, S-stage-1 through S-stage-8, A-REPORT |
| P2 | C2: nine routes + correct product branches | Chromium UI, 2D | `tests/production.spec.ts:59; 제품 경로 SLAB/BLOOM/BILLET/HR/CR/GI/GA/EG/HGI; then HGI + 냉연, recover ALL` | PASS | T2, S-route-slab through S-route-hgi, S-incompatible-filter-recovery, A-REPORT |
| P3 | C3: material roles + genealogy + selection | Chromium UI + response data | `tests/production.spec.ts:85; Advance one step ×5; PROD-HR / PROD-CR; step ×1; PROD-CR / PROD-GI; current process → substep` | PASS | T3, D3-tick6-production, S-hr-role-hr, S-hr-role-cr, S-cr-role-cr, S-cr-role-gi, A-REPORT |
| P4 | C4: scenario changes + deterministic reset | Chromium UI + response data | `tests/production.spec.ts:116; NORMAL/DELAY/RECOVERY each step ×6, inspect active work, reset then step ×6 and compare` | PASS | T4, D4-scenario-production-snapshots, S-scenario-normal-tick6, S-scenario-delay-tick6, S-scenario-recovery-tick6, A-REPORT |
| P5 | C5: mobile and authoritative simulation controls | Chromium UI at 390×844 | `tests/production.spec.ts:143; 2D, GA, coating, alloying step, speed4, play → poll tick → pause → wait600ms → step → overview` | PASS | T5, D5-mobile-layout, S-mobile-390, A-REPORT |
| P6 | C6: WebGL fallback preserves core actions | Chromium UI + real WebGL loss | `tests/production.spec.ts:166; canvas WebGL2 WEBGL_lose_context.loseContext(); Korean fallback → 생산 목록 열기; HGI/coating/select/step` | PASS | T6, S-webgl-fallback, A-REPORT |
| P7 | C7: real 3D interaction + workspace stability + local-only | Chromium WebGL canvas and UI | `tests/production.spec.ts:189; click facility at canvas(40%,26%); overview; drag/orbit/wheel; camera reset; detail; logistics/production ×3; capture requests` | PASS | T7, D7-external-requests, S-3d-overview, S-3d-facility-picking, S-3d-orbit, S-3d-detail, A-REPORT |
| P8 | C8: geometry selects the correct equipment operation | Chromium WebGL canvas | `tests/production.spec.ts:229; GA/EG/HGI product selector → coating; actual canvas clicks prep(40%,35%), bath(50%,44%), electrolytic cell(60%,54%)` | PASS | T8, S-equipment-ga-hdg, S-equipment-eg-egl, S-equipment-hgi-pickle, S-equipment-hgi-hdg, A-REPORT |

## adversarialCases

| scenario id | criterion reference | adversarial class | expected behavior | verdict | artifactRefs |
|---|---|---|---|---|---|
| A1 | C2 | incompatible route/filter | HGI has no CRM/cold rolling; empty cold worklist explains route exclusion; ALL restores four cold routes. Bloom/billet skip hot rolling. | PASS | T2, S-route-hgi, S-route-bloom, S-route-billet, S-incompatible-filter-recovery |
| A2 | C3 | same form, different business role | Tick5 HR is sale product, CR target HR is feedstock; tick6 CR is sale product, GI target CR is feedstock; parent chain stays intact. | PASS | T3, D3-tick6-production, S-hr-role-hr, S-hr-role-cr, S-cr-role-cr, S-cr-role-gi |
| A3 | C4 | repeated reset/state contamination | Every scenario replay equals its own tick6 production snapshot; three scenarios differ. | PASS | T4, D4-scenario-production-snapshots |
| A4 | C5 | narrow viewport / paused time | Document width ≤390; stages, material, substeps, controls remain usable; tick does not advance paused and step advances exactly one. | PASS | T5, D5-mobile-layout, S-mobile-390 |
| A5 | C6 | WebGL context loss | Clear fallback appears; 2D navigation, material selection and server stepping remain usable. | PASS | T6, S-webgl-fallback |
| A6 | C7 | repeated workspace mount/unmount | Three logistics/production switches preserve usable headings without uncaught browser errors. | PASS | T7, D7-uncaught-browser-errors |
| A7 | C7 | external network dependency | Reload plus 3D/UI actions issue no external requests; production scope is synthetic in validated world contract. | PASS | T7, D7-external-requests |
| A8 | C8 | visually similar / non-target equipment | GA electrolytic cell selects nothing; GA bath selects HDG-01. EG bath selects nothing; EG cell selects EGL-01. HGI prep selects HGI-PICKLE-01 and bath selects HDG-01. | PASS | T8, S-equipment-ga-hdg, S-equipment-eg-egl, S-equipment-hgi-pickle, S-equipment-hgi-hdg |
| A9 | C1–C8 | authorization / credentials | not_applicable: this local synthetic workspace adds no login, permissions, credential entry, or external writes. | not_applicable | A-REPORT |


## Corrected regression

A subsequent independent review found proportional 3D equipment-to-step mapping could select an unrelated coating operation for GA/EG. The scene owner replaced this with explicit equipment IDs. New browser scenario P8 directly clicks the geometry, verifies matching operations and rejects non-target equipment, and passes with all seven earlier production cases. Previous full report and trace/video artifacts are preserved in `production-full-playwright-results.json` and `production-full-run-artifacts/`.

## Observations and limits

- Initial sandbox run could not bind port8001; authorized escalated local test execution succeeded.
- Earlier exploratory run had an incorrect DELAY tick6 test expectation (HSM-A had completed exactly at tick6; active work is PICKLE-01) and overlapping live UI/localization edits. Test now asserts actual expected active work independently for all three scenarios. Korean WebGL fallback passed isolated and in the full suite. Preserved exploratory failure artifacts are not final verdict evidence.
- Reviewed actual desktop overview/detail, 2D stage, mobile, and fallback screenshots. 40 production screenshots are non-empty. Final screenshot helper scrolls to the document top before full-page capture; inspected final shots show navigation correctly positioned without the prior offscreen skip-link capture artifact.
- Browser QA uses one desktop Chrome engine plus a 390px emulated viewport, not physical mobile hardware. Canvas facility and coating-equipment picking, camera drag and zoom were exercised; direct 3D material picking was not claimed. Material selection/genealogy is covered through the visible worklist.

## artifactRefs

| id | kind | description | path |
|---|---|---|---|
| A-REPORT | browser-result | Final production suite 8 passed; no skipped/flaky/unexpected | `docs/evidence/playwright-results.json` |
| A-LOG | execution-log | Final production suite invocation and results | `docs/evidence/production-final-e2e.log` |
| A-UNIT | execution-log | Final npm test: 5 tests / 2 files passed | `docs/evidence/production-final-unit-tests.log` |
| A-FULL | browser-result | Earlier full suite 17 passed; includes original 10 logistics cases | `docs/evidence/production-full-playwright-results.json` |
| A-FULL-LOG | execution-log | Earlier full npm run test:e2e result | `docs/evidence/production-full-e2e.log` |
| D1-uncaught-browser-errors | browser-data | uncaught-browser-errors | `docs/evidence/production-qa-1-uncaught-browser-errors.json` |
| T1 | browser-action-trace | all eight stages expose internal work and return to overview in 2D | `test-results/production-all-eight-stage-059ac-nd-return-to-overview-in-2D/trace.zip` |
| D2-uncaught-browser-errors | browser-data | uncaught-browser-errors | `docs/evidence/production-qa-2-uncaught-browser-errors.json` |
| T2 | browser-action-trace | all nine product routes preserve casting branches and HGI bypasses cold rolling | `test-results/production-all-nine-produc-d0ca3-d-HGI-bypasses-cold-rolling/trace.zip` |
| D3-tick6-production | browser-data | tick6-production | `docs/evidence/production-qa-3-tick6-production.json` |
| D3-uncaught-browser-errors | browser-data | uncaught-browser-errors | `docs/evidence/production-qa-3-uncaught-browser-errors.json` |
| T3 | browser-action-trace | same HR and CR forms distinguish sale products from feedstock and preserve genealogy | `test-results/production-same-HR-and-CR--03886-tock-and-preserve-genealogy/trace.zip` |
| D4-scenario-production-snapshots | browser-data | scenario-production-snapshots | `docs/evidence/production-qa-4-scenario-production-snapshots.json` |
| D4-uncaught-browser-errors | browser-data | uncaught-browser-errors | `docs/evidence/production-qa-4-uncaught-browser-errors.json` |
| T4 | browser-action-trace | scenario changes alter visible work and reset reproduces production at the same step | `test-results/production-scenario-change-7d486-production-at-the-same-step/trace.zip` |
| D5-mobile-layout | browser-data | mobile-layout | `docs/evidence/production-qa-5-mobile-layout.json` |
| D5-uncaught-browser-errors | browser-data | uncaught-browser-errors | `docs/evidence/production-qa-5-uncaught-browser-errors.json` |
| T5 | browser-action-trace | mobile 2D core actions fit 390px and backend pause and step remain authoritative | `test-results/production-mobile-2D-core--30060-d-step-remain-authoritative/trace.zip` |
| D6-uncaught-browser-errors | browser-data | uncaught-browser-errors | `docs/evidence/production-qa-6-uncaught-browser-errors.json` |
| T6 | browser-action-trace | production WebGL context loss recovers to fully usable 2D stages and material selection | `test-results/production-production-WebG-9ac75-ages-and-material-selection/trace.zip` |
| D7-external-requests | browser-data | external-requests | `docs/evidence/production-qa-7-external-requests.json` |
| D7-uncaught-browser-errors | browser-data | uncaught-browser-errors | `docs/evidence/production-qa-7-uncaught-browser-errors.json` |
| T7 | browser-action-trace | 3D renders and camera responds while workspace tabs remain stable and local-only | `test-results/production-3D-renders-and--404b7-emain-stable-and-local-only/trace.zip` |
| D8-uncaught-browser-errors | browser-data | uncaught-browser-errors | `docs/evidence/production-qa-8-uncaught-browser-errors.json` |
| T8 | browser-action-trace | coating equipment clicks select only the matching GA, EG or HGI operation | `test-results/production-coating-equipme-a9b4b-hing-GA-EG-or-HGI-operation/trace.zip` |
| S-3d-detail | screenshot | 3d-detail | `docs/evidence/production-3d-detail.png` |
| S-3d-facility-picking | screenshot | 3d-facility-picking | `docs/evidence/production-3d-facility-picking.png` |
| S-3d-orbit | screenshot | 3d-orbit | `docs/evidence/production-3d-orbit.png` |
| S-3d-overview | screenshot | 3d-overview | `docs/evidence/production-3d-overview.png` |
| S-casting-root | screenshot | casting-root | `docs/evidence/production-casting-root.png` |
| S-cr-role-cr | screenshot | cr-role-cr | `docs/evidence/production-cr-role-cr.png` |
| S-cr-role-gi | screenshot | cr-role-gi | `docs/evidence/production-cr-role-gi.png` |
| S-equipment-eg-egl | screenshot | equipment-eg-egl | `docs/evidence/production-equipment-eg-egl.png` |
| S-equipment-ga-before | screenshot | equipment-ga-before | `docs/evidence/production-equipment-ga-before.png` |
| S-equipment-ga-hdg | screenshot | equipment-ga-hdg | `docs/evidence/production-equipment-ga-hdg.png` |
| S-equipment-hgi-hdg | screenshot | equipment-hgi-hdg | `docs/evidence/production-equipment-hgi-hdg.png` |
| S-equipment-hgi-pickle | screenshot | equipment-hgi-pickle | `docs/evidence/production-equipment-hgi-pickle.png` |
| S-hr-role-cr | screenshot | hr-role-cr | `docs/evidence/production-hr-role-cr.png` |
| S-hr-role-hr | screenshot | hr-role-hr | `docs/evidence/production-hr-role-hr.png` |
| S-incompatible-filter-recovery | screenshot | incompatible-filter-recovery | `docs/evidence/production-incompatible-filter-recovery.png` |
| S-mobile-390 | screenshot | mobile-390 | `docs/evidence/production-mobile-390.png` |
| S-overview-root | screenshot | overview-root | `docs/evidence/production-overview-root.png` |
| S-preview-coating-final | screenshot | preview-coating-final | `docs/evidence/production-preview-coating-final.png` |
| S-preview-final | screenshot | preview-final | `docs/evidence/production-preview-final.png` |
| S-route-billet | screenshot | route-billet | `docs/evidence/production-route-billet.png` |
| S-route-bloom | screenshot | route-bloom | `docs/evidence/production-route-bloom.png` |
| S-route-cr | screenshot | route-cr | `docs/evidence/production-route-cr.png` |
| S-route-eg | screenshot | route-eg | `docs/evidence/production-route-eg.png` |
| S-route-ga | screenshot | route-ga | `docs/evidence/production-route-ga.png` |
| S-route-gi | screenshot | route-gi | `docs/evidence/production-route-gi.png` |
| S-route-hgi | screenshot | route-hgi | `docs/evidence/production-route-hgi.png` |
| S-route-hr | screenshot | route-hr | `docs/evidence/production-route-hr.png` |
| S-route-slab | screenshot | route-slab | `docs/evidence/production-route-slab.png` |
| S-scenario-delay-tick6 | screenshot | scenario-delay-tick6 | `docs/evidence/production-scenario-delay-tick6.png` |
| S-scenario-normal-tick6 | screenshot | scenario-normal-tick6 | `docs/evidence/production-scenario-normal-tick6.png` |
| S-scenario-recovery-tick6 | screenshot | scenario-recovery-tick6 | `docs/evidence/production-scenario-recovery-tick6.png` |
| S-stage-1 | screenshot | stage-1 | `docs/evidence/production-stage-1.png` |
| S-stage-2 | screenshot | stage-2 | `docs/evidence/production-stage-2.png` |
| S-stage-3 | screenshot | stage-3 | `docs/evidence/production-stage-3.png` |
| S-stage-4 | screenshot | stage-4 | `docs/evidence/production-stage-4.png` |
| S-stage-5 | screenshot | stage-5 | `docs/evidence/production-stage-5.png` |
| S-stage-6 | screenshot | stage-6 | `docs/evidence/production-stage-6.png` |
| S-stage-7 | screenshot | stage-7 | `docs/evidence/production-stage-7.png` |
| S-stage-8 | screenshot | stage-8 | `docs/evidence/production-stage-8.png` |
| S-webgl-fallback | screenshot | webgl-fallback | `docs/evidence/production-webgl-fallback.png` |
