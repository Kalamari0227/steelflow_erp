# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: transport.spec.ts >> 390px 2D transport tracking survives WebGL loss and permits arrival navigation
- Location: tests/transport.spec.ts:167:1

# Error details

```
Error: expect(locator).toContainText(expected) failed

Locator: getByRole('complementary', { name: '선택 소재 상세' })
Expected substring: "현재 공정 · 열연"
Received string:    "소재 추적PROD-GICURRENT MATERIAL용강후공정 소재목표 제품GI · 용융아연배치 질량23 t작업 상태작업 중현재 공정 · 연주다음 공정 · 열연소재 변환 이력 3철원료소재 · 제선·출선MAT-PROD-GI:00용선소재 · 제선·출선MAT-PROD-GI:01용강소재 · 제강·출강MAT-PROD-GI:02형태와 용도는 별개입니다. 같은 열연·냉연 코일도 생산 경로에 따라 판매 제품 또는 다음 공정의 소재가 됩니다."
Timeout: 10000ms

Call log:
  - Expect "toContainText" getByRole('complementary', { name: '선택 소재 상세' }) with timeout 10000ms
  - waiting for getByRole('complementary', { name: '선택 소재 상세' })
    24 × locator resolved to <aside aria-label="선택 소재 상세" class="production-inspector panel">…</aside>
       - unexpected value "소재 추적PROD-GICURRENT MATERIAL용강후공정 소재목표 제품GI · 용융아연배치 질량23 t작업 상태작업 중현재 공정 · 연주다음 공정 · 열연소재 변환 이력 3철원료소재 · 제선·출선MAT-PROD-GI:00용선소재 · 제선·출선MAT-PROD-GI:01용강소재 · 제강·출강MAT-PROD-GI:02형태와 용도는 별개입니다. 같은 열연·냉연 코일도 생산 경로에 따라 판매 제품 또는 다음 공정의 소재가 됩니다."

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
  - strong: 작업 중
  - button "현재 공정 · 연주":
    - text: 현재 공정 · 연주
    - img
  - paragraph: 다음 공정 · 열연
  - heading "소재 변환 이력 3" [level=3]
  - list "소재 계보":
    - listitem:
      - strong: 철원료
      - text: 소재 · 제선·출선 MAT-PROD-GI:00
    - listitem:
      - strong: 용선
      - text: 소재 · 제선·출선 MAT-PROD-GI:01
    - listitem:
      - img
      - strong: 용강
      - text: 소재 · 제강·출강 MAT-PROD-GI:02
  - paragraph: 형태와 용도는 별개입니다. 같은 열연·냉연 코일도 생산 경로에 따라 판매 제품 또는 다음 공정의 소재가 됩니다.
```

# Test source

