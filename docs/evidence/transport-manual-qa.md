# Production transport manual QA

Date: 2026-10-24. Verdict: **PASS**. Evidence directory is `docs/evidence` because `omo-agent-toolkit ulw-loop status --json` returned `ULW_LOOP_PLAN_MISSING`.

Final actual execution: `npm run test:e2e` → **22 passed in 1.7 minutes**, including 10 logistics, 8 production, and 4 transport scenarios. `npm test` → **5 passed**. Final `npm run typecheck` → exit 0. All four transport cases recorded **zero uncaught page errors and zero off-origin requests**.

The isolated browser surface was Chrome at `http://127.0.0.1:5174/?workspace=production`, with an isolated SQLite backend at `http://127.0.0.1:8001`. The QA backend cadence is 2 seconds. Motion sampling first observes a real new backend tick, pauses, resets, then checks both samples have tick 0. No API response or simulation time was fabricated. Canvas comparison ignores only the two-pixel screenshot perimeter to exclude verified fractional-scroll clipping; vehicle motion is bounded well inside that perimeter.

## manualQa.surfaceEvidence

| Scenario ID | Criterion reference | Surface | Exact invocation / actions | Verdict | artifactRefs |
|---|---|---|---|---|---|
| S01 | T1, T2 | Browser controls + real API responses | `npm run test:e2e`; `transport arrival gates processing and never duplicates facility inventory`: click Advance one step at every tick 0–24; compare typed responses, every stage boundary and internal operation | PASS: 198,000 kg conserved; every stage boundary has 1 tick, internal operations 0; every moving batch has exactly one vehicle and no facility occupancy | A01, A02, A03 |
| S02 | T1, T2 | HTTP | `python3 docs/evidence/transport-http-check.py`; executes the exact `curl -i -sS -X POST` calls in A05 against NORMAL activation, seven step calls and reset | PASS: GI tick 6 is HR/23,000 kg on flatbed from hot_rolling→cold_rolling with cold operations queued; tick 7 leg completed and PICKLE-01 running | A04, A05, A06, A07 |
| S03 | T3 | Chrome WebGL canvas, actual mouse clicks | `npm run test:e2e`; `loaded 3D truck is selectable, moves, freezes on pause, resumes and resets`: click projected visible HGI cargo in overview, verify HGI inspector and overview remains; select GI, enter hot rolling, click HGI truck again | PASS: both actual truck clicks select HGI. Final screenshots visibly show slab on truck, cab and wheels; overview molten carriers remain visible after facility-label fix | A01, A08, A09, A10 |
| S04 | T3, T4 | Chrome WebGL canvas + simulation controls | Same test: synchronized Play→Pause at tick 0, capture, wait 650ms, resume at 2×, pause after tick advances, reset | PASS: movement **3,446 pixels**, bounded x392–500/y224–290 in 962×481 capture; pause **0 pixels**; reset **0 pixels**; resume advances tick 0→1 at requested speed 2 | A08, A09, A11, A12, A13 |
| S05 | T4 | Browser controls + API responses | S01 reset and replay ticks 0–7; production scenario test steps NORMAL/DELAY/RECOVERY to tick 11 and resets/replays each | PASS: exact production snapshot replay; NORMAL GI coating running, DELAY GI cold rolling running, RECOVERY GI in transit | A01, A02, A03, A14 |
| S06 | T5 | Chrome, 390×844 viewport, forced WebGL loss | `npm run test:e2e`; `390px 2D transport tracking survives WebGL loss and permits arrival navigation`: WEBGL_lose_context, open production list, select HGI vehicle in transport table, follow destination, step once | PASS: fallback supports vehicle/material selection, 26 t cargo, from/to links and arrival. Page document width **390**, viewport width **390** | A01, A15, A16, A17, A18 |
| S07 | T6 | Chrome prefers-reduced-motion | `npm run test:e2e`; `reduced motion holds loaded transport still between authoritative ticks`: emulate reduce, synchronized Play/Pause at tick 0, then real step to tick 1 | PASS: reduced-motion same-tick difference **0 pixels**; authoritative arrival changes **1,595 pixels** | A01, A19, A20, A21 |
| S08 | T6 | Browser exceptions and network request listener | `npm run test:e2e`; per-case pageerror/request listeners before navigation, reporter attachments decoded and independently checked | PASS: all 4 transport cases errors=[] and external=[]; all 22 cases passed | A01, A22 |
| S09 | Regression | CLI + complete Chrome suite | `npm test`; `npm run typecheck`; `npm run test:e2e` | PASS: 5 unit/RTL, TypeScript exit 0, 22 browser tests | A01, A23, A24 |

## manualQa.adversarialCases

| Scenario ID | Criterion reference | Adversarial class | Expected behavior | Verdict | artifactRefs |
|---|---|---|---|---|---|
| ADV01 | T1 | Arrival boundary | Downstream processing cannot run during the one-tick transport; starts when arrival completes | PASS, literal GI tick 6/7 expectations match both HTTP and browser responses | A02, A06, A07 |
| ADV02 | T1 | Internal operation boundary | Operations in one facility remain contiguous with no fictitious trip | PASS across every batch and ticks 0–24 | A02, A03 |
| ADV03 | T2 | Duplicate inventory | An in-transit batch must not also occupy a facility, and cargo version/mass must match | PASS across all 25 snapshots | A02, A03 |
| ADV04 | T3 | Pause/resume/speed | Paused pixels and backend tick freeze; speed 2 resumes actual clock progress | PASS, zero paused pixel difference and tick 0→1 after resume | A08, A11, A12 |
| ADV05 | T4 | Reset/replay | Fresh run reproduces transports/materials and paused truck position | PASS, exact API snapshot equality and zero reset pixel difference | A04, A08, A13, A14 |
| ADV06 | T5 | WebGL context loss | Accessible 2D transport table, inspector and arrival navigation remain usable | PASS | A15, A16, A17 |
| ADV07 | T5 | Narrow viewport | Core tracking fits 390px without document overflow | PASS, 390/390 | A16, A17, A18 |
| ADV08 | T6 | Reduced motion | No interpolation between authoritative snapshots, but arrival still renders | PASS, 0 same-tick pixels; 1,595 arrival pixels | A19, A20, A21 |
| ADV09 | T6 | External loading / exception | No off-origin request or uncaught browser exception | PASS | A22 |
| ADV10 | T3 | Foreground label interception | Clicking visible overview truck must select cargo, not enter foreground facility | PASS after scene-owner label correction; original regression kept in final test | A09, A10, A25 |
| ADV11 | Scope | Authentication / external mutation | This synthetic local-only change has no authentication, live dispatch, message sending or paid side effect | not_applicable: no such boundary is introduced or exercised | A00 |

