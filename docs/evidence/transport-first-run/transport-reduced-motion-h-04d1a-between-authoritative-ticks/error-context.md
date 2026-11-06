# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: transport.spec.ts >> reduced motion holds loaded transport still between authoritative ticks
- Location: tests/transport.spec.ts:169:1

# Error details

```
Error: expect(received).toBe(expected) // Object.is equality

Expected: 0
Received: 962
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
        - button "생산 공정" [pressed] [ref=e65] [cursor=pointer]
      - generic [ref=e68]:
        - generic [ref=e69]:
          - generic [ref=e70]:
            - button "생산 오버뷰" [ref=e72] [cursor=pointer]
            - heading "생산 오버뷰" [level=1] [ref=e73]
            - paragraph [ref=e75]: 소재가 제품이 되는 과정. 공정을 선택해 작업 흐름 안으로 들어가세요.
          - generic [ref=e76]: 합성 생산 시나리오
        - generic "생산 배치 현황" [ref=e78]:
          - generic [ref=e79]:
            - generic [ref=e82]: 작업 중
            - strong [ref=e83]: 6배치
          - generic [ref=e84]:
            - generic [ref=e87]: 생산 완료
            - strong [ref=e88]:
              - text: "0"
              - generic [ref=e89]: / 9
          - generic [ref=e90]:
            - generic [ref=e94]: 생산 배치 총량
            - strong [ref=e95]: 198t
          - generic [ref=e96]:
            - generic [ref=e102]: 공정 간 운송
            - strong [ref=e103]: 3대
        - generic [ref=e104]:
          - generic [ref=e105]:
            - strong [ref=e110]: 통합 생산 공정
            - generic [ref=e111]: 제선에서 제품 재고까지
          - generic [ref=e112]:
            - text: 제품 경로
            - combobox "제품 경로" [ref=e113]:
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
          - generic [ref=e114]:
            - text: 시나리오
            - combobox "생산 시나리오" [ref=e115]:
              - option "정상 생산" [selected]
              - option "열연 지연"
              - option "대체 라인 회복"
        - generic [ref=e116]:
          - region "생산 공정 시각화" [ref=e117]:
            - generic [ref=e118]:
              - generic [ref=e119]: 전체 공장 · 서버 상태 연결
              - generic [ref=e121]:
                - button "3D 공정" [pressed] [ref=e122] [cursor=pointer]
                - button "2D 공정" [ref=e126] [cursor=pointer]
            - generic [ref=e128]:
              - generic "대화형 생산 모형. 설비 또는 배치를 선택하세요. 드래그로 회전하고 스크롤로 확대합니다. 공정과 배치는 화면 옆 목록에서도 선택할 수 있습니다." [ref=e129]
              - button "생산 카메라 초기화" [ref=e132] [cursor=pointer]
              - generic:
                - generic: 공정을 클릭해 상세 화면으로 이동
                - generic: 드래그 회전 · 스크롤 확대
            - navigation "생산 공정 선택" [ref=e139]:
              - button "01 제선·출선 2 작업 중" [ref=e140] [cursor=pointer]:
                - generic [ref=e141]: "01"
                - strong [ref=e142]: 제선·출선
                - generic [ref=e143]: 2 작업 중
              - button "02 제강·출강 2 작업 중" [ref=e144] [cursor=pointer]:
                - generic [ref=e145]: "02"
                - strong [ref=e146]: 제강·출강
                - generic [ref=e147]: 2 작업 중
              - button "03 연주 2 작업 중" [ref=e148] [cursor=pointer]:
                - generic [ref=e149]: "03"
                - strong [ref=e150]: 연주
                - generic [ref=e151]: 2 작업 중
              - button "04 열연 현재 작업 없음" [ref=e152] [cursor=pointer]:
                - generic [ref=e153]: "04"
                - strong [ref=e154]: 열연
                - generic [ref=e155]: 현재 작업 없음
              - button "05 냉연 현재 작업 없음" [ref=e156] [cursor=pointer]:
                - generic [ref=e157]: "05"
                - strong [ref=e158]: 냉연
                - generic [ref=e159]: 현재 작업 없음
              - button "06 도금 현재 작업 없음" [ref=e160] [cursor=pointer]:
                - generic [ref=e161]: "06"
                - strong [ref=e162]: 도금
                - generic [ref=e163]: 현재 작업 없음
              - button "07 정정·검사 현재 작업 없음" [ref=e164] [cursor=pointer]:
                - generic [ref=e165]: "07"
                - strong [ref=e166]: 정정·검사
                - generic [ref=e167]: 현재 작업 없음
              - button "08 제품 재고 현재 작업 없음" [ref=e168] [cursor=pointer]:
                - generic [ref=e169]: "08"
                - strong [ref=e170]: 제품 재고
                - generic [ref=e171]: 현재 작업 없음
            - generic [ref=e172]:
              - button "Play simulation" [ref=e173] [cursor=pointer]:
                - generic [ref=e176]: Play
              - button "Advance one step" [ref=e177] [cursor=pointer]
              - button "Reset simulation" [ref=e180] [cursor=pointer]
              - generic [ref=e185]:
                - generic [ref=e186]: Simulation speed
                - combobox "Simulation speed" [ref=e187]:
                  - option "1× speed" [selected]
                  - option "2× speed"
                  - option "4× speed"
              - generic [ref=e188]:
                - generic [ref=e189]:
                  - generic [ref=e190]: 08:00 UTC
                  - generic [ref=e191]: Step 0 / 24
                - progressbar "Simulation progress" [ref=e192]
              - generic [ref=e193]: Paused
          - complementary "선택 소재 상세" [ref=e195]:
            - generic [ref=e196]:
              - generic [ref=e197]: 소재 추적
              - generic [ref=e202]: PROD-HGI
            - generic [ref=e203]:
              - text: CURRENT MATERIAL
              - heading "슬래브" [level=2] [ref=e204]
              - generic [ref=e205]: 후공정 소재
              - generic [ref=e206]:
                - generic [ref=e210]: 목표 제품
                - strong [ref=e211]: HGI · 열연도금
              - generic [ref=e212]:
                - generic [ref=e213]:
                  - generic [ref=e214]: 배치 질량
                  - strong [ref=e215]: 26 t
                - generic [ref=e216]:
                  - generic [ref=e217]: 작업 상태
                  - strong [ref=e218]: 운송 중
              - generic "선택 소재 운송 정보" [ref=e219]:
                - strong [ref=e226]: 소재 운반 트럭 · 운송 중
                - code [ref=e227]: VEHICLE-HGI-flatbed_truck
                - paragraph [ref=e228]: 현재 소재는 차량에 적재되어 있습니다.
                - button "출발 공정 · 연주" [ref=e229] [cursor=pointer]
                - button "도착 공정 · 열연" [ref=e233] [cursor=pointer]
            - generic [ref=e237]:
              - heading "소재 변환 이력 4" [level=3] [ref=e238]:
                - text: 소재 변환 이력
                - generic [ref=e239]: "4"
              - list "소재 계보" [ref=e240]:
                - listitem [ref=e241]:
                  - generic [ref=e244]:
                    - strong [ref=e245]: 철원료
                    - generic [ref=e246]: 소재 · 제선·출선
                    - generic [ref=e247]: MAT-PROD-HGI:00
                - listitem [ref=e250]:
                  - generic [ref=e253]:
                    - strong [ref=e254]: 용선
                    - generic [ref=e255]: 소재 · 제선·출선
                    - generic [ref=e256]: MAT-PROD-HGI:01
                - listitem [ref=e259]:
                  - generic [ref=e262]:
                    - strong [ref=e263]: 용강
                    - generic [ref=e264]: 소재 · 제강·출강
                    - generic [ref=e265]: MAT-PROD-HGI:02
                - listitem [ref=e268]:
                  - generic [ref=e280]:
                    - strong [ref=e281]: 슬래브
                    - generic [ref=e282]: 소재 · 연주
                    - generic [ref=e283]: MAT-PROD-HGI:03
            - paragraph [ref=e284]: 형태와 용도는 별개입니다. 같은 열연·냉연 코일도 생산 경로에 따라 판매 제품 또는 다음 공정의 소재가 됩니다.
        - region "선택 배치 생산 경로" [ref=e285]:
          - generic [ref=e286]:
            - generic [ref=e287]: MATERIAL ROUTE
            - strong [ref=e288]: PROD-HGI
          - list [ref=e289]:
            - listitem [ref=e290]:
              - button "제선·출선 · 완료" [ref=e291] [cursor=pointer]:
                - text: 제선·출선
                - generic [ref=e294]: · 완료
            - listitem [ref=e297]:
              - button "제강·출강 · 완료" [ref=e298] [cursor=pointer]:
                - text: 제강·출강
                - generic [ref=e301]: · 완료
            - listitem [ref=e304]:
              - button "연주 · 완료" [ref=e305] [cursor=pointer]:
                - text: 연주
                - generic [ref=e308]: · 완료
              - generic [ref=e309]: 열연까지 운송 중
            - listitem [ref=e316]:
              - button "열연 · 대기" [ref=e317] [cursor=pointer]:
                - text: 열연
                - generic [ref=e321]: · 대기
            - listitem [ref=e324]:
              - button "도금 · 대기" [ref=e325] [cursor=pointer]:
                - text: 도금
                - generic [ref=e329]: · 대기
            - listitem [ref=e332]:
              - button "정정·검사 · 대기" [ref=e333] [cursor=pointer]:
                - text: 정정·검사
                - generic [ref=e337]: · 대기
            - listitem [ref=e340]:
              - button "제품 재고 · 대기" [ref=e341] [cursor=pointer]:
                - text: 제품 재고
                - generic [ref=e345]: · 대기
        - region "공정 간 운송" [ref=e346]:
          - generic [ref=e347]:
            - heading "공정 간 운송" [level=2] [ref=e348]
            - generic [ref=e354]: 운송 중 1대 · 26 t
          - generic [ref=e355]:
            - generic [ref=e356]:
              - button "운송 중" [pressed] [ref=e357] [cursor=pointer]
              - button "선택 배치 경로" [ref=e358] [cursor=pointer]
            - generic [ref=e359]: 차량을 선택해 적재 소재를 추적하세요
          - region "생산 운송 표" [ref=e360]:
            - table [ref=e361]:
              - caption [ref=e362]: 공정 간 소재 운송. 현재 차량, 화물, 출발지와 도착지를 확인합니다.
              - rowgroup [ref=e363]:
                - row [ref=e364]:
                  - columnheader "운반 차량" [ref=e365]
                  - columnheader "적재 소재" [ref=e366]
                  - columnheader "운송 경로" [ref=e367]
                  - columnheader "질량" [ref=e368]
                  - columnheader "상태" [ref=e369]
              - rowgroup [ref=e370]:
                - row [ref=e371]:
                  - cell "VEHICLE-HGI-flatbed_truck 적재 소재 선택 VEHICLE-HGI-flatbed_truck" [ref=e372]:
                    - button "VEHICLE-HGI-flatbed_truck 적재 소재 선택" [pressed] [ref=e373] [cursor=pointer]: 소재 운반 트럭
                    - generic [ref=e374]: VEHICLE-HGI-flatbed_truck
                  - cell "슬래브 PROD-HGI · MAT-PROD-HGI:03" [ref=e375]:
                    - strong [ref=e376]: 슬래브
                    - generic [ref=e377]: PROD-HGI · MAT-PROD-HGI:03
                  - cell [ref=e378]:
                    - generic [ref=e379]:
                      - button "TRANSPORT-HGI-03 출발 연주" [ref=e380] [cursor=pointer]: 연주
                      - button "TRANSPORT-HGI-03 도착 열연" [ref=e383] [cursor=pointer]: 열연
                  - cell "26 t" [ref=e384]
                  - cell "운송 중" [ref=e385]
          - paragraph [ref=e387]: 공정 간 이동은 서버가 관리합니다. 도착이 확인된 뒤 다음 작업을 시작합니다.
        - region "생산 작업 목록" [ref=e388]:
          - generic [ref=e389]:
            - heading "전체 생산 배치" [level=2] [ref=e390]
            - generic [ref=e391]: 1개 배치 · 26 t
          - region "생산 소재 표" [ref=e392]:
            - table [ref=e393]:
              - caption [ref=e394]: 합성 생산 배치. 배치 선택으로 경로와 소재 계보를 확인합니다.
              - rowgroup [ref=e395]:
                - row [ref=e396]:
                  - columnheader "생산 배치" [ref=e397]
                  - columnheader "현재 소재" [ref=e398]
                  - columnheader "용도" [ref=e399]
                  - columnheader "목표 제품" [ref=e400]
                  - columnheader "현재 공정" [ref=e401]
                  - columnheader "질량" [ref=e402]
                  - columnheader "생산 진행" [ref=e403]
              - rowgroup [ref=e404]:
                - row [ref=e405]:
                  - cell [ref=e406]:
                    - button "PROD-HGI" [pressed] [ref=e407] [cursor=pointer]
                  - cell "슬래브 MAT-PROD-HGI:03" [ref=e408]:
                    - strong [ref=e409]: 슬래브
                    - generic [ref=e410]: MAT-PROD-HGI:03
                  - cell "후공정 소재" [ref=e411]
                  - cell "HGI · 열연도금" [ref=e413]
                  - cell "운송 중 연주 → 열연 · VEHICLE-HGI-flatbed_truck" [ref=e414]:
                    - generic [ref=e415]: 운송 중
                    - generic [ref=e416]: 연주 → 열연 · VEHICLE-HGI-flatbed_truck
                  - cell "26 t" [ref=e417]
                  - cell "46% 0.4615" [ref=e418]:
                    - generic [ref=e419]:
                      - generic [ref=e420]: 46%
                      - progressbar "PROD-HGI 생산 진행률" [ref=e421]
          - generic [ref=e422]: 생산 전용 합성 배치 · 소재 변환 이력은 중복 재고로 합산하지 않습니다.
        - paragraph [ref=e423]: 공정·설비·질량은 설명용 합성 데이터입니다. 블룸·빌렛은 반제품 판매 경로이며, 봉형강·선재 후공정은 이번 범위에 포함하지 않습니다.
```

# Test source

```ts
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
  110 |   await expect(inspector(page)).toContainText('PROD-HGI');
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
> 181 |   const reducedDiff = await difference(page, before, after); expect(reducedDiff.count).toBe(0);
      |                                                                                        ^ Error: expect(received).toBe(expected) // Object.is equality
  182 |   await clickCommand(page, 'Advance one step', 'step');
  183 |   const arrived = await capture(page, 'reduced-arrival');
  184 |   const arrivalDiff = await difference(page, after, arrived); expect(arrivalDiff.count).toBeGreaterThan(50);
  185 |   await save('reduced-motion', { reducedDiff, arrivalDiff, tick: paused.simulation.tick });
  186 | });
  187 | 
```