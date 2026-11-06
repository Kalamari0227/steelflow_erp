# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: production.spec.ts >> production WebGL context loss recovers to fully usable 2D stages and material selection
- Location: tests/production.spec.ts:165:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText('3D production view unavailable', { exact: true })
Expected: visible
Timeout: 10000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByText('3D production view unavailable', { exact: true }) with timeout 10000ms
  - waiting for getByText('3D production view unavailable', { exact: true })

```

```yaml
- link "Skip to operations":
  - /url: "#main-content"
- navigation "Main navigation":
  - link "SteelFlow home":
    - /url: "#main-content"
    - img
  - button "Operations overview":
    - img
  - button "Inventory view":
    - img
  - button "Open orders":
    - img
  - button "Open shipments":
    - img
  - button "Open event history":
    - img
  - button "Open demo guide":
    - img
  - text: SF
- banner:
  - text: SteelFlow 3D Operations twin
  - img
  - text: Synthetic environment LOCAL / V0.1
- main:
  - navigation "워크스페이스 선택":
    - button "물류 오버뷰":
      - img
      - text: 물류 오버뷰
    - button "생산 공정" [pressed]:
      - img
      - text: 생산 공정
  - button "생산 오버뷰"
  - heading "생산 오버뷰" [level=1]
  - paragraph: 소재가 제품이 되는 과정. 공정을 선택해 작업 흐름 안으로 들어가세요.
  - text: 합성 생산 시나리오
  - img
  - text: 진행 중
  - strong: 9배치
  - img
  - text: 생산 완료
  - strong: 0/ 9
  - img
  - text: 생산 배치 총량
  - strong: 198t
  - img
  - text: 제품 경로
  - strong: 9종
  - img
  - strong: 통합 생산 공정
  - text: 제선에서 제품 재고까지 제품 경로
  - combobox "제품 경로":
    - option "전체 제품" [selected]
    - option "슬래브"
    - option "블룸"
    - option "빌렛"
    - option "열연"
    - option "냉연"
    - option "GI · 용융아연"
    - option "GA · 합금화아연"
    - option "EG · 전기아연"
    - option "HGI · 열연도금"
  - text: 시나리오
  - combobox "생산 시나리오":
    - option "정상 생산" [selected]
    - option "열연 지연"
    - option "대체 라인 회복"
  - region "생산 공정 시각화":
    - text: 전체 공장 · 서버 상태 연결
    - button "3D 공정" [pressed]:
      - img
      - text: 3D 공정
    - button "2D 공정":
      - img
      - text: 2D 공정
    - button "생산 카메라 초기화":
      - img
    - text: 공정을 클릭해 상세 화면으로 이동 드래그 회전 · 스크롤 확대
    - navigation "생산 공정 선택":
      - button "01 제선·출선 2 작업 중":
        - text: "01"
        - strong: 제선·출선
        - text: 2 작업 중
      - button "02 제강·출강 2 작업 중":
        - text: "02"
        - strong: 제강·출강
        - text: 2 작업 중
      - button "03 연주 2 작업 중":
        - text: "03"
        - strong: 연주
        - text: 2 작업 중
      - button "04 열연 2 작업 중":
        - text: "04"
        - strong: 열연
        - text: 2 작업 중
      - button "05 냉연 현재 작업 없음":
        - text: "05"
        - strong: 냉연
        - text: 현재 작업 없음
      - button "06 도금 1 작업 중":
        - text: "06"
        - strong: 도금
        - text: 1 작업 중
      - button "07 정정·검사 현재 작업 없음":
        - text: "07"
        - strong: 정정·검사
        - text: 현재 작업 없음
      - button "08 제품 재고 현재 작업 없음":
        - text: "08"
        - strong: 제품 재고
        - text: 현재 작업 없음
    - button "Play simulation":
      - img
      - text: Play
    - button "Advance one step":
      - img
    - button "Reset simulation":
      - img
    - text: Simulation speed
    - combobox "Simulation speed":
      - option "1× speed" [selected]
      - option "2× speed"
      - option "4× speed"
    - text: 08:00 UTC Step 0 / 24
    - progressbar "Simulation progress"
    - text: Paused
  - complementary "선택 소재 상세":
    - img
    - text: 소재 추적 PROD-GI CURRENT MATERIAL
    - heading "슬래브" [level=2]
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
    - heading "소재 변환 이력 4" [level=3]
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
        - strong: 용강
        - text: 소재 · 제강·출강 MAT-PROD-GI:02
        - img
      - listitem:
        - img
        - strong: 슬래브
        - text: 소재 · 연주 MAT-PROD-GI:03
    - paragraph: 형태와 용도는 별개입니다. 같은 열연·냉연 코일도 생산 경로에 따라 판매 제품 또는 다음 공정의 소재가 됩니다.
  - region "선택 배치 생산 경로":
    - text: MATERIAL ROUTE
    - strong: PROD-GI
    - list:
      - listitem:
        - button "제선·출선 · 완료":
          - img
          - text: 제선·출선 · 완료
      - listitem:
        - button "제강·출강 · 완료":
          - img
          - text: 제강·출강 · 완료
      - listitem:
        - button "연주 · 작업 중":
          - img
          - text: 연주 · 작업 중
      - listitem:
        - button "열연 · 대기":
          - img
          - text: 열연 · 대기
      - listitem:
        - button "냉연 · 대기":
          - img
          - text: 냉연 · 대기
      - listitem:
        - button "도금 · 대기":
          - img
          - text: 도금 · 대기
      - listitem:
        - button "정정·검사 · 대기":
          - img
          - text: 정정·검사 · 대기
      - listitem:
        - button "제품 재고 · 대기":
          - img
          - text: 제품 재고 · 대기
  - region "생산 작업 목록":
    - heading "전체 생산 배치" [level=2]
    - text: 9개 배치 · 198 t
    - region "생산 소재 표":
      - table "합성 생산 배치. 배치 선택으로 경로와 소재 계보를 확인합니다.":
        - caption: 합성 생산 배치. 배치 선택으로 경로와 소재 계보를 확인합니다.
        - rowgroup:
          - row "생산 배치 현재 소재 용도 목표 제품 현재 공정 질량 생산 진행":
            - columnheader "생산 배치"
            - columnheader "현재 소재"
            - columnheader "용도"
            - columnheader "목표 제품"
            - columnheader "현재 공정"
            - columnheader "질량"
            - columnheader "생산 진행"
        - rowgroup:
          - row "PROD-SLAB 철원료 MAT-PROD-SLAB:00 후공정 소재 슬래브 제선·출선 18 t 0% 0":
            - cell "PROD-SLAB":
              - button "PROD-SLAB"
            - cell "철원료 MAT-PROD-SLAB:00":
              - strong: 철원료
              - text: MAT-PROD-SLAB:00
            - cell "후공정 소재"
            - cell "슬래브"
            - cell "제선·출선"
            - cell "18 t"
            - cell "0% 0":
              - text: 0%
              - progressbar "PROD-SLAB 생산 진행률"
          - row "PROD-BLOOM 철원료 MAT-PROD-BLOOM:00 후공정 소재 블룸 제선·출선 19 t 11% 0.1111":
            - cell "PROD-BLOOM":
              - button "PROD-BLOOM"
            - cell "철원료 MAT-PROD-BLOOM:00":
              - strong: 철원료
              - text: MAT-PROD-BLOOM:00
            - cell "후공정 소재"
            - cell "블룸"
            - cell "제선·출선"
            - cell "19 t"
            - cell "11% 0.1111":
              - text: 11%
              - progressbar "PROD-BLOOM 생산 진행률"
          - row "PROD-BILLET 용선 MAT-PROD-BILLET:01 후공정 소재 빌렛 제강·출강 20 t 22% 0.2222":
            - cell "PROD-BILLET":
              - button "PROD-BILLET"
            - cell "용선 MAT-PROD-BILLET:01":
              - strong: 용선
              - text: MAT-PROD-BILLET:01
            - cell "후공정 소재"
            - cell "빌렛"
            - cell "제강·출강"
            - cell "20 t"
            - cell "22% 0.2222":
              - text: 22%
              - progressbar "PROD-BILLET 생산 진행률"
          - row "PROD-HR 용강 MAT-PROD-HR:02 후공정 소재 열연 제강·출강 21 t 27% 0.2727":
            - cell "PROD-HR":
              - button "PROD-HR"
            - cell "용강 MAT-PROD-HR:02":
              - strong: 용강
              - text: MAT-PROD-HR:02
            - cell "후공정 소재"
            - cell "열연"
            - cell "제강·출강"
            - cell "21 t"
            - cell "27% 0.2727":
              - text: 27%
              - progressbar "PROD-HR 생산 진행률"
          - row "PROD-CR 용강 MAT-PROD-CR:02 후공정 소재 냉연 연주 22 t 29% 0.2857":
            - cell "PROD-CR":
              - button "PROD-CR"
            - cell "용강 MAT-PROD-CR:02":
              - strong: 용강
              - text: MAT-PROD-CR:02
            - cell "후공정 소재"
            - cell "냉연"
            - cell "연주"
            - cell "22 t"
            - cell "29% 0.2857":
              - text: 29%
              - progressbar "PROD-CR 생산 진행률"
          - row "PROD-GI 슬래브 MAT-PROD-GI:03 후공정 소재 GI · 용융아연 연주 23 t 33% 0.3333":
            - cell "PROD-GI":
              - button "PROD-GI" [pressed]
            - cell "슬래브 MAT-PROD-GI:03":
              - strong: 슬래브
              - text: MAT-PROD-GI:03
            - cell "후공정 소재"
            - cell "GI · 용융아연"
            - cell "연주"
            - cell "23 t"
            - cell "33% 0.3333":
              - text: 33%
              - progressbar "PROD-GI 생산 진행률"
          - row "PROD-GA 슬래브 MAT-PROD-GA:03 후공정 소재 GA · 합금화아연 열연 24 t 38% 0.375":
            - cell "PROD-GA":
              - button "PROD-GA"
            - cell "슬래브 MAT-PROD-GA:03":
              - strong: 슬래브
              - text: MAT-PROD-GA:03
            - cell "후공정 소재"
            - cell "GA · 합금화아연"
            - cell "열연"
            - cell "24 t"
            - cell "38% 0.375":
              - text: 38%
              - progressbar "PROD-GA 생산 진행률"
          - row "PROD-EG 슬래브 MAT-PROD-EG:03 후공정 소재 EG · 전기아연 열연 25 t 47% 0.4667":
            - cell "PROD-EG":
              - button "PROD-EG"
            - cell "슬래브 MAT-PROD-EG:03":
              - strong: 슬래브
              - text: MAT-PROD-EG:03
            - cell "후공정 소재"
            - cell "EG · 전기아연"
            - cell "열연"
            - cell "25 t"
            - cell "47% 0.4667":
              - text: 47%
              - progressbar "PROD-EG 생산 진행률"
          - row "PROD-HGI 열연 MAT-PROD-HGI:04 후공정 소재 HGI · 열연도금 도금 26 t 62% 0.6154":
            - cell "PROD-HGI":
              - button "PROD-HGI"
            - cell "열연 MAT-PROD-HGI:04":
              - strong: 열연
              - text: MAT-PROD-HGI:04
            - cell "후공정 소재"
            - cell "HGI · 열연도금"
            - cell "도금"
            - cell "26 t"
            - cell "62% 0.6154":
              - text: 62%
              - progressbar "PROD-HGI 생산 진행률"
    - text: 생산 전용 합성 배치 · 소재 변환 이력은 중복 재고로 합산하지 않습니다.
  - paragraph: 공정·설비·질량은 설명용 합성 데이터입니다. 블룸·빌렛은 반제품 판매 경로이며, 봉형강·선재 후공정은 이번 범위에 포함하지 않습니다.
