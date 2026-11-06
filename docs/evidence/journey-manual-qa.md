# Product journey manual QA

Date: 2026-10-24. Verdict: **PASS**. No ULW loop plan exists (`ULW_LOOP_PLAN_MISSING`); evidence uses the caller's `docs/evidence/journey-*` directory.

Final invocation: `npm run test:e2e` → **28 passed in 2.8 minutes**, zero skipped, zero flaky, zero unexpected. This includes the existing 22 logistics/production/transport cases and six new journey scenarios. No product code or old tests were changed by this QA task. The final run started at 09:53:30 UTC and lasted 167.509 seconds. All six journey cases have **zero uncaught page errors and zero off-origin requests** in their actual reporter attachments.

Surface: real Chrome, `http://127.0.0.1:5174/?workspace=journey`, isolated API `http://127.0.0.1:8001`, unique SQLite fixture configured by `playwright.config.ts`. Test snapshots come from actual requests; network adversaries hold or abort GET requests without fabricating response data or advancing a client clock. Pixel comparison uses the actual WebGL canvas, an RGB-delta threshold of 15, and excludes only its two-pixel perimeter. Video is the actual browser recording, converted to H.264 without altering frames: 1440×1000, 18.36 seconds.

## manualQa.surfaceEvidence

| Scenario ID | Criterion reference | Surface | Exact invocation / actions | Verdict | artifactRefs |
|---|---|---|---|---|---|
| S01 | J1: catalog and all routes | Chrome controls + real API responses | `npm run test:e2e`; `all 17 routes complete their exact forms with one stable lineage and no early transformations`: select every family/route in 2D; play/pause before the first boundary; click all 187 step boundaries; reset every completed route | PASS: all 17 literal final-form expectations, route lengths, 20,000 kg steel / 12,000 kg titanium, stable MATERIAL-id lineage, connected version parents, sale role only at completion and exact reset material/history | A01, A02, A03 |
| S02 | J1: no premature transformation | HTTP headers and bodies | `python3 docs/evidence/journey-http-check.py`; exact `curl -i -sS -X` invocations in A05 against select/play/pause/step/reset and invalid commands | PASS: HR first boundary4000ms remains SLAB; paused furnace4200ms remains SLAB; furnace10000ms becomes HOT_SLAB;45800ms becomes completed HR_COIL, sale_product,20,000kg; reset material/history identical | A04, A05, A06, A07, A08 |
| S03 | J2: actual eight family miniatures | Chrome WebGL canvas | `npm run test:e2e`; `all eight product families render distinct selectable 3D miniatures`: select hr/plate/wire/cr/gi/go/sts-hr/ti-hr, capture overview, select second equipment step and capture detail | PASS: all eight actual scenes and selectable equipment details; inspected contact sheets show steel rolling/plate cooling/wire laying, cold/coating baths, electrical annealing, stainless furnace/ladle and titanium press | A01, A09, A10, A11 |
| S04 | J3: actual mesh selection | Chrome mouse raycast + focus/selection state | `npm run test:e2e`; `real material and equipment meshes select and motion freezes, resumes at speed and resets`: click projected material at world[-15,1.06,-4], assert material passport focus; reset view, click furnace roof[-6,2.7,-4], assert equipment selection | PASS: actual rendered material and equipment mesh clicks select the corresponding UI, with camera reset between clicks | A12, A13 |
| S05 | J3: movement, pause, resume, reset | WebGL canvas + real backend state | Same test: step twice to HOT_SLAB, play550ms, pause, capture, wait600ms; resume at4× for500ms; reset | PASS: moving **1,240 pixels** bounded x496–595/y80–231 in1122×561; paused **0 pixels** and unchanged backend elapsed; reset **0 pixels**, exact original material and elapsed0; resume elapsed advances at4× | A12, A13, A14, A15, A16 |
| S06 | J3: full transformation video | Chrome actual continuous playback + independent API observations | Same test after reset: select4×, play, poll real API every200ms until completed, capture final and reset overview. `ffmpeg -y -i docs/evidence/journey-demo.webm -c:v libx264 -crf 20 -pix_fmt yuv420p -movflags +faststart docs/evidence/journey-demo.mp4` | PASS: actual full HR flow observed SLAB→HOT_SLAB→HOT_STRIP→STRIP→HR_COIL; final elapsed45800ms, stable lineage and20,000kg. Recording visibly shows the strip progressing along equipment and final coil on outgoing truck | A12, A17, A18, A19, A20 |
| S07 | J4: mobile and keyboard fallback | Chrome390×844 + forced WebGL context loss | `npm run test:e2e`; `390px keyboard controls and WebGL loss preserve complete 2D tracking`: WEBGL_lose_context, open2D, keyboard Enter on titanium family and vacuum equipment, select ti-sheet, advance one step | PASS: usable fallback, correct selected vacuum step, MATERIAL-ti-sheet:1 tracking; document390px equals viewport390px | A21, A22, A23 |
| S08 | J5: pending GET, error freeze and retry | Real browser network interception + canvas + independent API | `npm run test:e2e`; `connection failure freezes the actual scene and retry restores authoritative state`: hold actual GET, play, capture after700ms and another500ms, release as abort, capture error state550ms apart, pause backend, retry successfully | PASS: pending-request pair **0 pixels**, error pair **0 pixels**; visible progress remains last authoritative value while independent backend elapsed reaches1400ms; no early timeout alert, then explicit error and disabled controls, recovery through Retry | A24, A25, A26, A27 |
| S09 | J5: reduced motion | Chrome prefers-reduced-motion + delayed actual GET | `npm run test:e2e`; `reduced motion does not interpolate while real snapshot reads are delayed`: emulate reduce, holdGET, play, capture500ms apart; releaseGET and pause | PASS: reduced-motion pair **0 pixels** while real API advances; authoritative arrival changes **10,119 pixels** | A28, A29, A30 |
| S10 | J6: runtime and regression | Browser exception/request listeners + complete suite | `npm run test:e2e`; decode final reporter attachments and independently assert every journey health record is errors=[]/external=[] | PASS:6/6 clean browser-health records,28/28 overall, existing22 unchanged | A01, A31, A32 |
| S11 | Deliverable capture | Built production preview Chrome1440×1000 | `node --input-type=module` using Playwright Chromium: GET navigation to `http://127.0.0.1:4173/?workspace=journey`, assert progress0 and Play enabled, settle600ms, fullPage screenshot | PASS: fresh paused HR at0ms/1×, first step highlighted; requests allGET, errors=[]; no operator state mutation | A20, A37 |

