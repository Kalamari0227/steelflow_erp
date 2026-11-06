# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: transport.spec.ts >> loaded 3D truck is selectable, moves, freezes on pause, resumes and resets
- Location: tests/transport.spec.ts:101:1

# Error details

```
Error: expect(locator).toContainText(expected) failed

Locator: getByRole('complementary', { name: '선택 소재 상세' })
Expected substring: "PROD-HGI"
Received string:    "소재 추적PROD-GICURRENT MATERIAL용강후공정 소재목표 제품GI · 용융아연배치 질량23 t작업 상태운송 중용강 운반차 · 운송 중VEHICLE-GI-ladle_car현재 소재는 차량에 적재되어 있습니다.출발 공정 · 제강·출강도착 공정 · 연주소재 변환 이력 3철원료소재 · 제선·출선MAT-PROD-GI:00용선소재 · 제선·출선MAT-PROD-GI:01용강소재 · 제강·출강MAT-PROD-GI:02형태와 용도는 별개입니다. 같은 열연·냉연 코일도 생산 경로에 따라 판매 제품 또는 다음 공정의 소재가 됩니다."
Timeout: 10000ms

Call log:
  - Expect "toContainText" getByRole('complementary', { name: '선택 소재 상세' }) with timeout 10000ms
  - waiting for getByRole('complementary', { name: '선택 소재 상세' })
    24 × locator resolved to <aside aria-label="선택 소재 상세" class="production-inspector panel">…</aside>
       - unexpected value "소재 추적PROD-GICURRENT MATERIAL용강후공정 소재목표 제품GI · 용융아연배치 질량23 t작업 상태운송 중용강 운반차 · 운송 중VEHICLE-GI-ladle_car현재 소재는 차량에 적재되어 있습니다.출발 공정 · 제강·출강도착 공정 · 연주소재 변환 이력 3철원료소재 · 제선·출선MAT-PROD-GI:00용선소재 · 제선·출선MAT-PROD-GI:01용강소재 · 제강·출강MAT-PROD-GI:02형태와 용도는 별개입니다. 같은 열연·냉연 코일도 생산 경로에 따라 판매 제품 또는 다음 공정의 소재가 됩니다."

```

```yaml
- complementary "선택 소재 상세":
  - img
  - text: 소재 추적 PROD-GI CURRENT MATERIAL
  - heading "용강" [level=2]
  - text: 후공정 소재
  - img
  - text: 목표 제품
  - strong: GI · 용융아연
  - text: 배치 질량
  - strong: 23 t
  - text: 작업 상태
  - strong: 운송 중
  - img
  - strong: 용강 운반차 · 운송 중
  - code: VEHICLE-GI-ladle_car
  - paragraph: 현재 소재는 차량에 적재되어 있습니다.
  - button "출발 공정 · 제강·출강":
    - text: 출발 공정 · 제강·출강
    - img
  - button "도착 공정 · 연주":
    - text: 도착 공정 · 연주
    - img
  - heading "소재 변환 이력 3" [level=3]
  - list "소재 계보":
    - listitem:
      - strong: 철원료
      - text: 소재 · 제선·출선 MAT-PROD-GI:00
      - img
    - listitem:
      - strong: 용선
      - text: 소재 · 제선·출선 MAT-PROD-GI:01
      - img
    - listitem:
      - img
      - strong: 용강
      - text: 소재 · 제강·출강 MAT-PROD-GI:02
  - paragraph: 형태와 용도는 별개입니다. 같은 열연·냉연 코일도 생산 경로에 따라 판매 제품 또는 다음 공정의 소재가 됩니다.
```

# Test source

