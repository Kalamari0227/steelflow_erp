# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: production.spec.ts >> coating equipment clicks select only the matching GA, EG or HGI operation
- Location: tests/production.spec.ts:235:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('region', { name: '공정 내부 작업 흐름' }).getByRole('button', { name: /산세·표면준비 HGI-PICKLE-01/, pressed: true })
Expected: visible
Timeout: 10000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('region', { name: '공정 내부 작업 흐름' }).getByRole('button', { name: /산세·표면준비 HGI-PICKLE-01/, pressed: true }) with timeout 10000ms
  - waiting for getByRole('region', { name: '공정 내부 작업 흐름' }).getByRole('button', { name: /산세·표면준비 HGI-PICKLE-01/, pressed: true })

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
  - img
  - text: 도금
  - heading "도금 공정" [level=1]
  - paragraph: GI·GA·EG·HGI. 소재와 도금 방식에 따라 서로 다른 작업을 거칩니다.
  - button "전체 공정":
    - img
    - text: 전체 공정
  - text: 합성 생산 시나리오
  - img
  - text: 작업 중
  - strong: 6배치
  - img
  - text: 생산 완료
  - strong: 0/ 9
  - img
  - text: 생산 배치 총량
  - strong: 198t
  - img
  - text: 공정 간 운송
  - strong: 3대
  - img
  - strong: 도금
  - text: 제선에서 제품 재고까지 제품 경로
  - combobox "제품 경로":
    - option "전체 제품"
    - option "슬래브"
    - option "블룸"
    - option "빌렛"
    - option "열연"
    - option "냉연"
    - option "GI · 용융아연"
    - option "GA · 합금화아연"
    - option "EG · 전기아연"
    - option "HGI · 열연도금" [selected]
  - text: 시나리오
  - combobox "생산 시나리오":
    - option "정상 생산" [selected]
    - option "열연 지연"
    - option "대체 라인 회복"
  - region "생산 공정 시각화":
    - text: 도금 · 서버 상태 연결
    - button "3D 공정" [pressed]:
      - img
      - text: 3D 공정
    - button "2D 공정":
      - img
      - text: 2D 공정
    - button "생산 카메라 초기화":
      - img
    - text: 설비를 선택하면 작업 단계가 표시됩니다 드래그 회전 · 스크롤 확대
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
      - button "04 열연 현재 작업 없음":
        - text: "04"
        - strong: 열연
        - text: 현재 작업 없음
      - button "05 냉연 현재 작업 없음":
        - text: "05"
        - strong: 냉연
        - text: 현재 작업 없음
      - button "06 도금 현재 작업 없음" [pressed]:
        - text: "06"
        - strong: 도금
        - text: 현재 작업 없음
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
    - text: 소재 추적 PROD-HGI CURRENT MATERIAL
    - heading "슬래브" [level=2]
    - text: 후공정 소재
    - img
    - text: 목표 제품
    - strong: HGI · 열연도금
    - text: 배치 질량
    - strong: 26 t
    - text: 작업 상태
    - strong: 운송 중
    - img
    - strong: 소재 운반 트럭 · 운송 중
    - code: VEHICLE-HGI-flatbed_truck
    - paragraph: 현재 소재는 차량에 적재되어 있습니다.
    - button "출발 공정 · 연주":
      - text: 출발 공정 · 연주
      - img
    - button "도착 공정 · 열연":
      - text: 도착 공정 · 열연
      - img
    - heading "소재 변환 이력 4" [level=3]
    - list "소재 계보":
      - listitem:
        - strong: 철원료
        - text: 소재 · 제선·출선 MAT-PROD-HGI:00
        - img
      - listitem:
        - strong: 용선
        - text: 소재 · 제선·출선 MAT-PROD-HGI:01
        - img
      - listitem:
        - strong: 용강
        - text: 소재 · 제강·출강 MAT-PROD-HGI:02
        - img
      - listitem:
        - img
        - strong: 슬래브
        - text: 소재 · 연주 MAT-PROD-HGI:03
    - paragraph: 형태와 용도는 별개입니다. 같은 열연·냉연 코일도 생산 경로에 따라 판매 제품 또는 다음 공정의 소재가 됩니다.
  - region "선택 배치 생산 경로":
    - text: MATERIAL ROUTE
    - strong: PROD-HGI
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
        - button "연주 · 완료":
          - img
          - text: 연주 · 완료
        - text: 열연까지 운송 중
      - listitem:
        - button "열연 · 대기":
          - img
          - text: 열연 · 대기
      - listitem:
        - button "도금 · 대기" [pressed]:
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
  - region "공정 내부 작업 흐름":
    - heading "공정 내부 흐름" [level=2]
    - text: PROD-HGI
    - list:
      - listitem:
        - button "01 산세·표면준비 HGI-PICKLE-01 · 대기":
          - text: "01"
          - strong: 산세·표면준비
          - text: HGI-PICKLE-01 · 대기
      - listitem:
        - button "02 용융아연 도금 HDG-01 · 대기":
          - text: "02"
          - strong: 용융아연 도금
          - text: HDG-01 · 대기
  - region "공정 간 운송":
    - heading "공정 간 운송" [level=2]:
      - img
      - text: 공정 간 운송
    - text: 운송 중 0대 · 0 t
    - button "운송 중" [pressed]
    - button "선택 배치 경로"
    - text: 차량을 선택해 적재 소재를 추적하세요
    - region "생산 운송 표":
      - table "공정 간 소재 운송. 현재 차량, 화물, 출발지와 도착지를 확인합니다.":
        - caption: 공정 간 소재 운송. 현재 차량, 화물, 출발지와 도착지를 확인합니다.
        - rowgroup:
          - row "운반 차량 적재 소재 운송 경로 질량 상태":
            - columnheader "운반 차량"
            - columnheader "적재 소재"
            - columnheader "운송 경로"
            - columnheader "질량"
            - columnheader "상태"
        - rowgroup
    - paragraph: 현재 운송 중인 차량이 없습니다. 다음 공정으로 이동할 때 운송 상태가 표시됩니다.
    - paragraph: 공정 간 이동은 서버가 관리합니다. 도착이 확인된 뒤 다음 작업을 시작합니다.
  - region "생산 작업 목록":
    - heading "도금 작업 목록" [level=2]
    - text: 1개 배치 · 26 t
    - region "생산 소재 표":
      - table "합성 생산 배치. 배치 선택으로 경로와 소재 계보를 확인합니다.":
        - caption: 합성 생산 배치. 배치 선택으로 경로와 소재 계보를 확인합니다.
        - rowgroup:
          - row "생산 배치 현재 소재 용도 목표 제품 이 공정 상태 질량 생산 진행":
            - columnheader "생산 배치"
            - columnheader "현재 소재"
            - columnheader "용도"
            - columnheader "목표 제품"
            - columnheader "이 공정 상태"
            - columnheader "질량"
            - columnheader "생산 진행"
        - rowgroup:
          - row "PROD-HGI 슬래브 MAT-PROD-HGI:03 후공정 소재 HGI · 열연도금 대기 연주 → 열연 · VEHICLE-HGI-flatbed_truck 26 t 46% 0.4615":
            - cell "PROD-HGI":
              - button "PROD-HGI" [pressed]
            - cell "슬래브 MAT-PROD-HGI:03":
              - strong: 슬래브
              - text: MAT-PROD-HGI:03
            - cell "후공정 소재"
            - cell "HGI · 열연도금"
            - cell "대기 연주 → 열연 · VEHICLE-HGI-flatbed_truck"
            - cell "26 t"
            - cell "46% 0.4615":
              - text: 46%
              - progressbar "PROD-HGI 생산 진행률"
    - text: 생산 전용 합성 배치 · 소재 변환 이력은 중복 재고로 합산하지 않습니다.
  - paragraph: 공정·설비·질량은 설명용 합성 데이터입니다. 블룸·빌렛은 반제품 판매 경로이며, 봉형강·선재 후공정은 이번 범위에 포함하지 않습니다.
