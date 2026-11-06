# Transport QA plan

Evidence directory: `docs/evidence` (ulw-loop reports ULW_LOOP_PLAN_MISSING).
Product code is owned by other agents; QA owns `tests/production.spec.ts`, `tests/transport.spec.ts`, and transport evidence only.

Criteria:
- T1: Exactly one clock tick between adjacent stages; zero transport gaps between internal operations. Independent known NORMAL GI timeline: casting→hot rolling tick 3–4, hot rolling→cold rolling tick 6–7, cold rolling→coating tick 10–11; mass 23,000 kg. At tick 6 GI is on flatbed, cold-rolling operations queued; at tick 7 arrived and pickling running.
- T2: Transport cargo equals the batch current material/version/mass, and in-transit batches have vehicle location and no facility occupancy. All batch mass remains 198,000 kg across ticks and scenarios.
- T3: Real 3D canvas captures show loaded trucks moving while playing, frozen while paused, resuming and respecting speed. Selected vehicle links to matching inspector; visual screenshots are inspected, and canvas pixel deltas localize movement.
- T4: Reset reproduces deterministic transports and batch state. NORMAL/DELAY/RECOVERY retain differing meaningful operation/status expectations.
- T5: 390px 2D and WebGL-loss fallback retain transport selection and from/to tracking without horizontal overflow.
- T6: Reduced-motion rendering is static between clock snapshots. No uncaught browser errors or off-origin requests.

Invocations after integration ready:
1. `npm test` (unit/RTL CLI surface, log to transport-unit.log).
2. `npm run test:e2e` (real Chrome/Playwright UI surface at http://127.0.0.1:5174, isolated backend :8001, action traces/videos and screenshot PNGs).
3. `curl -i` against the isolated API for initial, stepped, arrival, reset states (HTTP surface; headers and bodies retained).

Adversarial classes: boundary/arrival, pause/resume/speed, reset/replay, reduced motion, 390px overflow, WebGL loss, off-origin loading, uncaught exception. Authorization/authentication and live-production mutation are not applicable to this synthetic local-only feature.

No verdict is assigned until scenarios execute. Failed cases will be reported to the owning implementation agent and rerun after fixes.
