# SteelFlow 3D P0 implementation

Target demo: 2026-10-30. Empty workspace inspected on 2026-10-24.

1. Foundation: Vite/React frontend, FastAPI backend, shared contracts, deterministic fixture, architecture and setup docs.
2. Scene: procedural isometric mill, coil yard, dispatch and port; orbit/zoom, hover, selection and reset camera.
3. Integration: SQLite models/migration and typed REST, linked order/coil/shipment views and accessible table.
4. Simulation: single backend clock, serialized commands, deterministic NORMAL/DELAY/RECOVERY transitions, append-only history across resets.
5. Rules and checks: transparent delay/recovery explanations, conservation, referential integrity, reproducibility, API and browser tests.
6. Demo: production build, browser screenshots, local fallback video, operator script and known limitations.

Acceptance requires observed browser rendering and controls, automated invariants, and actual test results. No ERP integrations, external publishing, credentials, external AI calls, or real operational data.

## P0 decisions

- One local operator, one backend worker. An asyncio task owns automatic stepping; the browser only polls state.
- Fixed UTC baseline 2026-10-30T08:00:00Z. One simulation tick represents 30 minutes. Wall-clock cadence changes at 1x/2x/4x without changing transition outcomes.
- Synthetic IDs are stable across runs. Reset starts a new run with the same business baseline and retains prior events; compare business state without audit run IDs.
- Three scenarios differ through explicit deterministic schedules. Recovery uses a documented alternate line/dispatch rule; it is a demonstration, not an optimization solver.
- 3D positions project current inventory locations; any interpolation is visual only. No remote models, textures, fonts or map tiles.
- World response is one consistent snapshot. Pydantic/OpenAPI and Zod define the contract; all control POSTs return the same world shape.
- The AI adapter is disabled by default and cannot mutate business state. Core explanations always come from local rules.

## Ownership

Backend worker: `backend/**`. Scene worker: `src/scene/**`. Lead: app shell, contracts, styles, documentation and integration. Verification worker: frontend and end-to-end tests. Shared contracts change only through the lead.

## Implementation record

| Phase | Delivered files | Checks and issues resolved |
| --- | --- | --- |
| 1 Foundation | package/TS/Vite config, `src/contracts.ts`, `docs/CONTRACT.md`, `DESIGN.md`, backend fixtures/models | Empty workspace confirmed. Public dependency install completed after sandbox DNS retry. Contract runtime parsing is exercised in integration tests. |
| 2 Scene | `src/scene/{WorldScene,WorldEntities,Facility,vehicles,primitives}.tsx` | Typecheck passed; actual canvas rendering, mesh hover/pick, orbit and zoom verified in Chrome. |
| 3 API and views | `backend/app/`, migrations, `src/{api,store}.ts`, components | All requested API routes and joined coil detail checked; SQLite migration roundtrip and constraints verified. |
| 4 Simulation | backend engine/clock, SimulationControls, event view | Full deterministic replay, pause/play/speed, background progression without an open page, reset retention, concurrent steps and persisted restart tested. |
| 5 Risk and integrity | backend rules/tests, store/Inspector tests, browser suite | 49 pytest and 5 Vitest/RTL tests pass. Risk predicate now uses actual ETA vs due, and affected lots correctly use Line A. |
| 6 Demo and rendering | lazy scene, capped DPR/demand frames, responsive styles, README, DEMO, screenshots/video | Narrow-layout overflow fixed by containing table accessibility nodes. WebGL teardown root conflict fixed with a stable label portal; failing regression turned green. Final counts and media are recorded in TEST_RESULTS. |

All P0 behavior was implemented locally. No external publishing or operational data access occurred. Tests use synthetic SQLite files separate from the operator demo database. Known build-size/dependency annotation warnings are documented without suppressing them.