## manualQa.artifactRefs

All paths below are relative to repository root. Every referenced artifact was checked to exist and contain bytes.

| ID | Kind | Description | Path |
|---|---|---|---|
| A00 | plan | Criteria, scope and planned invocations | `docs/evidence/transport-qa-plan.md` |
| A01 | log | Final complete 22/22 run | `docs/evidence/transport-final-full-e2e.log` |
| A02 | JSON | Full NORMAL production responses for tick 0–24 | `docs/evidence/transport-timeline.json` |
| A03 | browser trace | Timeline and replay action log | `docs/evidence/transport-final-run/transport-transport-arriva-e80d3-plicates-facility-inventory/trace.zip` |
| A04 | JSON | Independent curl assertions, departure/arrival/reset | `docs/evidence/transport-http-verdict.json` |
| A05 | command log | Exact curl invocations | `docs/evidence/transport-http-invocations.txt` |
| A06 | HTTP transcript | Headers and full body at GI departure tick 6 | `docs/evidence/transport-http-tick6.txt` |
| A07 | HTTP transcript | Headers and full body at GI arrival tick 7 | `docs/evidence/transport-http-tick7.txt` |
| A08 | JSON | Canvas pixel differences, bounding rectangle and ticks | `docs/evidence/transport-canvas-pixel-evidence.json` |
| A09 | browser trace | Actual overview/detail truck clicks, play/pause/speed/reset | `docs/evidence/transport-final-run/transport-loaded-3D-truck--9c683-on-pause-resumes-and-resets/trace.zip` |
| A10 | screenshot | Unobscured carriers and selected overview HGI truck | `docs/evidence/transport-overview-truck-selected.png` |
| A11 | screenshot | Loaded truck before motion | `docs/evidence/transport-truck-loaded-paused.png` |
| A12 | screenshot | Truck after movement and 650ms freeze | `docs/evidence/transport-truck-frozen.png` |
| A13 | screenshot | Reset reproduces initial truck location | `docs/evidence/transport-truck-reset.png` |
| A14 | JSON | Replay comparison ticks 0–7 | `docs/evidence/transport-replay.json` |
| A15 | browser trace | Mobile WebGL-loss, transport selection and arrival actions | `docs/evidence/transport-final-run/transport-390px-2D-transpo-940de--permits-arrival-navigation/trace.zip` |
| A16 | screenshot | 390px 2D fallback with loaded HGI and destination links | `docs/evidence/transport-mobile-fallback.png` |
| A17 | screenshot | 390px arrived HGI, hot rolling work and empty active route | `docs/evidence/transport-mobile-arrived.png` |
| A18 | JSON | Measured viewport/document width | `docs/evidence/transport-mobile-layout.json` |
| A19 | JSON | Reduced-motion and arrival differences | `docs/evidence/transport-reduced-motion.json` |
| A20 | browser trace | Reduced-motion real browser actions | `docs/evidence/transport-final-run/transport-reduced-motion-h-04d1a-between-authoritative-ticks/trace.zip` |
| A21 | screenshot | Reduced-motion authoritative arrival | `docs/evidence/transport-reduced-arrival.png` |
| A22 | JSON | Independently decoded final reporter results and browser health | `docs/evidence/transport-final-health.json` |
| A23 | log | Unit/RTL results | `docs/evidence/transport-unit.log` |
| A24 | log | Final TypeScript verification | `docs/evidence/transport-typecheck.log` |
| A25 | log | Original failed full run retained for regression history | `docs/evidence/transport-full-e2e.log` |
| A26 | video | Finite real browser transport selection/motion/pause/reset recording | `docs/evidence/transport-demo.webm` |
| A27 | JSON | Controlled JSON-evidence write causes Vite full-reload | `docs/evidence/transport-mobile-json-reload-signals.json` |
| A28 | report | Full final Playwright results with attachments | `docs/evidence/transport-final-run/results.json` |

## Findings resolved and limits

- The first full run rejected the overview truck click: a foreground facility label obscured/intercepted it. The scene owner moved the labels; final tests retain both overview and detail truck clicks.
- A one-row (962-pixel) reduced-motion screenshot mismatch came solely from fractional clipping at the canvas boundary. The comparison excludes only a two-pixel perimeter; the movement region is x392–500/y224–290.
- Controlled diagnostics proved writing `transport-mobile-layout.json` mid-scenario triggers Vite's `full-reload` frame. PNG overwrite alone did not. Evidence JSON now writes after all scenario assertions, and the final complete run passes. A27 preserves the exact reload signal.
- The video and screenshots prove visible movement and freeze, not a physical truck model or frame-rate benchmark. Demand rendering is not GPU-profiled. The test environment is a synthetic local fixture; no live production or external service mutation was performed.