## manualQa.adversarialCases

| Scenario ID | Criterion reference | Adversarial class | Expected behavior | Verdict | artifactRefs |
|---|---|---|---|---|---|
| ADV01 | J1 | Early process boundary | Input form remains until backend step completion | PASS: all17 initial partials, literal HR furnace before/at boundary | A02, A06, A07 |
| ADV02 | J1 | Identity/mass loss | One lineage and connected versions preserve mass through all187 transitions | PASS: all17 routes and complete reset replay | A02, A03 |
| ADV03 | J1 | Invalid commands | Unknown product404 and invalid speed422 do not mutate completed snapshot | PASS: full before/after snapshot equality | A04, A05, A33, A34, A35 |
| ADV04 | J3 | Pause/speed/reset | Real pixels and clock freeze;4× resumes; reset reproduces starting frame | PASS:0 paused/reset pixels, backend delta at4× | A12, A14, A15, A16 |
| ADV05 | J4 | WebGL loss | Keyboard-accessible2D remains usable and lineage remains visible | PASS | A21, A22 |
| ADV06 | J4 | Narrow viewport | Core controls fit390px without document overflow | PASS:390/390 | A22, A23 |
| ADV07 | J5 | Hung request before timeout | Scene stops extrapolating after350ms; no invented progress; server can continue independently | PASS: captured700ms+ after snapshot,0 pixels over next500ms; no timeout alert yet; real backend1400ms | A24, A25, A26 |
| ADV08 | J5 | Network failure/recovery | Explicit error freezes the last scene; Retry restores live authoritative state | PASS:0 error pixels, disabled pause, successful retry | A24, A25, A27 |
| ADV09 | J5 | Reduced-motion setting | No interpolated movement but authoritative changes remain visible | PASS:0 pixels delayed;10,119 after response | A28, A29, A30 |
| ADV10 | J6 | Runtime errors/external loading | No uncaught exception or off-origin request | PASS:all6cases | A31, A32 |
| ADV11 | Test isolation | Workspace changes during development server run | Evidence must distinguish reload interruption from product assertion failure | PASS after complete file-output freeze: same original test passes7.0s with no code/test change; prior27/28 run retained | A01, A36 |
| ADV12 | Scope | Authentication/payment/external mutation | No such boundary is introduced by this synthetic local journey workspace | not_applicable: no accounts, payments, permissions, live production writes or external messaging in scope | A00 |

## manualQa.artifactRefs

Paths are relative to repository root; all artifacts below were checked to exist and contain bytes.