```

# Test source

```ts
  168 |   await page.getByRole('button', { name: '전체 공정', exact: true }).click();
  169 |   await expect(page.getByRole('heading', { name: '생산 오버뷰', exact: true })).toBeVisible();
  170 | });
  171 | 
  172 | test('production WebGL context loss recovers to fully usable 2D stages and material selection', async ({ page }) => {
  173 |   const canvas = page.locator('canvas');
  174 |   await expect(canvas).toBeVisible();
  175 |   await page.waitForTimeout(600);
  176 |   const supported = await canvas.evaluate(element => {
  177 |     if (!(element instanceof HTMLCanvasElement)) throw new Error('Expected canvas');
  178 |     const extension = element.getContext('webgl2')?.getExtension('WEBGL_lose_context');
  179 |     if (!extension) return false;
  180 |     extension.loseContext();
  181 |     return true;
  182 |   });
  183 |   expect(supported).toBe(true);
  184 |   await expect(page.getByText('3D 생산 화면을 사용할 수 없습니다', { exact: true })).toBeVisible();
  185 |   await page.getByRole('button', { name: '생산 목록 열기', exact: true }).click();
  186 |   await expect(page.getByRole('button', { name: '2D 공정', exact: true })).toHaveAttribute('aria-pressed', 'true');
  187 |   await page.getByLabel('제품 경로', { exact: true }).selectOption('HGI');
  188 |   await nav(page).getByRole('button', { name: /도금/ }).click();
  189 |   await page.getByRole('region', { name: '생산 작업 목록' }).getByRole('button', { name: 'PROD-HGI', exact: true }).click();
  190 |   await expect(inspector(page)).toContainText('PROD-HGI');
  191 |   expect((await step(page)).simulation.tick).toBe(1);
  192 |   await shot(page, 'webgl-fallback');
  193 | });
  194 | 
  195 | test('3D renders and camera responds while workspace tabs remain stable and local-only', async ({ page }, testInfo) => {
  196 |   const external: string[] = [];
  197 |   page.on('request', request => { if (!request.url().startsWith('http://127.0.0.1:5174/') && !request.url().startsWith('data:') && !request.url().startsWith('blob:')) external.push(request.url()); });
  198 |   await page.reload();
  199 |   const canvas = page.locator('canvas');
  200 |   await expect(canvas).toBeVisible();
  201 |   await expect(page.getByRole('button', { name: 'Advance one step', exact: true })).toBeEnabled();
  202 |   await page.waitForTimeout(600);
  203 |   await shot(page, '3d-overview');
  204 |   const overviewBox = await canvas.boundingBox();
  205 |   if (!overviewBox) throw new Error('Missing overview canvas');
  206 |   await page.mouse.click(overviewBox.x + overviewBox.width * 0.40, overviewBox.y + overviewBox.height * 0.26);
  207 |   await expect(page.getByRole('heading', { name: '제선·출선 공정', exact: true })).toBeVisible();
  208 |   await shot(page, '3d-facility-picking');
  209 |   await page.getByRole('button', { name: '전체 공정', exact: true }).click();
  210 |   const before = await canvas.screenshot();
  211 |   const box = await canvas.boundingBox();
  212 |   if (!box) throw new Error('Missing 3D canvas bounds');
  213 |   await page.mouse.move(box.x + box.width * 0.7, box.y + box.height * 0.5);
  214 |   await page.mouse.down();
  215 |   await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.6, { steps: 12 });
  216 |   await page.mouse.up();
  217 |   await page.mouse.wheel(0, -150);
  218 |   await expect.poll(async () => (await canvas.screenshot()).equals(before)).toBe(false);
  219 |   await shot(page, '3d-orbit');
  220 |   await page.getByRole('button', { name: '생산 카메라 초기화', exact: true }).click();
  221 |   await nav(page).getByRole('button', { name: /제선·출선/ }).click();
  222 |   await expect(page.getByRole('heading', { name: '제선·출선 공정', exact: true })).toBeVisible();
  223 |   await shot(page, '3d-detail');
  224 |   const tabs = page.getByRole('navigation', { name: '워크스페이스 선택' });
  225 |   for (let i = 0; i < 3; i++) {
  226 |     await tabs.getByRole('button', { name: '물류 오버뷰', exact: true }).click();
  227 |     await expect(page.getByRole('heading', { name: 'Operations overview', exact: true })).toBeVisible();
  228 |     await tabs.getByRole('button', { name: '생산 공정', exact: true }).click();
  229 |     await expect(page.getByRole('heading', { name: '생산 오버뷰', exact: true })).toBeVisible();
  230 |   }
  231 |   await testInfo.attach('external-requests', { body: JSON.stringify(external), contentType: 'application/json' });
  232 |   expect(external).toEqual([]);
  233 | });
  234 | 
  235 | test('coating equipment clicks select only the matching GA, EG or HGI operation', async ({ page }) => {
  236 |   await page.getByLabel('제품 경로', { exact: true }).selectOption('GA');
  237 |   await nav(page).getByRole('button', { name: /도금/ }).click();
  238 |   const canvas = page.locator('canvas');
  239 |   const work = page.getByRole('region', { name: '공정 내부 작업 흐름' });
  240 |   await expect(canvas).toBeVisible();
  241 |   await page.waitForTimeout(600);
  242 |   await shot(page, 'equipment-ga-before');
  243 |   const clickEquipment = async (x: number, y: number) => {
  244 |     await canvas.scrollIntoViewIfNeeded();
  245 |     const box = await canvas.boundingBox();
  246 |     if (!box) throw new Error('Coating canvas has no bounds');
  247 |     await page.mouse.click(box.x + box.width * x, box.y + box.height * y);
  248 |   };
  249 |   await clickEquipment(0.60, 0.54);
  250 |   await expect(work.getByRole('button', { pressed: true })).toHaveCount(0);
  251 |   await expect(work.getByRole('status')).toHaveCount(0);
  252 |   await clickEquipment(0.50, 0.44);
  253 |   await expect(work.getByRole('button', { name: /용융아연 도금 HDG-01/, pressed: true })).toBeVisible();
  254 |   await expect(work.getByRole('status')).toContainText('HDG-01');
  255 |   await shot(page, 'equipment-ga-hdg');
  256 | 
  257 |   await page.getByLabel('제품 경로', { exact: true }).selectOption('EG');
  258 |   await clickEquipment(0.50, 0.44);
  259 |   await expect(work.getByRole('button', { pressed: true })).toHaveCount(0);
  260 |   await expect(work.getByRole('status')).toHaveCount(0);
  261 |   await clickEquipment(0.60, 0.54);
  262 |   await expect(work.getByRole('button', { name: /전해 아연 도금 EGL-01/, pressed: true })).toBeVisible();
  263 |   await expect(work.getByRole('status')).toContainText('EGL-01');
  264 |   await shot(page, 'equipment-eg-egl');
  265 | 
  266 |   await page.getByLabel('제품 경로', { exact: true }).selectOption('HGI');
  267 |   await clickEquipment(0.40, 0.35);
> 268 |   await expect(work.getByRole('button', { name: /산세·표면준비 HGI-PICKLE-01/, pressed: true })).toBeVisible();
      |                                                                                            ^ Error: expect(locator).toBeVisible() failed
  269 |   await expect(work.getByRole('status')).toContainText('HGI-PICKLE-01');
  270 |   await shot(page, 'equipment-hgi-pickle');
  271 |   await clickEquipment(0.50, 0.44);
  272 |   await expect(work.getByRole('button', { name: /용융아연 도금 HDG-01/, pressed: true })).toBeVisible();
  273 |   await expect(work.getByRole('status')).toContainText('HDG-01');
  274 |   await shot(page, 'equipment-hgi-hdg');
  275 | });
  276 | 
```