```

# Test source

```ts
  77  |   await expect(page.getByText('선택한 제품은 이 공정을 거치지 않습니다.', { exact: false })).toBeVisible();
  78  |   await expect(page.getByRole('region', { name: '생산 작업 목록' }).getByRole('button')).toHaveCount(0);
  79  |   await page.getByLabel('제품 경로', { exact: true }).selectOption('ALL');
  80  |   await expect(page.getByRole('region', { name: '생산 작업 목록' }).getByRole('button')).toHaveCount(4);
  81  |   await shot(page, 'incompatible-filter-recovery');
  82  | });
  83  | 
  84  | test('same HR and CR forms distinguish sale products from feedstock and preserve genealogy', async ({ page }, testInfo) => {
  85  |   await page.getByRole('button', { name: '2D 공정', exact: true }).click();
  86  |   let advanced: World | undefined;
  87  |   for (let tick = 1; tick <= 5; tick++) advanced = await step(page);
  88  |   if (!advanced) throw new Error('Missing stepped world');
  89  |   for (const [product, form, role] of [['HR', '열연', '판매 제품'], ['CR', '열연', '후공정 소재']]) {
  90  |     await page.getByRole('region', { name: '생산 작업 목록' }).getByRole('button', { name: `PROD-${product}`, exact: true }).click();
  91  |     await expect(inspector(page).getByRole('heading', { name: form, exact: true })).toBeVisible();
  92  |     await expect(inspector(page).locator('.material-summary .production-badge')).toHaveText(role!);
  93  |     await shot(page, `hr-role-${product?.toLowerCase()}`);
  94  |   }
  95  |   advanced = await step(page);
  96  |   for (const [product, role] of [['CR', '판매 제품'], ['GI', '후공정 소재']]) {
  97  |     await page.getByRole('region', { name: '생산 작업 목록' }).getByRole('button', { name: `PROD-${product}`, exact: true }).click();
  98  |     await expect(inspector(page).getByRole('heading', { name: '냉연', exact: true })).toBeVisible();
  99  |     await expect(inspector(page).locator('.material-summary .production-badge')).toHaveText(role!);
  100 |     const batch = advanced.production.batches.find(item => item.product === product);
  101 |     if (!batch) throw new Error(`Missing ${product}`);
  102 |     const history = inspector(page).getByRole('list', { name: '소재 계보' });
  103 |     await expect(history.getByRole('listitem')).toHaveCount(batch.material_history.length);
  104 |     for (const item of batch.material_history) await expect(history).toContainText(item.id);
  105 |     for (let i = 1; i < batch.material_history.length; i++) expect(batch.material_history[i]?.parent_id).toBe(batch.material_history[i - 1]?.id);
  106 |     await shot(page, `cr-role-${product?.toLowerCase()}`);
  107 |   }
  108 |   await testInfo.attach('tick6-production', { body: JSON.stringify(advanced.production, null, 2), contentType: 'application/json' });
  109 |   await inspector(page).getByRole('button', { name: /현재 공정/ }).click();
  110 |   const steps = page.getByRole('region', { name: '공정 내부 작업 흐름' });
  111 |   await steps.getByRole('button').first().click();
  112 |   await expect(steps.getByRole('status')).toContainText('설비');
  113 | });
  114 | 
  115 | test('scenario changes alter visible work and reset reproduces production at the same step', async ({ page }, testInfo) => {
  116 |   await page.getByRole('button', { name: '2D 공정', exact: true }).click();
  117 |   const results: Record<string, World['production']> = {};
  118 |   for (const scenario of ['NORMAL', 'DELAY', 'RECOVERY']) {
  119 |     if (scenario !== 'NORMAL') {
  120 |       const response = page.waitForResponse(item => item.url().endsWith(`/scenarios/${scenario}/activate`));
  121 |       await page.getByLabel('생산 시나리오', { exact: true }).selectOption(scenario);
  122 |       expect((await response).ok()).toBe(true);
  123 |     }
  124 |     let state: World | undefined;
  125 |     for (let i = 0; i < 6; i++) state = await step(page);
  126 |     if (!state) throw new Error('Missing production snapshot');
  127 |     results[scenario] = state.production;
  128 |     await page.getByLabel('제품 경로', { exact: true }).selectOption('GI');
  129 |     await inspector(page).getByRole('button', { name: /현재 공정/ }).click();
  130 |     await expect(page.getByRole('region', { name: '공정 내부 작업 흐름' }).getByRole('button', { name: scenario === 'DELAY' ? /산세 PICKLE-01 · 작업 중/ : scenario === 'RECOVERY' ? /소둔 ANNEAL-01 · 작업 중/ : /용융아연 도금 HDG-01 · 작업 중/ })).toBeVisible();
  131 |     await shot(page, `scenario-${scenario.toLowerCase()}-tick6`);
  132 |     await command(page, 'Reset simulation', 'reset');
  133 |     for (let i = 0; i < 6; i++) state = await step(page);
  134 |     expect(state.production).toEqual(results[scenario]);
  135 |   }
  136 |   expect(results.NORMAL).not.toEqual(results.DELAY);
  137 |   expect(results.RECOVERY).not.toEqual(results.DELAY);
  138 |   expect(results.RECOVERY).not.toEqual(results.NORMAL);
  139 |   await testInfo.attach('scenario-production-snapshots', { body: JSON.stringify(results, null, 2), contentType: 'application/json' });
  140 | });
  141 | 
  142 | test('mobile 2D core actions fit 390px and backend pause and step remain authoritative', async ({ page, request }, testInfo) => {
  143 |   await page.setViewportSize({ width: 390, height: 844 });
  144 |   await page.getByRole('button', { name: '2D 공정', exact: true }).click();
  145 |   await page.getByLabel('제품 경로', { exact: true }).selectOption('GA');
  146 |   await nav(page).getByRole('button', { name: /도금/ }).click();
  147 |   await page.getByRole('region', { name: '생산 작업 목록' }).getByRole('button', { name: 'PROD-GA', exact: true }).click();
  148 |   await page.getByRole('region', { name: '공정 내부 작업 흐름' }).getByRole('button').last().click();
  149 |   await expect(page.getByRole('region', { name: '공정 내부 작업 흐름' }).getByRole('status')).toContainText('합금화');
  150 |   await page.getByLabel('Simulation speed', { exact: true }).selectOption('4');
  151 |   const playing = await command(page, 'Play simulation', 'play');
  152 |   await expect.poll(async () => (await world(request)).simulation.tick).toBeGreaterThan(playing.simulation.tick);
  153 |   const paused = await command(page, 'Pause simulation', 'pause');
  154 |   await page.waitForTimeout(600);
  155 |   expect((await world(request)).simulation.tick).toBe(paused.simulation.tick);
  156 |   expect((await step(page)).simulation.tick).toBe(paused.simulation.tick + 1);
  157 |   await shot(page, 'mobile-390');
  158 |   const layout = await page.evaluate(() => ({ documentWidth: document.documentElement.scrollWidth, viewportWidth: innerWidth }));
  159 |   await testInfo.attach('mobile-layout', { body: JSON.stringify(layout), contentType: 'application/json' });
  160 |   expect(layout.documentWidth).toBeLessThanOrEqual(layout.viewportWidth);
  161 |   await page.getByRole('button', { name: '전체 공정', exact: true }).click();
  162 |   await expect(page.getByRole('heading', { name: '생산 오버뷰', exact: true })).toBeVisible();
  163 | });
  164 | 
  165 | test('production WebGL context loss recovers to fully usable 2D stages and material selection', async ({ page }) => {
  166 |   const canvas = page.locator('canvas');
  167 |   await expect(canvas).toBeVisible();
  168 |   await page.waitForTimeout(600);
  169 |   const supported = await canvas.evaluate(element => {
  170 |     if (!(element instanceof HTMLCanvasElement)) throw new Error('Expected canvas');
  171 |     const extension = element.getContext('webgl2')?.getExtension('WEBGL_lose_context');
  172 |     if (!extension) return false;
  173 |     extension.loseContext();
  174 |     return true;
  175 |   });
  176 |   expect(supported).toBe(true);
> 177 |   await expect(page.getByText('3D production view unavailable', { exact: true })).toBeVisible();
      |                                                                                   ^ Error: expect(locator).toBeVisible() failed
  178 |   await page.getByRole('button', { name: 'Open production list', exact: true }).click();
  179 |   await expect(page.getByRole('button', { name: '2D 공정', exact: true })).toHaveAttribute('aria-pressed', 'true');
  180 |   await page.getByLabel('제품 경로', { exact: true }).selectOption('HGI');
  181 |   await nav(page).getByRole('button', { name: /도금/ }).click();
  182 |   await page.getByRole('region', { name: '생산 작업 목록' }).getByRole('button', { name: 'PROD-HGI', exact: true }).click();
  183 |   await expect(inspector(page)).toContainText('PROD-HGI');
  184 |   expect((await step(page)).simulation.tick).toBe(1);
  185 |   await shot(page, 'webgl-fallback');
  186 | });
  187 | 
  188 | test('3D renders and camera responds while workspace tabs remain stable and local-only', async ({ page }, testInfo) => {
  189 |   const external: string[] = [];
  190 |   page.on('request', request => { if (!request.url().startsWith('http://127.0.0.1:5174/') && !request.url().startsWith('data:') && !request.url().startsWith('blob:')) external.push(request.url()); });
  191 |   await page.reload();
  192 |   const canvas = page.locator('canvas');
  193 |   await expect(canvas).toBeVisible();
  194 |   await expect(page.getByRole('button', { name: 'Advance one step', exact: true })).toBeEnabled();
  195 |   await page.waitForTimeout(600);
  196 |   await shot(page, '3d-overview');
  197 |   const overviewBox = await canvas.boundingBox();
  198 |   if (!overviewBox) throw new Error('Missing overview canvas');
  199 |   await page.mouse.click(overviewBox.x + overviewBox.width * 0.40, overviewBox.y + overviewBox.height * 0.26);
  200 |   await expect(page.getByRole('heading', { name: '제선·출선 공정', exact: true })).toBeVisible();
  201 |   await shot(page, '3d-facility-picking');
  202 |   await page.getByRole('button', { name: '전체 공정', exact: true }).click();
  203 |   const before = await canvas.screenshot();
  204 |   const box = await canvas.boundingBox();
  205 |   if (!box) throw new Error('Missing 3D canvas bounds');
  206 |   await page.mouse.move(box.x + box.width * 0.7, box.y + box.height * 0.5);
  207 |   await page.mouse.down();
  208 |   await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.6, { steps: 12 });
  209 |   await page.mouse.up();
  210 |   await page.mouse.wheel(0, -150);
  211 |   await expect.poll(async () => (await canvas.screenshot()).equals(before)).toBe(false);
  212 |   await shot(page, '3d-orbit');
  213 |   await page.getByRole('button', { name: '생산 카메라 초기화', exact: true }).click();
  214 |   await nav(page).getByRole('button', { name: /제선·출선/ }).click();
  215 |   await expect(page.getByRole('heading', { name: '제선·출선 공정', exact: true })).toBeVisible();
  216 |   await shot(page, '3d-detail');
  217 |   const tabs = page.getByRole('navigation', { name: '워크스페이스 선택' });
  218 |   for (let i = 0; i < 3; i++) {
  219 |     await tabs.getByRole('button', { name: '물류 오버뷰', exact: true }).click();
  220 |     await expect(page.getByRole('heading', { name: 'Operations overview', exact: true })).toBeVisible();
  221 |     await tabs.getByRole('button', { name: '생산 공정', exact: true }).click();
  222 |     await expect(page.getByRole('heading', { name: '생산 오버뷰', exact: true })).toBeVisible();
  223 |   }
  224 |   await testInfo.attach('external-requests', { body: JSON.stringify(external), contentType: 'application/json' });
  225 |   expect(external).toEqual([]);
  226 | });
  227 | 
```