| ID | Kind | Description | Path |
|---|---|---|---|
| A00 | plan | Scope and criteria | `docs/evidence/journey-qa-plan.md` |
| A01 | log | Final28/28 full browser execution | `docs/evidence/journey-final-full-e2e.log` |
| A02 | JSON | All17route initial/partial/every-step snapshots | `docs/evidence/journey-all-route-snapshots.json` |
| A03 | browser trace | All17route controls and assertions | `docs/evidence/journey-final-run/journey-all-17-routes-comp-82d8d-nd-no-early-transformations/trace.zip` |
| A04 | JSON | Independent HTTP verdict | `docs/evidence/journey-http-verdict.json` |
| A05 | command log | Exact curl-i command arrays | `docs/evidence/journey-http-invocations.json` |
| A06 | HTTP transcript | Furnace partial4200ms remainsSLAB | `docs/evidence/journey-http-partial-furnace.txt` |
| A07 | HTTP transcript | Furnace boundary10000ms becomesHOT_SLAB | `docs/evidence/journey-http-furnace-boundary.txt` |
| A08 | HTTP transcript | Completed HR at45800ms | `docs/evidence/journey-http-boundary-9.txt` |
| A09 | screenshot contact sheet | All8family actual overview renders | `docs/evidence/journey-family-contactsheet.png` |
| A10 | screenshot contact sheet | All8family selected equipment details | `docs/evidence/journey-family-contactsheet-detail.png` |
| A11 | browser trace | Family/step selection actions | `docs/evidence/journey-final-run/journey-all-eight-product--f09d3-ct-selectable-3D-miniatures/trace.zip` |
| A12 | JSON | Motion pixel bounds, speed snapshots, complete observed HR playback | `docs/evidence/journey-motion.json` |
| A13 | browser trace | Actual mesh clicks, motion and full HR playback | `docs/evidence/journey-final-run/journey-real-material-and--7574e-resumes-at-speed-and-resets/trace.zip` |
| A14 | screenshot | Before motion, HOT_SLAB | `docs/evidence/journey-motion-before.png` |
| A15 | screenshot | Moved and paused frame | `docs/evidence/journey-motion-frozen.png` |
| A16 | screenshot | Reset reproduces baseline | `docs/evidence/journey-motion-reset.png` |
| A17 | video | Original finite actual browser capture | `docs/evidence/journey-demo.webm` |
| A18 | video | H.264 full motion/complete-HR playback18.36s | `docs/evidence/journey-demo.mp4` |
| A19 | video contact sheet | Six sampled frames from actual recorded video | `docs/evidence/journey-video-contactsheet.png` |
| A20 | screenshot | Fresh built-preview4173 full-page desktop overview, paused0ms/1× | `docs/evidence/journey-desktop-overview.png` |
| A21 | browser trace | Mobile keyboard and actual WebGL loss | `docs/evidence/journey-final-run/journey-390px-keyboard-con-9fb63-eserve-complete-2D-tracking/trace.zip` |
| A22 | screenshot |390px complete fallback page | `docs/evidence/journey-mobile-fallback.png` |
| A23 | JSON | Actual document/viewport widths | `docs/evidence/journey-mobile-layout.json` |
| A24 | JSON | HeldGET and failedGET freeze pixel evidence | `docs/evidence/journey-failure-freeze.json` |
| A25 | browser trace | PendingGET→abort→Retry actual actions | `docs/evidence/journey-final-run/journey-connection-failure-3bbc6-estores-authoritative-state/trace.zip` |
| A26 | screenshot | PendingGET frozen second frame | `docs/evidence/journey-hung-second.png` |
| A27 | screenshot | Error frozen second frame | `docs/evidence/journey-failure-frozen-second.png` |
| A28 | JSON | Reduced-motion pixel measurements | `docs/evidence/journey-reduced-motion.json` |
| A29 | browser trace | Reduced-motion delayedGET and release | `docs/evidence/journey-final-run/journey-reduced-motion-doe-f4401--snapshot-reads-are-delayed/trace.zip` |
| A30 | screenshot | Reduced-motion authoritative arrival | `docs/evidence/journey-reduced-authoritative.png` |
| A31 | JSON | Decoded final health records and full-run stats | `docs/evidence/journey-final-health.json` |
| A32 | JSON | Full final Playwright results and attachments | `docs/evidence/journey-final-run/results.json` |
| A33 | HTTP transcript | Unknown-product404 | `docs/evidence/journey-http-unknown-product.txt` |
| A34 | HTTP transcript | Invalid-speed422 | `docs/evidence/journey-http-invalid-speed.txt` |
| A35 | HTTP transcript | Snapshot unchanged after invalid requests | `docs/evidence/journey-http-after-invalid.txt` |
| A36 | retained failure artifacts | Original27passed/1reload-interrupted run, log/results/all traces | `docs/evidence/journey-interrupted-full-run/results.json` |
| A37 | JSON | Production-preview capture URL, viewport, GET-only requests and visible text | `docs/evidence/journey-preview-capture.json` |
| A38 | screenshot | Original final-test post-reset capture retained | `docs/evidence/journey-desktop-post-reset.png` |

## Resolved findings and limits

- First diagnostic reset comparison caught retained inactive mill-drive rotation. The scene owner corrected it; final actual reset difference is0 pixels.
- Held requests exposed unbounded local extrapolation before timeout. The scene owner capped it at350ms; final real pending-request test confirms frozen pixels before an error is raised.
- A prior full run's existing logistics test was interrupted by document reload: POST at18:50:19.553 had response status-1 and Vite reconnected; a second reconnect occurred18:50:53. These align with concurrent Markdown evidence writes at18:50:19 and18:50:53. Exact triggering file was not captured by that trace, so file attribution is an inference. Entire run retained. Under total output freeze the unchanged test and all28cases passed.
- JSON evidence is written after assertions to avoid development-server reload during scenarios. This is test-output coordination; no product expectation was relaxed.
- Screenshots and video prove rendered movement, selection, visible shape transition and freeze. They do not measure GPU utilization or certify physical plant timing. Synthetic mass/time models and reference-inspired geometry are illustrative; no live service or real production data was changed.