```ts
  10  |   const response = await request.get('/api/v1/world');
  11  |   expect(response.ok()).toBe(true);
  12  |   return WorldSchema.parse(await response.json());
  13  | }
  14  | async function clickCommand(page: Page, label: string, endpoint: string) {
  15  |   const pending = page.waitForResponse(response => response.url().endsWith(`/simulation/${endpoint}`) && response.request().method() === 'POST');
  16  |   await page.getByRole('button', { name: label, exact: true }).click();
  17  |   const response = await pending;
  18  |   expect(response.ok()).toBe(true);
  19  |   return WorldSchema.parse(await response.json());
  20  | }
  21  | async function save(name: string, value: unknown) { await writeFile(`${evidence}/transport-${name}.json`, JSON.stringify(value, null, 2)); }
  22  | async function capture(page: Page, name: string) { return page.locator('canvas').screenshot({ path: `${evidence}/transport-${name}.png` }); }
  23  | async function difference(page: Page, before: Buffer, after: Buffer) {
  24  |   return page.evaluate(async ([first, second]) => {
  25  |     const decode = async (encoded: string) => {
  26  |       const image = new Image(); image.src = `data:image/png;base64,${encoded}`; await image.decode();
  27  |       const canvas = document.createElement('canvas'); canvas.width = image.width; canvas.height = image.height;
  28  |       const context = canvas.getContext('2d'); if (!context) throw new Error('Missing image context');
  29  |       context.drawImage(image, 0, 0); return { width: image.width, height: image.height, data: context.getImageData(0, 0, image.width, image.height).data };
  30  |     };
  31  |     const a = await decode(first!); const b = await decode(second!);
  32  |     let count = 0; let x0 = a.width; let y0 = a.height; let x1 = -1; let y1 = -1;
  33  |     for (let pixel = 0; pixel < a.width * a.height; pixel++) {
  34  |       const offset = pixel * 4;
  35  |       if (Math.abs(a.data[offset]! - b.data[offset]!) + Math.abs(a.data[offset + 1]! - b.data[offset + 1]!) + Math.abs(a.data[offset + 2]! - b.data[offset + 2]!) > 15) {
  36  |         count++; const x = pixel % a.width; const y = Math.floor(pixel / a.width);
  37  |         x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y);
  38  |       }
  39  |     }
  40  |     return { count, bounds: count ? { x0, y0, x1, y1 } : null, width: a.width, height: a.height };
  41  |   }, [before.toString('base64'), after.toString('base64')]);
  42  | }
  43  | 
  44  | test.beforeEach(async ({ page, request }) => {
  45  |   await mkdir(evidence, { recursive: true });
  46  |   const log = { errors: [] as string[], external: [] as string[] }; logs.set(page, log);
  47  |   page.on('pageerror', error => log.errors.push(error.message));
  48  |   page.on('request', request => { if (!request.url().startsWith('http://127.0.0.1:5174/') && !request.url().startsWith('data:') && !request.url().startsWith('blob:')) log.external.push(request.url()); });
  49  |   expect((await request.post('/api/v1/scenarios/NORMAL/activate')).ok()).toBe(true);
  50  |   await page.goto('/?workspace=production');
  51  |   await expect(page.getByRole('heading', { name: '생산 오버뷰', exact: true })).toBeVisible();
  52  | });
  53  | test.afterEach(async ({ page }, testInfo) => {
  54  |   await testInfo.attach('transport-browser-health', { body: JSON.stringify(logs.get(page)), contentType: 'application/json' });
  55  |   expect(logs.get(page)).toEqual({ errors: [], external: [] });
  56  | });
  57  | 
  58  | test('transport arrival gates processing and never duplicates facility inventory', async ({ page, request }) => {
  59  |   await page.getByRole('button', { name: '2D 공정', exact: true }).click();
  60  |   const states: World['production'][] = [];
  61  |   for (let tick = 0; tick <= 24; tick++) {
  62  |     const state = tick === 0 ? await getWorld(request) : await clickCommand(page, 'Advance one step', 'step');
  63  |     expect(state.simulation.tick).toBe(tick); states.push(state.production);
  64  |     expect(state.production.total_mass_kg).toBe(198000);
  65  |     for (const batch of state.production.batches) {
  66  |       const active = state.production.transports.filter(leg => leg.batch_id === batch.id && leg.status === 'in_transit');
  67  |       const facilities = state.production.stages.filter(stage => stage.batch_ids.includes(batch.id));
  68  |       expect(active.length).toBeLessThanOrEqual(1);
  69  |       if (active[0]) {
  70  |         expect(batch.status).toBe('in_transit'); expect(batch.active_transport_id).toBe(active[0].id);
  71  |         expect(batch.current_location_id).toBe(active[0].vehicle_id); expect(facilities).toEqual([]);
  72  |         expect([active[0].material_id, active[0].material_form, active[0].mass_kg]).toEqual([batch.material_id, batch.material_form, batch.mass_kg]);
  73  |         expect(batch.steps.filter(step => step.status === 'running')).toEqual([]);
  74  |       } else {
  75  |         expect(batch.active_transport_id).toBeNull(); expect(facilities).toHaveLength(1);
  76  |         expect(batch.current_location_id).toBe(facilities[0]?.id);
  77  |       }
  78  |       for (let index = 1; index < batch.steps.length; index++) {
  79  |         const previous = batch.steps[index - 1]!; const next = batch.steps[index]!;
  80  |         expect(next.start_tick - previous.end_tick).toBe(previous.stage_id === next.stage_id ? 0 : 1);
  81  |       }
  82  |     }
  83  |   }
  84  |   const gi6 = states[6]!.batches.find(batch => batch.id === 'PROD-GI')!;
  85  |   const leg = states[6]!.transports.find(item => item.id === gi6.active_transport_id)!;
  86  |   expect({ from: leg.from_stage, to: leg.to_stage, start: leg.start_tick, end: leg.end_tick, cargo: leg.material_form, mass: leg.mass_kg, kind: leg.vehicle_kind }).toEqual({ from: 'hot_rolling', to: 'cold_rolling', start: 6, end: 7, cargo: 'HR', mass: 23000, kind: 'flatbed_truck' });
  87  |   expect(gi6.steps.filter(step => step.stage_id === 'cold_rolling').map(step => step.status)).toEqual(['queued', 'queued', 'queued']);
  88  |   const gi7 = states[7]!.batches.find(batch => batch.id === 'PROD-GI')!;
  89  |   expect([gi7.status, gi7.current_location_id, gi7.equipment_id]).toEqual(['running', 'cold_rolling', 'PICKLE-01']);
  90  |   expect(states[7]!.transports.find(item => item.id === leg.id)?.status).toBe('completed');
  91  |   expect(states[24]!.completed_mass_kg).toBe(198000);
  92  |   await save('timeline', states);
  93  |   await clickCommand(page, 'Reset simulation', 'reset');
  94  |   for (let tick = 0; tick <= 7; tick++) {
  95  |     const replay = tick === 0 ? await getWorld(request) : await clickCommand(page, 'Advance one step', 'step');
  96  |     expect(replay.production).toEqual(states[tick]);
  97  |   }
  98  |   await save('replay', { matchedTicks: [0, 1, 2, 3, 4, 5, 6, 7], result: 'exact production equality' });
  99  | });
  100 | 
  101 | test('loaded 3D truck is selectable, moves, freezes on pause, resumes and resets', async ({ page, request }) => {
  102 |   const canvas = page.locator('canvas'); await expect(canvas).toBeVisible(); await page.waitForTimeout(700);
  103 |   await capture(page, 'overview-specialist-carriers');
  104 |   const box = await canvas.boundingBox(); if (!box) throw new Error('Missing canvas');
  105 |   // HGI at tick 0 is halfway from casting to hot rolling at world x=8,z=0.
  106 |   const camera = new OrthographicCamera(-box.width / 2, box.width / 2, box.height / 2, -box.height / 2, 0.1, 150);
  107 |   camera.position.set(35, 34, 42); camera.zoom = Math.min(box.width / 42, box.height / 29); camera.lookAt(0, 0, 0); camera.updateProjectionMatrix(); camera.updateMatrixWorld();
  108 |   const projected = new Vector3(8, 0.9, 0).project(camera);
  109 |   await page.mouse.click(box.x + (projected.x + 1) * box.width / 2, box.y + (1 - projected.y) * box.height / 2);
> 110 |   await expect(inspector(page)).toContainText('PROD-HGI');
      |                                 ^ Error: expect(locator).toContainText(expected) failed
  111 |   await expect(inspector(page)).toContainText('운송 중');
  112 |   await page.getByLabel('제품 경로', { exact: true }).selectOption('HGI');
  113 |   await page.getByRole('navigation', { name: '생산 공정 선택' }).getByRole('button', { name: /열연/ }).click();
  114 |   await canvas.scrollIntoViewIfNeeded(); await page.waitForTimeout(400);
  115 |   const initial = await capture(page, 'truck-loaded-paused');
  116 |   const initialWorld = await getWorld(request);
  117 |   await clickCommand(page, 'Play simulation', 'play');
  118 |   await page.waitForTimeout(60);
  119 |   const paused = await clickCommand(page, 'Pause simulation', 'pause');
  120 |   expect(paused.simulation.tick).toBe(initialWorld.simulation.tick);
  121 |   const moved = await capture(page, 'truck-moved-paused');
  122 |   const movingDiff = await difference(page, initial, moved); expect(movingDiff.count).toBeGreaterThan(50);
  123 |   await page.waitForTimeout(650);
  124 |   const frozen = await capture(page, 'truck-frozen');
  125 |   const pausedDiff = await difference(page, moved, frozen); expect(pausedDiff.count).toBe(0);
  126 |   expect((await getWorld(request)).simulation.tick).toBe(paused.simulation.tick);
  127 |   await page.getByLabel('Simulation speed', { exact: true }).selectOption('2');
  128 |   await clickCommand(page, 'Play simulation', 'play');
  129 |   await expect.poll(async () => (await getWorld(request)).simulation.tick).toBeGreaterThan(paused.simulation.tick);
  130 |   const resumed = await clickCommand(page, 'Pause simulation', 'pause'); expect(resumed.simulation.speed).toBe(2);
  131 |   await capture(page, 'truck-resumed-arrival');
  132 |   await clickCommand(page, 'Reset simulation', 'reset');
  133 |   expect((await getWorld(request)).production).toEqual(initialWorld.production);
  134 |   await page.waitForTimeout(250);
  135 |   const reset = await capture(page, 'truck-reset');
  136 |   const resetDiff = await difference(page, initial, reset); expect(resetDiff.count).toBe(0);
  137 |   await save('canvas-pixel-evidence', { movingDiff, pausedDiff, resetDiff, beforeTick: initialWorld.simulation.tick, pausedTick: paused.simulation.tick, resumedTick: resumed.simulation.tick, selectionClick: { x: projected.x, y: projected.y } });
  138 | });
  139 | 
  140 | test('390px 2D transport tracking survives WebGL loss and permits arrival navigation', async ({ page }) => {
  141 |   await page.setViewportSize({ width: 390, height: 844 });
  142 |   const canvas = page.locator('canvas'); await expect(canvas).toBeVisible(); await page.waitForTimeout(400);
  143 |   expect(await canvas.evaluate(element => {
  144 |     const extension = (element as HTMLCanvasElement).getContext('webgl2')?.getExtension('WEBGL_lose_context');
  145 |     if (!extension) return false; extension.loseContext(); return true;
  146 |   })).toBe(true);
  147 |   await page.getByRole('button', { name: '생산 목록 열기', exact: true }).click();
  148 |   await expect(page.getByRole('button', { name: '2D 공정', exact: true })).toHaveAttribute('aria-pressed', 'true');
  149 |   const transportTable = page.getByRole('region', { name: '생산 운송 표', exact: true });
  150 |   await transportTable.getByRole('button', { name: 'VEHICLE-HGI-flatbed_truck 적재 소재 선택', exact: true }).click();
  151 |   await expect(inspector(page)).toContainText('PROD-HGI');
  152 |   await page.getByLabel('제품 경로', { exact: true }).selectOption('HGI');
  153 |   await expect(transportTable.getByRole('row')).toHaveCount(2);
  154 |   await expect(transportTable.getByRole('row').last()).toContainText('26 t');
  155 |   await expect(inspector(page)).toContainText('VEHICLE-HGI-flatbed_truck');
  156 |   await expect(inspector(page)).toContainText('운송 중');
  157 |   await page.screenshot({ path: `${evidence}/transport-mobile-fallback.png`, fullPage: true });
  158 |   const layout = await page.evaluate(() => ({ width: innerWidth, document: document.documentElement.scrollWidth }));
  159 |   expect(layout.document).toBeLessThanOrEqual(layout.width); await save('mobile-layout', layout);
  160 |   await inspector(page).getByRole('button', { name: /도착/ }).click();
  161 |   await expect(page.getByRole('heading', { name: '열연 공정', exact: true })).toBeVisible();
  162 |   await clickCommand(page, 'Advance one step', 'step');
  163 |   await expect(inspector(page)).not.toContainText('운송 중');
  164 |   await expect(inspector(page)).toContainText('현재 공정 · 열연');
  165 |   await page.screenshot({ path: `${evidence}/transport-mobile-arrived.png`, fullPage: true });
  166 | });
  167 | 
  168 | 
  169 | test('reduced motion holds loaded transport still between authoritative ticks', async ({ page, request }) => {
  170 |   await page.emulateMedia({ reducedMotion: 'reduce' });
  171 |   await page.getByLabel('제품 경로', { exact: true }).selectOption('HGI');
  172 |   const canvas = page.locator('canvas'); await expect(canvas).toBeVisible(); await canvas.scrollIntoViewIfNeeded();
  173 |   await page.waitForTimeout(500);
  174 |   const before = await capture(page, 'reduced-before');
  175 |   const beforeWorld = await getWorld(request);
  176 |   await clickCommand(page, 'Play simulation', 'play');
  177 |   await page.waitForTimeout(100);
  178 |   const paused = await clickCommand(page, 'Pause simulation', 'pause');
  179 |   expect(paused.simulation.tick).toBe(beforeWorld.simulation.tick);
  180 |   const after = await capture(page, 'reduced-after');
  181 |   const reducedDiff = await difference(page, before, after); expect(reducedDiff.count).toBe(0);
  182 |   await clickCommand(page, 'Advance one step', 'step');
  183 |   const arrived = await capture(page, 'reduced-arrival');
  184 |   const arrivalDiff = await difference(page, after, arrived); expect(arrivalDiff.count).toBeGreaterThan(50);
  185 |   await save('reduced-motion', { reducedDiff, arrivalDiff, tick: paused.simulation.tick });
  186 | });
  187 | 
```