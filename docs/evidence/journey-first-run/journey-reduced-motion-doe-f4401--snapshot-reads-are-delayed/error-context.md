# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: journey.spec.ts >> reduced motion does not interpolate while real snapshot reads are delayed
- Location: tests/journey.spec.ts:187:1

# Error details

```
Error: route.continue: Route is already handled!
```

# Page snapshot

```yaml
- generic [ref=e3]:
  - link "Skip to operations" [ref=e4] [cursor=pointer]:
    - /url: "#main-content"
  - navigation "Main navigation" [ref=e5]:
    - link "SteelFlow home" [ref=e6] [cursor=pointer]:
      - /url: "#main-content"
    - button "Operations overview" [ref=e10] [cursor=pointer]
    - button "Inventory view" [ref=e16] [cursor=pointer]
    - button "Open orders" [ref=e27] [cursor=pointer]
    - button "Open shipments" [ref=e31] [cursor=pointer]
    - button "Open event history" [ref=e36] [cursor=pointer]
    - generic [ref=e39]:
      - button "Open demo guide" [ref=e40] [cursor=pointer]
      - generic "Local demo operator" [ref=e44]: SF
  - generic [ref=e45]:
    - banner [ref=e46]:
      - generic [ref=e47]:
        - text: SteelFlow
        - generic [ref=e48]: 3D
        - generic [ref=e50]: Operations twin
      - generic [ref=e53]:
        - generic [ref=e54]: Synthetic environment
        - generic [ref=e56]: LOCAL / V0.1
    - main [ref=e57]:
      - navigation "워크스페이스 선택" [ref=e58]:
        - button "물류 오버뷰" [ref=e59] [cursor=pointer]
        - button "생산 공정" [ref=e65] [cursor=pointer]
        - button "제품 제조공정" [pressed] [ref=e68] [cursor=pointer]
      - generic [ref=e73]:
        - generic [ref=e74]:
          - heading "소재에서 제품까지" [level=1] [ref=e75]
          - generic [ref=e76]: 합성 데이터 · 공정 시연
        - navigation "제품군 선택" [ref=e77]:
          - button "열연" [pressed] [ref=e78] [cursor=pointer]
          - button "후판" [ref=e79] [cursor=pointer]
          - button "선재" [ref=e80] [cursor=pointer]
          - button "냉연" [ref=e81] [cursor=pointer]
          - button "도금" [ref=e82] [cursor=pointer]
          - button "전기강판" [ref=e83] [cursor=pointer]
          - button "스테인리스" [ref=e84] [cursor=pointer]
          - button "티타늄" [ref=e85] [cursor=pointer]
        - generic [ref=e86]:
          - generic [ref=e87]:
            - heading "열연 코일" [level=2] [ref=e88]
            - paragraph [ref=e89]: 슬래브가 가열·압연·냉각·권취를 거쳐 열연 코일이 되는 흐름입니다.
          - generic [ref=e90]:
            - text: 제조 경로
            - combobox "제조 경로" [ref=e91] [cursor=pointer]:
              - option "열연 코일" [selected]
        - region "제품 제조 미니어처" [ref=e92]:
          - generic [ref=e93]:
            - status [ref=e94]: 공정 일시정지
            - generic [ref=e95]:
              - generic [ref=e96]:
                - checkbox "소재 따라가기" [ref=e97]
                - text: 소재 따라가기
              - button "전체 보기" [ref=e98] [cursor=pointer]
              - button "3D" [pressed] [ref=e105] [cursor=pointer]
              - button "2D" [ref=e109] [cursor=pointer]
          - generic [ref=e111]:
            - generic [ref=e113]:
              - generic "열연 코일 제조 미니어처. 소재와 설비를 선택할 수 있습니다. 드래그로 회전, 스크롤로 확대합니다." [ref=e114]
              - generic: 드래그 회전 · 휠 확대 · 설비와 소재 선택
            - navigation "제품 제조 단계" [ref=e117]:
              - list [ref=e118]:
                - listitem [ref=e119]:
                  - button "01 소재 입고 현재 단계" [ref=e120] [cursor=pointer]:
                    - generic [ref=e121]: "01"
                    - strong [ref=e122]: 소재 입고
                    - generic [ref=e123]: 현재 단계
                - listitem [ref=e124]:
                  - button "02 가열로 대기" [ref=e125] [cursor=pointer]:
                    - generic [ref=e126]: "02"
                    - strong [ref=e127]: 가열로
                    - generic [ref=e128]: 대기
                - listitem [ref=e129]:
                  - button "03 조압연 대기" [ref=e130] [cursor=pointer]:
                    - generic [ref=e131]: "03"
                    - strong [ref=e132]: 조압연
                    - generic [ref=e133]: 대기
                - listitem [ref=e134]:
                  - button "04 사상압연 대기" [ref=e135] [cursor=pointer]:
                    - generic [ref=e136]: "04"
                    - strong [ref=e137]: 사상압연
                    - generic [ref=e138]: 대기
                - listitem [ref=e139]:
                  - button "05 냉각 대기" [ref=e140] [cursor=pointer]:
                    - generic [ref=e141]: "05"
                    - strong [ref=e142]: 냉각
                    - generic [ref=e143]: 대기
                - listitem [ref=e144]:
                  - button "06 권취 대기" [ref=e145] [cursor=pointer]:
                    - generic [ref=e146]: "06"
                    - strong [ref=e147]: 권취
                    - generic [ref=e148]: 대기
                - listitem [ref=e149]:
                  - button "07 정정 대기" [ref=e150] [cursor=pointer]:
                    - generic [ref=e151]: "07"
                    - strong [ref=e152]: 정정
                    - generic [ref=e153]: 대기
                - listitem [ref=e154]:
                  - button "08 포장 대기" [ref=e155] [cursor=pointer]:
                    - generic [ref=e156]: "08"
                    - strong [ref=e157]: 포장
                    - generic [ref=e158]: 대기
                - listitem [ref=e159]:
                  - button "09 제품 출고 대기" [ref=e160] [cursor=pointer]:
                    - generic [ref=e161]: "09"
                    - strong [ref=e162]: 제품 출고
                    - generic [ref=e163]: 대기
          - generic "제품 공정 재생" [ref=e164]:
            - generic [ref=e165]:
              - button "재생" [ref=e166] [cursor=pointer]
              - button "처음부터" [ref=e169] [cursor=pointer]
              - button "다음 단계" [ref=e173] [cursor=pointer]
            - generic [ref=e176]:
              - generic [ref=e177]: 시연 시간
              - strong [ref=e178]: 0:01 / 0:45
              - progressbar "전체 공정 진행률" [ref=e179]
            - group "재생 속도" [ref=e180]:
              - button "1×" [pressed] [ref=e181] [cursor=pointer]
              - button "2×" [ref=e182] [cursor=pointer]
              - button "4×" [ref=e183] [cursor=pointer]
        - generic [ref=e184]:
          - region "선택 공정 설명" [ref=e185]:
            - text: 현재 소재가 거치는 공정
            - heading "소재 입고" [level=2] [ref=e186]
            - paragraph [ref=e187]: 선택한 합성 소재를 운반차에서 생산 라인으로 인계합니다. 공정 설명에 추가한 데모 운송 단계입니다.
            - generic [ref=e188]:
              - generic [ref=e189]: SLAB
              - strong [ref=e192]: SLAB
            - link "My POSCO · 열연 제조공정" [ref=e193] [cursor=pointer]:
              - /url: https://my.posco.com/s/exshowrmproductmain?lv1=a0uTJ000004pM0zYAE
          - region "소재 이력" [ref=e198]:
            - generic [ref=e199]:
              - heading "하나의 소재, 이어지는 이력" [level=2] [ref=e204]
              - generic [ref=e205]: 공정 소재
            - generic [ref=e206]:
              - strong [ref=e207]: SLAB
              - generic [ref=e208]: 20,000 kg
              - generic [ref=e209]: 소재 입고
            - generic [ref=e210]:
              - generic [ref=e211]:
                - term [ref=e212]: 동일 소재 ID
                - definition [ref=e213]: MATERIAL-hr
              - generic [ref=e214]:
                - term [ref=e215]: 현재 버전
                - definition [ref=e216]: MATERIAL-hr:0
              - generic [ref=e217]:
                - term [ref=e218]: 이전 버전
                - definition [ref=e219]: 최초 투입 소재
            - region "소재 변환 이력" [ref=e220]:
              - list [ref=e221]:
                - listitem [ref=e222]:
                  - generic [ref=e225]:
                    - strong [ref=e226]: SLAB
                    - generic [ref=e227]: MATERIAL-hr:0
        - paragraph [ref=e228]: 공개된 제품 제조 흐름을 바탕으로 재구성한 미니어처입니다. 시간과 질량은 설명용 합성 데이터이며, 실제 생산 속도·설비 제어와 연결되지 않습니다. 소재의 이동과 변환은 로컬 서버가 결정합니다.
```

# Test source

```ts
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
  165 |   await stage.focus(); await page.keyboard.press('Enter'); await expect(stage).toHaveAttribute('aria-pressed', 'true');
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
> 191 |   await page.route('**/api/v1/journey', async route => { await gate; await route.continue(); });
      |                                                                                          ^ Error: route.continue: Route is already handled!
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