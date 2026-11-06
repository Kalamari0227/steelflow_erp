# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: transport.spec.ts >> 390px 2D transport tracking survives WebGL loss and permits arrival navigation
- Location: tests/transport.spec.ts:159:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByRole('heading', { name: '열연 공정', exact: true })
Expected: visible
Timeout: 10000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" getByRole('heading', { name: '열연 공정', exact: true }) with timeout 10000ms
  - waiting for getByRole('heading', { name: '열연 공정', exact: true })
    - waiting for navigation to finish...
    - navigated to "http://127.0.0.1:5174/?workspace=production"

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
  - text: SF
- banner: SteelFlow 3D Synthetic environment
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
  - strong: 통합 생산 공정
  - text: 제품 경로
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
    - text: 공정을 클릭해 상세 화면으로 이동
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
      - button "06 도금 현재 작업 없음":
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
      - listitem:
        - strong: 용선
        - text: 소재 · 제선·출선 MAT-PROD-GI:01
      - listitem:
        - img
        - strong: 용강
        - text: 소재 · 제강·출강 MAT-PROD-GI:02
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
        - text: 연주까지 운송 중
      - listitem:
        - button "연주 · 대기":
          - img
          - text: 연주 · 대기
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
  - region "공정 간 운송":
    - heading "공정 간 운송" [level=2]:
      - img
      - text: 공정 간 운송
    - text: 운송 중 3대 · 69 t
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
        - rowgroup:
          - row "VEHICLE-BILLET-hot_metal_car 적재 소재 선택 VEHICLE-BILLET-hot_metal_car 용선 PROD-BILLET · MAT-PROD-BILLET:01 TRANSPORT-BILLET-01 출발 제선·출선 TRANSPORT-BILLET-01 도착 제강·출강 20 t 운송 중":
            - cell "VEHICLE-BILLET-hot_metal_car 적재 소재 선택 VEHICLE-BILLET-hot_metal_car":
              - button "VEHICLE-BILLET-hot_metal_car 적재 소재 선택": 용선 운반차
              - text: VEHICLE-BILLET-hot_metal_car
            - cell "용선 PROD-BILLET · MAT-PROD-BILLET:01":
              - strong: 용선
              - text: PROD-BILLET · MAT-PROD-BILLET:01
            - cell "TRANSPORT-BILLET-01 출발 제선·출선 TRANSPORT-BILLET-01 도착 제강·출강":
              - button "TRANSPORT-BILLET-01 출발 제선·출선": 제선·출선
              - button "TRANSPORT-BILLET-01 도착 제강·출강": 제강·출강
            - cell "20 t"
            - cell "운송 중"
          - row "VEHICLE-GI-ladle_car 적재 소재 선택 VEHICLE-GI-ladle_car 용강 PROD-GI · MAT-PROD-GI:02 TRANSPORT-GI-02 출발 제강·출강 TRANSPORT-GI-02 도착 연주 23 t 운송 중":
            - cell "VEHICLE-GI-ladle_car 적재 소재 선택 VEHICLE-GI-ladle_car":
              - button "VEHICLE-GI-ladle_car 적재 소재 선택" [pressed]: 용강 운반차
              - text: VEHICLE-GI-ladle_car
            - cell "용강 PROD-GI · MAT-PROD-GI:02":
              - strong: 용강
              - text: PROD-GI · MAT-PROD-GI:02
            - cell "TRANSPORT-GI-02 출발 제강·출강 TRANSPORT-GI-02 도착 연주":
              - button "TRANSPORT-GI-02 출발 제강·출강": 제강·출강
              - button "TRANSPORT-GI-02 도착 연주": 연주
            - cell "23 t"
            - cell "운송 중"
          - row "VEHICLE-HGI-flatbed_truck 적재 소재 선택 VEHICLE-HGI-flatbed_truck 슬래브 PROD-HGI · MAT-PROD-HGI:03 TRANSPORT-HGI-03 출발 연주 TRANSPORT-HGI-03 도착 열연 26 t 운송 중":
            - cell "VEHICLE-HGI-flatbed_truck 적재 소재 선택 VEHICLE-HGI-flatbed_truck":
              - button "VEHICLE-HGI-flatbed_truck 적재 소재 선택": 소재 운반 트럭
              - text: VEHICLE-HGI-flatbed_truck
            - cell "슬래브 PROD-HGI · MAT-PROD-HGI:03":
              - strong: 슬래브
              - text: PROD-HGI · MAT-PROD-HGI:03
            - cell "TRANSPORT-HGI-03 출발 연주 TRANSPORT-HGI-03 도착 열연":
              - button "TRANSPORT-HGI-03 출발 연주": 연주
              - button "TRANSPORT-HGI-03 도착 열연": 열연
            - cell "26 t"
            - cell "운송 중"
    - paragraph: 공정 간 이동은 서버가 관리합니다. 도착이 확인된 뒤 다음 작업을 시작합니다.
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
          - row "PROD-BILLET 용선 MAT-PROD-BILLET:01 후공정 소재 빌렛 운송 중 제선·출선 → 제강·출강 · VEHICLE-BILLET-hot_metal_car 20 t 22% 0.2222":
            - cell "PROD-BILLET":
              - button "PROD-BILLET"
            - cell "용선 MAT-PROD-BILLET:01":
              - strong: 용선
              - text: MAT-PROD-BILLET:01
            - cell "후공정 소재"
            - cell "빌렛"
            - cell "운송 중 제선·출선 → 제강·출강 · VEHICLE-BILLET-hot_metal_car"
            - cell "20 t"
            - cell "22% 0.2222":
              - text: 22%
              - progressbar "PROD-BILLET 생산 진행률"
          - row "PROD-HR 용선 MAT-PROD-HR:01 후공정 소재 열연 제강·출강 21 t 18% 0.1818":
            - cell "PROD-HR":
              - button "PROD-HR"
            - cell "용선 MAT-PROD-HR:01":
              - strong: 용선
              - text: MAT-PROD-HR:01
            - cell "후공정 소재"
            - cell "열연"
            - cell "제강·출강"
            - cell "21 t"
            - cell "18% 0.1818":
              - text: 18%
              - progressbar "PROD-HR 생산 진행률"
          - row "PROD-CR 용강 MAT-PROD-CR:02 후공정 소재 냉연 제강·출강 22 t 21% 0.2143":
            - cell "PROD-CR":
              - button "PROD-CR"
            - cell "용강 MAT-PROD-CR:02":
              - strong: 용강
              - text: MAT-PROD-CR:02
            - cell "후공정 소재"
            - cell "냉연"
            - cell "제강·출강"
            - cell "22 t"
            - cell "21% 0.2143":
              - text: 21%
              - progressbar "PROD-CR 생산 진행률"
          - row "PROD-GI 용강 MAT-PROD-GI:02 후공정 소재 GI · 용융아연 운송 중 제강·출강 → 연주 · VEHICLE-GI-ladle_car 23 t 27% 0.2667":
            - cell "PROD-GI":
              - button "PROD-GI" [pressed]
            - cell "용강 MAT-PROD-GI:02":
              - strong: 용강
              - text: MAT-PROD-GI:02
            - cell "후공정 소재"
            - cell "GI · 용융아연"
            - cell "운송 중 제강·출강 → 연주 · VEHICLE-GI-ladle_car"
            - cell "23 t"
            - cell "27% 0.2667":
              - text: 27%
              - progressbar "PROD-GI 생산 진행률"
          - row "PROD-GA 용강 MAT-PROD-GA:02 후공정 소재 GA · 합금화아연 연주 24 t 25% 0.25":
            - cell "PROD-GA":
              - button "PROD-GA"
            - cell "용강 MAT-PROD-GA:02":
              - strong: 용강
              - text: MAT-PROD-GA:02
            - cell "후공정 소재"
            - cell "GA · 합금화아연"
            - cell "연주"
            - cell "24 t"
            - cell "25% 0.25":
              - text: 25%
              - progressbar "PROD-GA 생산 진행률"
          - row "PROD-EG 슬래브 MAT-PROD-EG:03 후공정 소재 EG · 전기아연 연주 25 t 33% 0.3333":
            - cell "PROD-EG":
              - button "PROD-EG"
            - cell "슬래브 MAT-PROD-EG:03":
              - strong: 슬래브
              - text: MAT-PROD-EG:03
            - cell "후공정 소재"
            - cell "EG · 전기아연"
            - cell "연주"
            - cell "25 t"
            - cell "33% 0.3333":
              - text: 33%
              - progressbar "PROD-EG 생산 진행률"
          - row "PROD-HGI 슬래브 MAT-PROD-HGI:03 후공정 소재 HGI · 열연도금 운송 중 연주 → 열연 · VEHICLE-HGI-flatbed_truck 26 t 46% 0.4615":
            - cell "PROD-HGI":
              - button "PROD-HGI"
            - cell "슬래브 MAT-PROD-HGI:03":
              - strong: 슬래브
              - text: MAT-PROD-HGI:03
            - cell "후공정 소재"
            - cell "HGI · 열연도금"
            - cell "운송 중 연주 → 열연 · VEHICLE-HGI-flatbed_truck"
            - cell "26 t"
            - cell "46% 0.4615":
              - text: 46%
              - progressbar "PROD-HGI 생산 진행률"
    - text: 생산 전용 합성 배치 · 소재 변환 이력은 중복 재고로 합산하지 않습니다.
  - paragraph: 공정·설비·질량은 설명용 합성 데이터입니다. 블룸·빌렛은 반제품 판매 경로이며, 봉형강·선재 후공정은 이번 범위에 포함하지 않습니다.
