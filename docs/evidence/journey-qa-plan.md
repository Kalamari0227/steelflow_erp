# Product journey QA plan

No ULW loop plan exists; use caller-owned docs/evidence/journey-* artifacts. Product and existing tests remain untouched.

- J1: Select all 17 catalog routes through browser family/route controls; independently assert final forms and step counts, mass20,000kg (titanium12,000), one lineage, connected versions, no premature first-step transform, each UI step boundary, completed sale role and reset replay.
- J2: Capture actual WebGL geometry for all 8 families and inspect representative equipment detail; no screenshot planes or source-only visual claims.
- J3: Actual mouse raycast onto material and furnace meshes; compare real canvas images before/after play, freeze on pause, resume4x and reset; preserve finite video/action trace.
- J4: 390px viewport, keyboard family/equipment selection, actual WEBGL_lose_context fallback, 2D material and current-version tracking with no document overflow.
- J5: Abort actual journey GET requests to exercise error/frozen-last-state and recover through retry; reduced-motion holds still during delayed real GET responses but updates on authoritative response.
- J6: Zero uncaught page errors and off-origin network requests; existing22regressions unchanged.

Exact primary invocation after integration freeze: `npm run test:e2e`. Focused diagnostic invocation: `npm run test:e2e -- tests/journey.spec.ts`. Chrome uses isolated API8001/UI5174 and separate SQLite fixture. Evidence JSON is written only after scenario assertions because overwriting docs/evidence JSON is known to trigger Vite full reload.
