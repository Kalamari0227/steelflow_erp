# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: journey.spec.ts >> 390px keyboard controls and WebGL loss preserve complete 2D tracking
- Location: tests/journey.spec.ts:155:1

# Error details

```
Error: expect(locator).toHaveAttribute(expected) failed

Locator:  getByRole('navigation', { name: '제품 제조 단계' }).getByRole('button').nth(4)
Expected: "true"
Received: "false"
Timeout:  10000ms

Call log:
  - Expect "toHaveAttribute" getByRole('navigation', { name: '제품 제조 단계' }).getByRole('button').nth(4) with timeout 10000ms
  - waiting for getByRole('navigation', { name: '제품 제조 단계' }).getByRole('button').nth(4)
    24 × locator resolved to <button aria-pressed="false">…</button>
       - unexpected value "false"

```

```yaml
- button "05 VAF 대기":
  - text: "05"
  - strong: VAF
  - text: 대기
```

# Test source

```ts
  65  |   await expect(page.getByRole('heading', { name: '소재에서 제품까지', exact: true })).toBeVisible();
  66  |   await expect(page.getByRole('navigation', { name: '제품군 선택' }).getByRole('button')).toHaveCount(8);
  67  | });
  68  | test.afterEach(async ({ page }, info) => {
  69  |   await info.attach('journey-browser-health', { body: JSON.stringify(health.get(page)), contentType: 'application/json' });
  70  |   expect(health.get(page)).toEqual({ errors: [], external: [] });
  71  | });
  72  | 
  73  | test('all 17 routes complete their exact forms with one stable lineage and no early transformations', async ({ page, request }) => {
  74  |   test.setTimeout(120_000);
  75  |   await page.getByRole('button', { name: '2D', exact: true }).click();
  76  |   const catalogResponse = await request.get('/api/v1/journey/products'); expect(catalogResponse.ok()).toBe(true);
  77  |   const catalog = JourneyCatalogSchema.parse(await catalogResponse.json()).products;
  78  |   expect(catalog).toHaveLength(17); expect(catalog.reduce((total, product) => total + product.steps.length, 0)).toBe(187);
  79  |   const results: Record<string, JourneySnapshot[]> = {};
  80  |   for (const [id, family, input, output, count] of expectedRoutes) {
  81  |     const definition = catalog.find(item => item.id === id)!;
  82  |     expect([definition.family, definition.input_form, definition.output_form, definition.steps.length]).toEqual([family, input, output, count]);
  83  |     const initial = await select(page, id, family); const mass = id.startsWith('ti-') ? 12000 : 20000;
  84  |     expect(initial.material).toMatchObject({ lineage_id: `MATERIAL-${id}`, form: input, mass_kg: mass, role: 'feedstock', parent_version_id: null });
  85  |     await expect(page.getByRole('navigation', { name: '제품 제조 단계' }).getByRole('button')).toHaveCount(count);
  86  |     await command(page, '재생', 'play'); await page.waitForTimeout(160);
  87  |     const partial = await command(page, '일시정지', 'pause');
  88  |     expect(partial.elapsed_ms).toBeGreaterThan(0); expect(partial.elapsed_ms).toBeLessThan(4000);
  89  |     expect(partial.material.form).toBe(input); expect(partial.history).toHaveLength(1);
  90  |     results[id] = [initial, partial]; let previous = initial;
  91  |     for (let index = 0; index < count; index++) {
  92  |       const next = await command(page, '다음 단계', 'step'); results[id]!.push(next);
  93  |       expect(next.material.lineage_id).toBe(initial.material.lineage_id); expect(next.material.mass_kg).toBe(mass);
  94  |       expect(next.material.form).toBe(definition.steps[index]!.output_form);
  95  |       expect(next.material.parent_version_id).toBe(previous.material.version_id);
  96  |       expect(next.history).toHaveLength(index + 2); expect(next.history.at(-1)?.at_ms).toBe(next.elapsed_ms);
  97  |       expect(next.material.role).toBe(index === count - 1 ? 'sale_product' : 'feedstock');
  98  |       expect(next.completed).toBe(index === count - 1);
  99  |       if (!next.completed) expect(next.active_step_id).toBe(definition.steps[index + 1]!.id);
  100 |       previous = next;
  101 |     }
  102 |     expect(previous.material.form).toBe(output); expect(previous.elapsed_ms).toBe(previous.duration_ms);
  103 |     await expect(passport(page)).toContainText(output); await expect(passport(page)).toContainText('완성 제품');
  104 |     await expect(page.getByRole('button', { name: '재생', exact: true })).toBeDisabled();
  105 |     await expect(page.getByRole('button', { name: '다음 단계', exact: true })).toBeDisabled();
  106 |     const replay = await command(page, '처음부터', 'reset');
  107 |     expect(replay.material).toEqual(initial.material); expect(replay.history).toEqual(initial.history); expect(replay.run_id).not.toBe(initial.run_id);
  108 |   }
  109 |   await save('all-route-snapshots', results);
  110 | });
  111 | 
  112 | test('all eight product families render distinct selectable 3D miniatures', async ({ page }) => {
  113 |   const families = expectedRoutes.filter((item, index, all) => all.findIndex(other => other[1] === item[1]) === index);
  114 |   for (const [id, family] of families) {
  115 |     await select(page, id, family); await page.getByLabel('소재 따라가기', { exact: true }).uncheck();
  116 |     await expect(page.locator('canvas')).toBeVisible(); await page.waitForTimeout(200);
  117 |     await capture(page, `family-${id}`);
  118 |     const steps = page.getByRole('navigation', { name: '제품 제조 단계' });
  119 |     await steps.getByRole('button').nth(1).click();
  120 |     await expect(steps.getByRole('button').nth(1)).toHaveAttribute('aria-pressed', 'true');
  121 |     await expect(page.getByRole('region', { name: '선택 공정 설명' })).toContainText('선택한 설비');
  122 |     await capture(page, `family-${id}-detail`);
  123 |   }
  124 | });
  125 | 
  126 | test('real material and equipment meshes select and motion freezes, resumes at speed and resets', async ({ page, request }) => {
  127 |   const canvas = page.locator('canvas'); await expect(canvas).toBeVisible();
  128 |   await page.getByLabel('소재 따라가기', { exact: true }).uncheck(); await page.waitForTimeout(500);
  129 |   await canvas.scrollIntoViewIfNeeded();
  130 |   const box = await canvas.boundingBox(); if (!box) throw new Error('Missing canvas bounds');
  131 |   const camera = new OrthographicCamera(-box.width / 2, box.width / 2, box.height / 2, -box.height / 2, .1, 200);
  132 |   camera.position.set(13, 24, 29); camera.zoom = Math.min(box.width / 39.9, box.height / 18.02); camera.lookAt(0, 0, 0); camera.updateProjectionMatrix(); camera.updateMatrixWorld();
  133 |   const clickWorld = async (x: number, y: number, z: number) => { const p = new Vector3(x, y, z).project(camera); await page.mouse.click(box.x + (p.x + 1) * box.width / 2, box.y + (1 - p.y) * box.height / 2); };
  134 |   await clickWorld(-15, 1.06, -4); await expect(passport(page)).toBeFocused();
  135 |   await page.getByRole('button', { name: '전체 보기', exact: true }).click();
  136 |   await clickWorld(-6, 2.7, -4);
  137 |   await expect(page.getByRole('navigation', { name: '제품 제조 단계' }).getByRole('button').nth(1)).toHaveAttribute('aria-pressed', 'true');
  138 |   await page.getByRole('button', { name: '전체 보기', exact: true }).click();
  139 |   const baseline = await capture(page, 'motion-baseline'); const initial = await snapshot(request);
  140 |   await command(page, '다음 단계', 'step'); await command(page, '다음 단계', 'step');
  141 |   expect((await snapshot(request)).material.form).toBe('HOT_SLAB');
  142 |   const before = await capture(page, 'motion-before');
  143 |   await command(page, '재생', 'play'); await page.waitForTimeout(550);
  144 |   const paused = await command(page, '일시정지', 'pause'); expect(paused.active_step_id).toBe('hr-03'); expect(paused.material.form).toBe('HOT_SLAB');
  145 |   const moved = await capture(page, 'motion-moved'); const movement = await diff(page, before, moved); expect(movement.count).toBeGreaterThan(50);
  146 |   await page.waitForTimeout(600); const frozen = await capture(page, 'motion-frozen'); const pause = await diff(page, moved, frozen); expect(pause.count).toBe(0);
  147 |   expect((await snapshot(request)).elapsed_ms).toBe(paused.elapsed_ms);
  148 |   await command(page, '4×', 'speed'); await command(page, '재생', 'play'); await page.waitForTimeout(500);
  149 |   const resumed = await command(page, '일시정지', 'pause'); expect(resumed.speed).toBe(4); expect(resumed.elapsed_ms - paused.elapsed_ms).toBeGreaterThanOrEqual(1600);
  150 |   const reset = await command(page, '처음부터', 'reset'); expect(reset.material).toEqual(initial.material); expect(reset.elapsed_ms).toBe(0);
  151 |   const resetImage = await capture(page, 'motion-reset'); const resetDiff = await diff(page, baseline, resetImage); expect(resetDiff.count).toBe(0);
  152 |   await save('motion', { movement, pause, resetDiff, paused, resumed });
  153 | });
  154 | 
  155 | test('390px keyboard controls and WebGL loss preserve complete 2D tracking', async ({ page }) => {
  156 |   await page.setViewportSize({ width: 390, height: 844 }); await expect(page.locator('canvas')).toBeVisible(); await page.waitForTimeout(300);
  157 |   expect(await page.locator('canvas').evaluate(element => { const extension = (element as HTMLCanvasElement).getContext('webgl2')?.getExtension('WEBGL_lose_context'); if (!extension) return false; extension.loseContext(); return true; })).toBe(true);
  158 |   await page.getByRole('button', { name: '2D 공정 보기', exact: true }).click();
  159 |   await expect(page.getByRole('region', { name: '2D 제품 제조 공정' })).toBeVisible();
  160 |   const titanium = page.getByRole('navigation', { name: '제품군 선택' }).getByRole('button', { name: '티타늄', exact: true });
  161 |   await titanium.focus(); await page.keyboard.press('Enter');
  162 |   await expect(page.getByLabel('제조 경로', { exact: true })).toHaveValue('ti-hr');
  163 |   await page.getByLabel('제조 경로', { exact: true }).selectOption('ti-sheet');
  164 |   const stage = page.getByRole('navigation', { name: '제품 제조 단계' }).getByRole('button').nth(4);
> 165 |   await stage.focus(); await page.keyboard.press('Enter'); await expect(stage).toHaveAttribute('aria-pressed', 'true');
      |                                                                                ^ Error: expect(locator).toHaveAttribute(expected) failed
  166 |   await expect(page.getByRole('region', { name: '선택 공정 설명' })).toContainText('진공');
  167 |   await command(page, '다음 단계', 'step'); await expect(passport(page)).toContainText('MATERIAL-ti-sheet:1');
  168 |   const layout = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth })); expect(layout.document).toBeLessThanOrEqual(layout.viewport);
  169 |   await page.screenshot({ path: `${evidence}/journey-mobile-fallback.png`, fullPage: true }); await save('mobile-layout', layout);
  170 | });
  171 | 
  172 | test('connection failure freezes the actual scene and retry restores authoritative state', async ({ page, request }) => {
  173 |   await page.getByLabel('소재 따라가기', { exact: true }).uncheck(); await expect(page.locator('canvas')).toBeVisible();
  174 |   await command(page, '재생', 'play'); await page.waitForTimeout(250);
  175 |   await page.route('**/api/v1/journey', route => route.abort('failed'));
  176 |   await expect(page.getByRole('alert').filter({ hasText: '재생 화면은 멈춰 있습니다' })).toBeVisible();
  177 |   await expect(page.getByRole('button', { name: '일시정지', exact: true })).toBeDisabled();
  178 |   const first = await capture(page, 'failure-frozen-first'); await page.waitForTimeout(550); const second = await capture(page, 'failure-frozen-second');
  179 |   const frozen = await diff(page, first, second); expect(frozen.count).toBe(0);
  180 |   const paused = await request.post('/api/v1/journey/pause'); expect(paused.ok()).toBe(true);
  181 |   await page.unroute('**/api/v1/journey'); await page.getByRole('button', { name: '다시 연결', exact: true }).click();
  182 |   await expect(page.getByRole('alert').filter({ hasText: '재생 화면은 멈춰 있습니다' })).toHaveCount(0);
  183 |   await expect(page.getByRole('button', { name: '재생', exact: true })).toBeEnabled();
  184 |   await save('failure-freeze', frozen);
  185 | });
  186 | 
  187 | test('reduced motion does not interpolate while real snapshot reads are delayed', async ({ page, request }) => {
  188 |   await page.emulateMedia({ reducedMotion: 'reduce' }); await page.getByLabel('소재 따라가기', { exact: true }).uncheck();
  189 |   await expect(page.locator('canvas')).toBeVisible();
  190 |   let release: (() => void) | undefined; const gate = new Promise<void>(resolve => { release = resolve; });
  191 |   await page.route('**/api/v1/journey', async route => { await gate; await route.continue(); });
  192 |   try {
  193 |     await command(page, '재생', 'play'); const first = await capture(page, 'reduced-first');
  194 |     await page.waitForTimeout(500); const second = await capture(page, 'reduced-second'); const frozen = await diff(page, first, second); expect(frozen.count).toBe(0);
  195 |     expect((await snapshot(request)).elapsed_ms).toBeGreaterThan(0);
  196 |     release?.(); await page.unroute('**/api/v1/journey');
  197 |     await command(page, '일시정지', 'pause');
  198 |     const arrived = await capture(page, 'reduced-authoritative'); const changed = await diff(page, second, arrived); expect(changed.count).toBeGreaterThan(50);
  199 |     await save('reduced-motion', { frozen, changed });
  200 |   } finally { release?.(); await page.unroute('**/api/v1/journey'); }
  201 | });
  202 | 
```