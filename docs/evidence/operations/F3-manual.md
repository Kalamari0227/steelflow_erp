# F3 — actual root browser verification

Verdict: **PASS**. Executed 2026-10-25 KST against retained http://127.0.0.1:4175 in an independent Codex IAB tab4, 1280×720, DPR1.5. Root controlled the UI through CUA; a separate read-only HTTP observer made 139 GETs. Original 4173/8000 servers were not targets. All paths below are relative to this report's directory.

## Observed actions and matching evidence

| Action | Actual observation | Evidence |
| --- | --- | --- |
| Select GA order/material | ORD-ga links MAT-ga-01, WO-ga-01, LOT-ga-01; 60,300kg order, 20,000kg initial material | F3-manual/01-selected-ga-ax.txt; 01-selected-ga.png; http-initial-world.json |
| Native material picking | Changed selection to ga02, clicked the visible ga01 body at actual projected screen coordinate604,342; inspector returned ga01 | F3-manual/02-native-material-pick-ax.txt; 02-native-material-pick.png |
| Equipment, camera and breadcrumb | Clicked physical ORE-SOURCE, URL became equipment/sources/ORE-SOURCE; orbit drag and wheel changed camera; overview/stage retained same material | F3-manual/03-orbit-zoom.json; 04-equipment-pick-ax.txt |
| Backend-owned production | Same run383d0a45fed64693859f71d200a74b1a and ga01 observed ORE→LIQUID_STEEL→SLAB→HR_COIL→CR_COIL→COATED_STRIP→GA_COIL, versionsV02/V04/V07/V13/V21/V28/V30 | F3-manual/05-production-scene.json through 12-port-scene.json and matching PNGs |
| Pause/resume | At62800ms revision157, material and elapsed/revision remained identical across independent observations, then UI Play resumed | F3-manual/06-pause-stability.json; 06-paused.png |
| Physical transport | Separate explicitly stepped run8354826a1ca24dd58db6f8b61667ab83: hook at44900, actual HOT_METAL V03 cargo at45900, then different cargo position at46900; inspector OPS-TORPEDO-A-CARGO | F3-manual/20-actual-cargo-scene.json; 20-actual-cargo.png; 21-cargo-moved-scene.json |
| Inspection and current version | PASSED inspection INSPECT-MAT-ga-01:V30 and selected GA_COIL V30, shipment link present | F3-manual/14-shipment-one-ax.txt; 17-2d-ga01-ax.txt |
| Partial then full delivery | Actual first run UI at455800ms showed67%; independently captured partial449600/rev539 delivered40,200kg remaining20,100kg. Full473600/rev554 delivered60,300kg remaining0; ORDER_DELIVERED E00003292 at473000 | F3-manual/12-port.png; http-partial-world.json; http-full-world.json; http-observed-summary.json |
| Both shipment links | SHIP-ga-01 ga01+ga02 actual arrival07:26 UTC; SHIP-ga-02 ga03 actual arrival07:53 UTC, both DELIVERED | F3-manual/14-shipment-one-ax.txt; 15-shipment-two-ax.txt; 15-shipment-two.png |
| 2D equivalent view | Shipment2 selects its ga03 member; 2D retains this identity. Explicit ga01 selection shows completed process table and PASSED V30; return3D same run, paused478400/rev558 and customer location | F3-manual/16-2d-ax.txt; 17-2d-ga01-ax.txt; 17-2d-ga01.png; 18-completed-scene.json |
| Final reset / usable output | UI reset, search clear, GA selected, 3D overview, followoff. NORMAL run41b0c1168629413396717ff2f58c5f69, elapsed/revision0, paused1x, 20orders22materials, AIoff, healthok | F3-manual/22-final-reset-ax.txt; 22-final-reset.png; 22-final-reset-world.json; 22-final-health.json |

## Honest scope and diagnostics

First end-to-end run used UI4x Play/Pause only; no Step/API seek. It paused at62800ms and after GA completion478400ms, so it is not labeled unbroken. The separately preserved automated normal video is the unbroken run. The supplemental physical-cargo observation used UI Step in a second run and was reset afterward. An initial transport search mistakenly looked for diagnostic custody `carrier`; the real documented value is `cargo`. After correction, actual hook/cargo positions were observed and saved; no product change was needed.

Partial pause was late: the HTTP observer's output delivered partial/full together. Root already captured the genuine67% screen at455800. The filename13-partial-ax.txt is an attempted partial pause capture but actually contains full delivery; it is **not partial-state proof**. Exact partial quantity proof is the independent raw HTTP world. No replayed fixture or invented snapshot is used.

CUA captured error/warn console array **[]** in browser-console.json and no visible blocking error. CUA exposes no raw pageerror/network event stream, so those counts are supported by the separate current production preview9 and full59 harness, not falsely attributed to the manual tab. Current9 covers zero unexplained pageerrors/console/externalrequests, keyboard/mobile/WebGL/timeout/last-state/reconnect; intended injected failures have separate logs. See docs/evidence/operations/intentional-error-audit.json and the actual preview9 report.

F3 combines this independent UI/HTTP observation with the required current9 production preview (9passed, exit0, 0skip/flaky/retry), full59 before the documented three-file arrival-label delta, actual videos, traces and source/cleanup receipts. The live tab is deliberately marked as the user's deliverable; the retained backend/preview are intentional product resources, not leftover QA processes.