```ts
  92  |         expect(batch.active_transport_id).toBeNull(); expect(facilities).toHaveLength(1);
  93  |         expect(batch.current_location_id).toBe(facilities[0]?.id);
  94  |       }
  95  |       for (let index = 1; index < batch.steps.length; index++) {
  96  |         const previous = batch.steps[index - 1]!; const next = batch.steps[index]!;
  97  |         expect(next.start_tick - previous.end_tick).toBe(previous.stage_id === next.stage_id ? 0 : 1);
  98  |       }
  99  |     }
  100 |   }
  101 |   const gi6 = states[6]!.batches.find(batch => batch.id === 'PROD-GI')!;
  102 |   const leg = states[6]!.transports.find(item => item.id === gi6.active_transport_id)!;
  103 |   expect({ from: leg.from_stage, to: leg.to_stage, start: leg.start_tick, end: leg.end_tick, cargo: leg.material_form, mass: leg.mass_kg, kind: leg.vehicle_kind }).toEqual({ from: 'hot_rolling', to: 'cold_rolling', start: 6, end: 7, cargo: 'HR', mass: 23000, kind: 'flatbed_truck' });
  104 |   expect(gi6.steps.filter(step => step.stage_id === 'cold_rolling').map(step => step.status)).toEqual(['queued', 'queued', 'queued']);
  105 |   const gi7 = states[7]!.batches.find(batch => batch.id === 'PROD-GI')!;
  106 |   expect([gi7.status, gi7.current_location_id, gi7.equipment_id]).toEqual(['running', 'cold_rolling', 'PICKLE-01']);
  107 |   expect(states[7]!.transports.find(item => item.id === leg.id)?.status).toBe('completed');
  108 |   expect(states[24]!.completed_mass_kg).toBe(198000);
  109 |   await save('timeline', states);
  110 |   await clickCommand(page, 'Reset simulation', 'reset');
  111 |   for (let tick = 0; tick <= 7; tick++) {
  112 |     const replay = tick === 0 ? await getWorld(request) : await clickCommand(page, 'Advance one step', 'step');
  113 |     expect(replay.production).toEqual(states[tick]);
  114 |   }
  115 |   await save('replay', { matchedTicks: [0, 1, 2, 3, 4, 5, 6, 7], result: 'exact production equality' });
  116 | });
  117 | 
  118 | test('loaded 3D truck is selectable, moves, freezes on pause, resumes and resets', async ({ page, request }) => {
  119 |   const canvas = page.locator('canvas'); await expect(canvas).toBeVisible(); await page.waitForTimeout(700);
  120 |   await capture(page, 'overview-specialist-carriers');
  121 |   const overviewBox = await canvas.boundingBox(); if (!overviewBox) throw new Error('Missing overview canvas');
  122 |   const overviewCamera = new OrthographicCamera(-overviewBox.width / 2, overviewBox.width / 2, overviewBox.height / 2, -overviewBox.height / 2, 0.1, 150);
  123 |   overviewCamera.position.set(35, 34, 42); overviewCamera.zoom = Math.min(overviewBox.width / 42, overviewBox.height / 29);
  124 |   overviewCamera.lookAt(0, 0, 0); overviewCamera.updateProjectionMatrix(); overviewCamera.updateMatrixWorld();
  125 |   const overviewPoint = new Vector3(7.66, 0.962, 0).project(overviewCamera);
  126 |   await page.mouse.click(overviewBox.x + (overviewPoint.x + 1) * overviewBox.width / 2, overviewBox.y + (1 - overviewPoint.y) * overviewBox.height / 2);
  127 |   await expect(inspector(page)).toContainText('PROD-HGI');
  128 |   await expect(page.getByRole('heading', { name: '생산 오버뷰', exact: true })).toBeVisible();
  129 |   await capture(page, 'overview-truck-selected');
  130 |   await page.getByRole('region', { name: '생산 작업 목록' }).getByRole('button', { name: 'PROD-GI', exact: true }).click();
  131 |   await page.getByRole('navigation', { name: '생산 공정 선택' }).getByRole('button', { name: /열연/ }).click();
  132 |   await canvas.scrollIntoViewIfNeeded(); await page.waitForTimeout(300);
  133 |   const box = await canvas.boundingBox(); if (!box) throw new Error('Missing canvas');
  134 |   const camera = new OrthographicCamera(-box.width / 2, box.width / 2, box.height / 2, -box.height / 2, 0.1, 150);
  135 |   camera.position.set(15, 15, 21.3); camera.zoom = Math.min(box.width / 18, box.height / 22.6); camera.lookAt(0, 0, 3.3); camera.updateProjectionMatrix(); camera.updateMatrixWorld();
  136 |   const projected = new Vector3(-0.45, 1.215, 6.6).project(camera);
  137 |   await page.mouse.click(box.x + (projected.x + 1) * box.width / 2, box.y + (1 - projected.y) * box.height / 2);
  138 |   await expect(inspector(page)).toContainText('PROD-HGI');
  139 |   await expect(inspector(page)).toContainText('운송 중');
  140 |   await page.getByLabel('제품 경로', { exact: true }).selectOption('HGI');
  141 |   await synchronizeClock(page, request);
  142 |   const initial = await capture(page, 'truck-loaded-paused');
  143 |   const initialWorld = await getWorld(request);
  144 |   await clickCommand(page, 'Play simulation', 'play');
  145 |   await page.waitForTimeout(60);
  146 |   const paused = await clickCommand(page, 'Pause simulation', 'pause');
  147 |   expect(paused.simulation.tick).toBe(initialWorld.simulation.tick);
  148 |   const moved = await capture(page, 'truck-moved-paused');
  149 |   const movingDiff = await difference(page, initial, moved); expect(movingDiff.count).toBeGreaterThan(50);
  150 |   await page.waitForTimeout(650);
  151 |   const frozen = await capture(page, 'truck-frozen');
  152 |   const pausedDiff = await difference(page, moved, frozen); expect(pausedDiff.count).toBe(0);
  153 |   expect((await getWorld(request)).simulation.tick).toBe(paused.simulation.tick);
  154 |   await page.getByLabel('Simulation speed', { exact: true }).selectOption('2');
  155 |   await clickCommand(page, 'Play simulation', 'play');
  156 |   await expect.poll(async () => (await getWorld(request)).simulation.tick).toBeGreaterThan(paused.simulation.tick);
  157 |   const resumed = await clickCommand(page, 'Pause simulation', 'pause'); expect(resumed.simulation.speed).toBe(2);
  158 |   await capture(page, 'truck-resumed-arrival');
  159 |   await clickCommand(page, 'Reset simulation', 'reset');
  160 |   expect((await getWorld(request)).production).toEqual(initialWorld.production);
  161 |   await page.waitForTimeout(250);
  162 |   const reset = await capture(page, 'truck-reset');
  163 |   const resetDiff = await difference(page, initial, reset); expect(resetDiff.count).toBe(0);
  164 |   await save('canvas-pixel-evidence', { movingDiff, pausedDiff, resetDiff, beforeTick: initialWorld.simulation.tick, pausedTick: paused.simulation.tick, resumedTick: resumed.simulation.tick, selectionClick: { x: projected.x, y: projected.y } });
  165 | });
  166 | 
  167 | test('390px 2D transport tracking survives WebGL loss and permits arrival navigation', async ({ page }) => {
  168 |   await page.setViewportSize({ width: 390, height: 844 });
  169 |   const canvas = page.locator('canvas'); await expect(canvas).toBeVisible(); await page.waitForTimeout(400);
  170 |   expect(await canvas.evaluate(element => {
  171 |     const extension = (element as HTMLCanvasElement).getContext('webgl2')?.getExtension('WEBGL_lose_context');
  172 |     if (!extension) return false; extension.loseContext(); return true;
  173 |   })).toBe(true);
  174 |   await page.getByRole('button', { name: '생산 목록 열기', exact: true }).click();
  175 |   await expect(page.getByRole('button', { name: '2D 공정', exact: true })).toHaveAttribute('aria-pressed', 'true');
  176 |   const transportTable = page.getByRole('region', { name: '생산 운송 표', exact: true });
  177 |   await transportTable.getByRole('button', { name: 'VEHICLE-HGI-flatbed_truck 적재 소재 선택', exact: true }).click();
  178 |   await expect(inspector(page)).toContainText('PROD-HGI');
  179 |   await page.getByLabel('제품 경로', { exact: true }).selectOption('HGI');
  180 |   await expect(transportTable.getByRole('row')).toHaveCount(2);
  181 |   await expect(transportTable.getByRole('row').last()).toContainText('26 t');
  182 |   await expect(inspector(page)).toContainText('VEHICLE-HGI-flatbed_truck');
  183 |   await expect(inspector(page)).toContainText('운송 중');
  184 |   const fallbackScreenshot = await page.screenshot({ fullPage: true });
  185 |   await writeFile(`${evidence}/transport-mobile-fallback.png`, fallbackScreenshot);
  186 |   const layout = await page.evaluate(() => ({ width: innerWidth, document: document.documentElement.scrollWidth }));
  187 |   expect(layout.document).toBeLessThanOrEqual(layout.width); await save('mobile-layout', layout);
  188 |   await inspector(page).getByRole('button', { name: /도착/ }).click();
  189 |   await expect(page.getByRole('heading', { name: '열연 공정', exact: true })).toBeVisible();
  190 |   await clickCommand(page, 'Advance one step', 'step');
  191 |   await expect(inspector(page)).not.toContainText('운송 중');
> 192 |   await expect(inspector(page)).toContainText('현재 공정 · 열연');
      |                                 ^ Error: expect(locator).toContainText(expected) failed
  193 |   await page.screenshot({ path: `${evidence}/transport-mobile-arrived.png`, fullPage: true });
  194 |   await writeFile(`${evidence}/transport-mobile-fallback.png`, fallbackScreenshot);
  195 |   await save('mobile-layout', layout);
  196 | });
  197 | 
  198 | 
  199 | test('reduced motion holds loaded transport still between authoritative ticks', async ({ page, request }) => {
  200 |   await page.emulateMedia({ reducedMotion: 'reduce' });
  201 |   await page.getByLabel('제품 경로', { exact: true }).selectOption('HGI');
  202 |   const canvas = page.locator('canvas'); await expect(canvas).toBeVisible(); await canvas.scrollIntoViewIfNeeded();
  203 |   await page.waitForTimeout(500);
  204 |   await synchronizeClock(page, request);
  205 |   const before = await capture(page, 'reduced-before');
  206 |   const beforeWorld = await getWorld(request);
  207 |   await clickCommand(page, 'Play simulation', 'play');
  208 |   await page.waitForTimeout(100);
  209 |   const paused = await clickCommand(page, 'Pause simulation', 'pause');
  210 |   expect(paused.simulation.tick).toBe(beforeWorld.simulation.tick);
  211 |   const after = await capture(page, 'reduced-after');
  212 |   const reducedDiff = await difference(page, before, after); expect(reducedDiff.count).toBe(0);
  213 |   await clickCommand(page, 'Advance one step', 'step');
  214 |   const arrived = await capture(page, 'reduced-arrival');
  215 |   const arrivalDiff = await difference(page, after, arrived); expect(arrivalDiff.count).toBeGreaterThan(50);
  216 |   await save('reduced-motion', { reducedDiff, arrivalDiff, tick: paused.simulation.tick });
  217 | });
  218 | 
```