```

# Test source

```ts
  80  |         expect(batch.current_location_id).toBe(active[0].vehicle_id); expect(facilities).toEqual([]);
  81  |         expect([active[0].material_id, active[0].material_form, active[0].mass_kg]).toEqual([batch.material_id, batch.material_form, batch.mass_kg]);
  82  |         expect(batch.steps.filter(step => step.status === 'running')).toEqual([]);
  83  |       } else {
  84  |         expect(batch.active_transport_id).toBeNull(); expect(facilities).toHaveLength(1);
  85  |         expect(batch.current_location_id).toBe(facilities[0]?.id);
  86  |       }
  87  |       for (let index = 1; index < batch.steps.length; index++) {
  88  |         const previous = batch.steps[index - 1]!; const next = batch.steps[index]!;
  89  |         expect(next.start_tick - previous.end_tick).toBe(previous.stage_id === next.stage_id ? 0 : 1);
  90  |       }
  91  |     }
  92  |   }
  93  |   const gi6 = states[6]!.batches.find(batch => batch.id === 'PROD-GI')!;
  94  |   const leg = states[6]!.transports.find(item => item.id === gi6.active_transport_id)!;
  95  |   expect({ from: leg.from_stage, to: leg.to_stage, start: leg.start_tick, end: leg.end_tick, cargo: leg.material_form, mass: leg.mass_kg, kind: leg.vehicle_kind }).toEqual({ from: 'hot_rolling', to: 'cold_rolling', start: 6, end: 7, cargo: 'HR', mass: 23000, kind: 'flatbed_truck' });
  96  |   expect(gi6.steps.filter(step => step.stage_id === 'cold_rolling').map(step => step.status)).toEqual(['queued', 'queued', 'queued']);
  97  |   const gi7 = states[7]!.batches.find(batch => batch.id === 'PROD-GI')!;
  98  |   expect([gi7.status, gi7.current_location_id, gi7.equipment_id]).toEqual(['running', 'cold_rolling', 'PICKLE-01']);
  99  |   expect(states[7]!.transports.find(item => item.id === leg.id)?.status).toBe('completed');
  100 |   expect(states[24]!.completed_mass_kg).toBe(198000);
  101 |   await save('timeline', states);
  102 |   await clickCommand(page, 'Reset simulation', 'reset');
  103 |   for (let tick = 0; tick <= 7; tick++) {
  104 |     const replay = tick === 0 ? await getWorld(request) : await clickCommand(page, 'Advance one step', 'step');
  105 |     expect(replay.production).toEqual(states[tick]);
  106 |   }
  107 |   await save('replay', { matchedTicks: [0, 1, 2, 3, 4, 5, 6, 7], result: 'exact production equality' });
  108 | });
  109 | 
  110 | test('loaded 3D truck is selectable, moves, freezes on pause, resumes and resets', async ({ page, request }) => {
  111 |   const canvas = page.locator('canvas'); await expect(canvas).toBeVisible(); await page.waitForTimeout(700);
  112 |   await capture(page, 'overview-specialist-carriers');
  113 |   const overviewBox = await canvas.boundingBox(); if (!overviewBox) throw new Error('Missing overview canvas');
  114 |   const overviewCamera = new OrthographicCamera(-overviewBox.width / 2, overviewBox.width / 2, overviewBox.height / 2, -overviewBox.height / 2, 0.1, 150);
  115 |   overviewCamera.position.set(35, 34, 42); overviewCamera.zoom = Math.min(overviewBox.width / 42, overviewBox.height / 29);
  116 |   overviewCamera.lookAt(0, 0, 0); overviewCamera.updateProjectionMatrix(); overviewCamera.updateMatrixWorld();
  117 |   const overviewPoint = new Vector3(7.66, 0.962, 0).project(overviewCamera);
  118 |   await page.mouse.click(overviewBox.x + (overviewPoint.x + 1) * overviewBox.width / 2, overviewBox.y + (1 - overviewPoint.y) * overviewBox.height / 2);
  119 |   await expect(inspector(page)).toContainText('PROD-HGI');
  120 |   await expect(page.getByRole('heading', { name: '생산 오버뷰', exact: true })).toBeVisible();
  121 |   await capture(page, 'overview-truck-selected');
  122 |   await page.getByRole('region', { name: '생산 작업 목록' }).getByRole('button', { name: 'PROD-GI', exact: true }).click();
  123 |   await page.getByRole('navigation', { name: '생산 공정 선택' }).getByRole('button', { name: /열연/ }).click();
  124 |   await canvas.scrollIntoViewIfNeeded(); await page.waitForTimeout(300);
  125 |   const box = await canvas.boundingBox(); if (!box) throw new Error('Missing canvas');
  126 |   const camera = new OrthographicCamera(-box.width / 2, box.width / 2, box.height / 2, -box.height / 2, 0.1, 150);
  127 |   camera.position.set(15, 15, 21.3); camera.zoom = Math.min(box.width / 18, box.height / 22.6); camera.lookAt(0, 0, 3.3); camera.updateProjectionMatrix(); camera.updateMatrixWorld();
  128 |   const projected = new Vector3(-0.45, 1.215, 6.6).project(camera);
  129 |   await page.mouse.click(box.x + (projected.x + 1) * box.width / 2, box.y + (1 - projected.y) * box.height / 2);
  130 |   await expect(inspector(page)).toContainText('PROD-HGI');
  131 |   await expect(inspector(page)).toContainText('운송 중');
  132 |   await page.getByLabel('제품 경로', { exact: true }).selectOption('HGI');
  133 |   await synchronizeClock(page, request);
  134 |   const initial = await capture(page, 'truck-loaded-paused');
  135 |   const initialWorld = await getWorld(request);
  136 |   await clickCommand(page, 'Play simulation', 'play');
  137 |   await page.waitForTimeout(60);
  138 |   const paused = await clickCommand(page, 'Pause simulation', 'pause');
  139 |   expect(paused.simulation.tick).toBe(initialWorld.simulation.tick);
  140 |   const moved = await capture(page, 'truck-moved-paused');
  141 |   const movingDiff = await difference(page, initial, moved); expect(movingDiff.count).toBeGreaterThan(50);
  142 |   await page.waitForTimeout(650);
  143 |   const frozen = await capture(page, 'truck-frozen');
  144 |   const pausedDiff = await difference(page, moved, frozen); expect(pausedDiff.count).toBe(0);
  145 |   expect((await getWorld(request)).simulation.tick).toBe(paused.simulation.tick);
  146 |   await page.getByLabel('Simulation speed', { exact: true }).selectOption('2');
  147 |   await clickCommand(page, 'Play simulation', 'play');
  148 |   await expect.poll(async () => (await getWorld(request)).simulation.tick).toBeGreaterThan(paused.simulation.tick);
  149 |   const resumed = await clickCommand(page, 'Pause simulation', 'pause'); expect(resumed.simulation.speed).toBe(2);
  150 |   await capture(page, 'truck-resumed-arrival');
  151 |   await clickCommand(page, 'Reset simulation', 'reset');
  152 |   expect((await getWorld(request)).production).toEqual(initialWorld.production);
  153 |   await page.waitForTimeout(250);
  154 |   const reset = await capture(page, 'truck-reset');
  155 |   const resetDiff = await difference(page, initial, reset); expect(resetDiff.count).toBe(0);
  156 |   await save('canvas-pixel-evidence', { movingDiff, pausedDiff, resetDiff, beforeTick: initialWorld.simulation.tick, pausedTick: paused.simulation.tick, resumedTick: resumed.simulation.tick, selectionClick: { x: projected.x, y: projected.y } });
  157 | });
  158 | 
  159 | test('390px 2D transport tracking survives WebGL loss and permits arrival navigation', async ({ page }) => {
  160 |   await page.setViewportSize({ width: 390, height: 844 });
  161 |   const canvas = page.locator('canvas'); await expect(canvas).toBeVisible(); await page.waitForTimeout(400);
  162 |   expect(await canvas.evaluate(element => {
  163 |     const extension = (element as HTMLCanvasElement).getContext('webgl2')?.getExtension('WEBGL_lose_context');
  164 |     if (!extension) return false; extension.loseContext(); return true;
  165 |   })).toBe(true);
  166 |   await page.getByRole('button', { name: '생산 목록 열기', exact: true }).click();
  167 |   await expect(page.getByRole('button', { name: '2D 공정', exact: true })).toHaveAttribute('aria-pressed', 'true');
  168 |   const transportTable = page.getByRole('region', { name: '생산 운송 표', exact: true });
  169 |   await transportTable.getByRole('button', { name: 'VEHICLE-HGI-flatbed_truck 적재 소재 선택', exact: true }).click();
  170 |   await expect(inspector(page)).toContainText('PROD-HGI');
  171 |   await page.getByLabel('제품 경로', { exact: true }).selectOption('HGI');
  172 |   await expect(transportTable.getByRole('row')).toHaveCount(2);
  173 |   await expect(transportTable.getByRole('row').last()).toContainText('26 t');
  174 |   await expect(inspector(page)).toContainText('VEHICLE-HGI-flatbed_truck');
  175 |   await expect(inspector(page)).toContainText('운송 중');
  176 |   await page.screenshot({ path: `${evidence}/transport-mobile-fallback.png`, fullPage: true });
  177 |   const layout = await page.evaluate(() => ({ width: innerWidth, document: document.documentElement.scrollWidth }));
  178 |   expect(layout.document).toBeLessThanOrEqual(layout.width); await save('mobile-layout', layout);
  179 |   await inspector(page).getByRole('button', { name: /도착/ }).click();
> 180 |   await expect(page.getByRole('heading', { name: '열연 공정', exact: true })).toBeVisible();
      |                                                                           ^ Error: expect(locator).toBeVisible() failed
  181 |   await clickCommand(page, 'Advance one step', 'step');
  182 |   await expect(inspector(page)).not.toContainText('운송 중');
  183 |   await expect(inspector(page)).toContainText('현재 공정 · 열연');
  184 |   await page.screenshot({ path: `${evidence}/transport-mobile-arrived.png`, fullPage: true });
  185 | });
  186 | 
  187 | 
  188 | test('reduced motion holds loaded transport still between authoritative ticks', async ({ page, request }) => {
  189 |   await page.emulateMedia({ reducedMotion: 'reduce' });
  190 |   await page.getByLabel('제품 경로', { exact: true }).selectOption('HGI');
  191 |   const canvas = page.locator('canvas'); await expect(canvas).toBeVisible(); await canvas.scrollIntoViewIfNeeded();
  192 |   await page.waitForTimeout(500);
  193 |   await synchronizeClock(page, request);
  194 |   const before = await capture(page, 'reduced-before');
  195 |   const beforeWorld = await getWorld(request);
  196 |   await clickCommand(page, 'Play simulation', 'play');
  197 |   await page.waitForTimeout(100);
  198 |   const paused = await clickCommand(page, 'Pause simulation', 'pause');
  199 |   expect(paused.simulation.tick).toBe(beforeWorld.simulation.tick);
  200 |   const after = await capture(page, 'reduced-after');
  201 |   const reducedDiff = await difference(page, before, after); expect(reducedDiff.count).toBe(0);
  202 |   await clickCommand(page, 'Advance one step', 'step');
  203 |   const arrived = await capture(page, 'reduced-arrival');
  204 |   const arrivalDiff = await difference(page, after, arrived); expect(arrivalDiff.count).toBeGreaterThan(50);
  205 |   await save('reduced-motion', { reducedDiff, arrivalDiff, tick: paused.simulation.tick });
  206 | });
  207 | 
```