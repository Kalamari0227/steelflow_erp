# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: transport.spec.ts >> 390px 2D transport tracking survives WebGL loss and permits arrival navigation
- Location: tests/transport.spec.ts:149:1

# Error details

```
Test timeout of 45000ms exceeded.
```

```
Error: page.waitForResponse: Test timeout of 45000ms exceeded.
```

# Page snapshot

```yaml
- generic [ref=f1e3]:
  - link "Skip to operations" [ref=f1e4] [cursor=pointer]:
    - /url: "#main-content"
  - navigation "Main navigation" [ref=f1e5]:
    - link "SteelFlow home" [ref=f1e6] [cursor=pointer]:
      - /url: "#main-content"
    - button "Operations overview" [ref=f1e9] [cursor=pointer]
    - button "Inventory view" [ref=f1e15] [cursor=pointer]
    - button "Open orders" [ref=f1e26] [cursor=pointer]
    - button "Open shipments" [ref=f1e30] [cursor=pointer]
    - button "Open event history" [ref=f1e35] [cursor=pointer]
    - generic "Local demo operator" [ref=f1e39]: SF
  - generic [ref=f1e40]:
    - banner [ref=f1e41]:
      - generic [ref=f1e42]:
        - text: SteelFlow
        - generic [ref=f1e43]: 3D
      - generic [ref=f1e44]: Synthetic environment
    - main [ref=f1e47]:
      - navigation "워크스페이스 선택" [ref=f1e48]:
        - button "물류 오버뷰" [ref=f1e49] [cursor=pointer]
        - button "생산 공정" [pressed] [ref=f1e55] [cursor=pointer]
      - generic [ref=f1e58]:
        - generic [ref=f1e60]:
          - button "생산 오버뷰" [ref=f1e62] [cursor=pointer]
          - heading "생산 오버뷰" [level=1] [ref=f1e63]
          - paragraph [ref=f1e65]: 소재가 제품이 되는 과정. 공정을 선택해 작업 흐름 안으로 들어가세요.
        - generic "생산 배치 현황" [ref=f1e66]:
          - generic [ref=f1e67]:
            - generic [ref=f1e70]: 작업 중
            - strong [ref=f1e71]: 6배치
          - generic [ref=f1e72]:
            - generic [ref=f1e75]: 생산 완료
            - strong [ref=f1e76]:
              - text: "0"
              - generic [ref=f1e77]: / 9
          - generic [ref=f1e78]:
            - generic [ref=f1e82]: 생산 배치 총량
            - strong [ref=f1e83]: 198t
          - generic [ref=f1e84]:
            - generic [ref=f1e90]: 공정 간 운송
            - strong [ref=f1e91]: 3대
        - generic [ref=f1e92]:
          - strong [ref=f1e98]: 통합 생산 공정
          - generic [ref=f1e99]:
            - text: 제품 경로
            - combobox "제품 경로" [ref=f1e100]:
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
          - generic [ref=f1e101]:
            - text: 시나리오
            - combobox "생산 시나리오" [ref=f1e102]:
              - option "정상 생산" [selected]
              - option "열연 지연"
              - option "대체 라인 회복"
        - generic [ref=f1e103]:
          - region "생산 공정 시각화" [ref=f1e104]:
            - generic [ref=f1e105]:
              - generic [ref=f1e106]: 전체 공장 · 서버 상태 연결
              - generic [ref=f1e108]:
                - button "3D 공정" [pressed] [ref=f1e109] [cursor=pointer]
                - button "2D 공정" [ref=f1e113] [cursor=pointer]
            - generic [ref=f1e115]:
              - generic "대화형 생산 모형. 설비 또는 배치를 선택하세요. 드래그로 회전하고 스크롤로 확대합니다. 공정과 배치는 화면 옆 목록에서도 선택할 수 있습니다." [ref=f1e116]
              - button "생산 카메라 초기화" [ref=f1e119] [cursor=pointer]
              - generic: 공정을 클릭해 상세 화면으로 이동
            - navigation "생산 공정 선택" [ref=f1e126]:
              - button "01 제선·출선 1 작업 중" [ref=f1e127] [cursor=pointer]:
                - generic [ref=f1e128]: "01"
                - strong [ref=f1e129]: 제선·출선
                - generic [ref=f1e130]: 1 작업 중
              - button "02 제강·출강 2 작업 중" [ref=f1e131] [cursor=pointer]:
                - generic [ref=f1e132]: "02"
                - strong [ref=f1e133]: 제강·출강
                - generic [ref=f1e134]: 2 작업 중
              - button "03 연주 2 작업 중" [ref=f1e135] [cursor=pointer]:
                - generic [ref=f1e136]: "03"
                - strong [ref=f1e137]: 연주
                - generic [ref=f1e138]: 2 작업 중
              - button "04 열연 1 작업 중" [ref=f1e139] [cursor=pointer]:
                - generic [ref=f1e140]: "04"
                - strong [ref=f1e141]: 열연
                - generic [ref=f1e142]: 1 작업 중
              - button "05 냉연 현재 작업 없음" [ref=f1e143] [cursor=pointer]:
                - generic [ref=f1e144]: "05"
                - strong [ref=f1e145]: 냉연
                - generic [ref=f1e146]: 현재 작업 없음
              - button "06 도금 현재 작업 없음" [ref=f1e147] [cursor=pointer]:
                - generic [ref=f1e148]: "06"
                - strong [ref=f1e149]: 도금
                - generic [ref=f1e150]: 현재 작업 없음
              - button "07 정정·검사 현재 작업 없음" [ref=f1e151] [cursor=pointer]:
                - generic [ref=f1e152]: "07"
                - strong [ref=f1e153]: 정정·검사
                - generic [ref=f1e154]: 현재 작업 없음
              - button "08 제품 재고 현재 작업 없음" [ref=f1e155] [cursor=pointer]:
                - generic [ref=f1e156]: "08"
                - strong [ref=f1e157]: 제품 재고
                - generic [ref=f1e158]: 현재 작업 없음
            - generic [ref=f1e159]:
              - button "Play simulation" [ref=f1e160] [cursor=pointer]
              - button "Advance one step" [ref=f1e163] [cursor=pointer]
              - button "Reset simulation" [ref=f1e166] [cursor=pointer]
              - generic [ref=f1e171]:
                - generic [ref=f1e172]: Simulation speed
                - combobox "Simulation speed" [ref=f1e173]:
                  - option "1× speed" [selected]
                  - option "2× speed"
                  - option "4× speed"
              - generic [ref=f1e174]:
                - generic [ref=f1e175]:
                  - generic [ref=f1e176]: 08:30 UTC
                  - generic [ref=f1e177]: Step 1 / 24
                - progressbar "Simulation progress" [ref=f1e178]
          - complementary "선택 소재 상세" [ref=f1e180]:
            - generic [ref=f1e181]:
              - generic [ref=f1e182]: 소재 추적
              - generic [ref=f1e187]: PROD-GI
            - generic [ref=f1e188]:
              - text: CURRENT MATERIAL
              - heading "용강" [level=2] [ref=f1e189]
              - generic [ref=f1e190]: 후공정 소재
              - generic [ref=f1e191]:
                - generic [ref=f1e195]: 목표 제품
                - strong [ref=f1e196]: GI · 용융아연
              - generic [ref=f1e197]:
                - generic [ref=f1e198]:
                  - generic [ref=f1e199]: 배치 질량
                  - strong [ref=f1e200]: 23 t
                - generic [ref=f1e201]:
                  - generic [ref=f1e202]: 작업 상태
                  - strong [ref=f1e203]: 작업 중
              - button "현재 공정 · 연주" [ref=f1e204] [cursor=pointer]
              - paragraph [ref=f1e208]: 다음 공정 · 열연
            - generic [ref=f1e209]:
              - heading "소재 변환 이력 3" [level=3] [ref=f1e210]:
                - text: 소재 변환 이력
                - generic [ref=f1e211]: "3"
              - list "소재 계보" [ref=f1e212]:
                - listitem [ref=f1e213]:
                  - generic [ref=f1e216]:
                    - strong [ref=f1e217]: 철원료
                    - generic [ref=f1e218]: 소재 · 제선·출선
                    - generic [ref=f1e219]: MAT-PROD-GI:00
                - listitem [ref=f1e220]:
                  - generic [ref=f1e223]:
                    - strong [ref=f1e224]: 용선
                    - generic [ref=f1e225]: 소재 · 제선·출선
                    - generic [ref=f1e226]: MAT-PROD-GI:01
                - listitem [ref=f1e227]:
                  - generic [ref=f1e239]:
                    - strong [ref=f1e240]: 용강
                    - generic [ref=f1e241]: 소재 · 제강·출강
                    - generic [ref=f1e242]: MAT-PROD-GI:02
            - paragraph [ref=f1e243]: 형태와 용도는 별개입니다. 같은 열연·냉연 코일도 생산 경로에 따라 판매 제품 또는 다음 공정의 소재가 됩니다.
        - region "선택 배치 생산 경로" [ref=f1e244]:
          - generic [ref=f1e245]:
            - generic [ref=f1e246]: MATERIAL ROUTE
            - strong [ref=f1e247]: PROD-GI
          - list [ref=f1e248]:
            - listitem [ref=f1e249]:
              - button "제선·출선 · 완료" [ref=f1e250] [cursor=pointer]:
                - text: 제선·출선
                - generic [ref=f1e253]: · 완료
            - listitem [ref=f1e256]:
              - button "제강·출강 · 완료" [ref=f1e257] [cursor=pointer]:
                - text: 제강·출강
                - generic [ref=f1e260]: · 완료
            - listitem [ref=f1e263]:
              - button "연주 · 작업 중" [ref=f1e264] [cursor=pointer]:
                - text: 연주
                - generic [ref=f1e268]: · 작업 중
            - listitem [ref=f1e271]:
              - button "열연 · 대기" [ref=f1e272] [cursor=pointer]:
                - text: 열연
                - generic [ref=f1e276]: · 대기
            - listitem [ref=f1e279]:
              - button "냉연 · 대기" [ref=f1e280] [cursor=pointer]:
                - text: 냉연
                - generic [ref=f1e284]: · 대기
            - listitem [ref=f1e287]:
              - button "도금 · 대기" [ref=f1e288] [cursor=pointer]:
                - text: 도금
                - generic [ref=f1e292]: · 대기
            - listitem [ref=f1e295]:
              - button "정정·검사 · 대기" [ref=f1e296] [cursor=pointer]:
                - text: 정정·검사
                - generic [ref=f1e300]: · 대기
            - listitem [ref=f1e303]:
              - button "제품 재고 · 대기" [ref=f1e304] [cursor=pointer]:
                - text: 제품 재고
                - generic [ref=f1e308]: · 대기
        - region "공정 간 운송" [ref=f1e309]:
          - generic [ref=f1e310]:
            - heading "공정 간 운송" [level=2] [ref=f1e311]
            - generic [ref=f1e317]: 운송 중 3대 · 66 t
          - generic [ref=f1e318]:
            - generic [ref=f1e319]:
              - button "운송 중" [pressed] [ref=f1e320] [cursor=pointer]
              - button "선택 배치 경로" [ref=f1e321] [cursor=pointer]
            - generic [ref=f1e322]: 차량을 선택해 적재 소재를 추적하세요
          - region "생산 운송 표" [ref=f1e323]:
            - table [ref=f1e324]:
              - caption [ref=f1e325]: 공정 간 소재 운송. 현재 차량, 화물, 출발지와 도착지를 확인합니다.
              - rowgroup [ref=f1e326]:
                - row [ref=f1e327]:
                  - columnheader "운반 차량" [ref=f1e328]
                  - columnheader "적재 소재" [ref=f1e329]
                  - columnheader "운송 경로" [ref=f1e330]
                  - columnheader "질량" [ref=f1e331]
                  - columnheader "상태" [ref=f1e332]
              - rowgroup [ref=f1e333]:
                - row [ref=f1e334]:
                  - cell "VEHICLE-BLOOM-hot_metal_car 적재 소재 선택 VEHICLE-BLOOM-hot_metal_car" [ref=f1e335]:
                    - button "VEHICLE-BLOOM-hot_metal_car 적재 소재 선택" [ref=f1e336] [cursor=pointer]: 용선 운반차
                    - generic [ref=f1e337]: VEHICLE-BLOOM-hot_metal_car
                  - cell "용선 PROD-BLOOM · MAT-PROD-BLOOM:01" [ref=f1e338]:
                    - strong [ref=f1e339]: 용선
                    - generic [ref=f1e340]: PROD-BLOOM · MAT-PROD-BLOOM:01
                  - cell [ref=f1e341]:
                    - generic [ref=f1e342]:
                      - button "TRANSPORT-BLOOM-01 출발 제선·출선" [ref=f1e343] [cursor=pointer]: 제선·출선
                      - button "TRANSPORT-BLOOM-01 도착 제강·출강" [ref=f1e346] [cursor=pointer]: 제강·출강
                  - cell "19 t" [ref=f1e347]
                  - cell "운송 중" [ref=f1e348]
                - row [ref=f1e350]:
                  - cell "VEHICLE-CR-ladle_car 적재 소재 선택 VEHICLE-CR-ladle_car" [ref=f1e351]:
                    - button "VEHICLE-CR-ladle_car 적재 소재 선택" [ref=f1e352] [cursor=pointer]: 용강 운반차
                    - generic [ref=f1e353]: VEHICLE-CR-ladle_car
                  - cell "용강 PROD-CR · MAT-PROD-CR:02" [ref=f1e354]:
                    - strong [ref=f1e355]: 용강
                    - generic [ref=f1e356]: PROD-CR · MAT-PROD-CR:02
                  - cell [ref=f1e357]:
                    - generic [ref=f1e358]:
                      - button "TRANSPORT-CR-02 출발 제강·출강" [ref=f1e359] [cursor=pointer]: 제강·출강
                      - button "TRANSPORT-CR-02 도착 연주" [ref=f1e362] [cursor=pointer]: 연주
                  - cell "22 t" [ref=f1e363]
                  - cell "운송 중" [ref=f1e364]
                - row [ref=f1e366]:
                  - cell "VEHICLE-EG-flatbed_truck 적재 소재 선택 VEHICLE-EG-flatbed_truck" [ref=f1e367]:
                    - button "VEHICLE-EG-flatbed_truck 적재 소재 선택" [ref=f1e368] [cursor=pointer]: 소재 운반 트럭
                    - generic [ref=f1e369]: VEHICLE-EG-flatbed_truck
                  - cell "슬래브 PROD-EG · MAT-PROD-EG:03" [ref=f1e370]:
                    - strong [ref=f1e371]: 슬래브
                    - generic [ref=f1e372]: PROD-EG · MAT-PROD-EG:03
                  - cell [ref=f1e373]:
                    - generic [ref=f1e374]:
                      - button "TRANSPORT-EG-03 출발 연주" [ref=f1e375] [cursor=pointer]: 연주
                      - button "TRANSPORT-EG-03 도착 열연" [ref=f1e378] [cursor=pointer]: 열연
                  - cell "25 t" [ref=f1e379]
                  - cell "운송 중" [ref=f1e380]
          - paragraph [ref=f1e382]: 공정 간 이동은 서버가 관리합니다. 도착이 확인된 뒤 다음 작업을 시작합니다.
        - region "생산 작업 목록" [ref=f1e383]:
          - generic [ref=f1e384]:
            - heading "전체 생산 배치" [level=2] [ref=f1e385]
            - generic [ref=f1e386]: 9개 배치 · 198 t
          - region "생산 소재 표" [ref=f1e387]:
            - table [ref=f1e388]:
              - caption [ref=f1e389]: 합성 생산 배치. 배치 선택으로 경로와 소재 계보를 확인합니다.
              - rowgroup [ref=f1e390]:
                - row [ref=f1e391]:
                  - columnheader "생산 배치" [ref=f1e392]
                  - columnheader "현재 소재" [ref=f1e393]
                  - columnheader "용도" [ref=f1e394]
                  - columnheader "목표 제품" [ref=f1e395]
                  - columnheader "현재 공정" [ref=f1e396]
                  - columnheader "질량" [ref=f1e397]
                  - columnheader "생산 진행" [ref=f1e398]
              - rowgroup [ref=f1e399]:
                - row [ref=f1e400]:
                  - cell [ref=f1e401]:
                    - button "PROD-SLAB" [ref=f1e402] [cursor=pointer]
                  - cell "철원료 MAT-PROD-SLAB:00" [ref=f1e403]:
                    - strong [ref=f1e404]: 철원료
                    - generic [ref=f1e405]: MAT-PROD-SLAB:00
                  - cell "후공정 소재" [ref=f1e406]
                  - cell "슬래브" [ref=f1e408]
                  - cell "제선·출선" [ref=f1e409]
                  - cell "18 t" [ref=f1e410]
                  - cell "11% 0.1111" [ref=f1e411]:
                    - generic [ref=f1e412]:
                      - generic [ref=f1e413]: 11%
                      - progressbar "PROD-SLAB 생산 진행률" [ref=f1e414]
                - row [ref=f1e415]:
                  - cell [ref=f1e416]:
                    - button "PROD-BLOOM" [ref=f1e417] [cursor=pointer]
                  - cell "용선 MAT-PROD-BLOOM:01" [ref=f1e418]:
                    - strong [ref=f1e419]: 용선
                    - generic [ref=f1e420]: MAT-PROD-BLOOM:01
                  - cell "후공정 소재" [ref=f1e421]
                  - cell "블룸" [ref=f1e423]
                  - cell "운송 중 제선·출선 → 제강·출강 · VEHICLE-BLOOM-hot_metal_car" [ref=f1e424]:
                    - generic [ref=f1e425]: 운송 중
                    - generic [ref=f1e426]: 제선·출선 → 제강·출강 · VEHICLE-BLOOM-hot_metal_car
                  - cell "19 t" [ref=f1e427]
                  - cell "22% 0.2222" [ref=f1e428]:
                    - generic [ref=f1e429]:
                      - generic [ref=f1e430]: 22%
                      - progressbar "PROD-BLOOM 생산 진행률" [ref=f1e431]
                - row [ref=f1e432]:
                  - cell [ref=f1e433]:
                    - button "PROD-BILLET" [ref=f1e434] [cursor=pointer]
                  - cell "용선 MAT-PROD-BILLET:01" [ref=f1e435]:
                    - strong [ref=f1e436]: 용선
                    - generic [ref=f1e437]: MAT-PROD-BILLET:01
                  - cell "후공정 소재" [ref=f1e438]
                  - cell "빌렛" [ref=f1e440]
                  - cell "제강·출강" [ref=f1e441]
                  - cell "20 t" [ref=f1e442]
                  - cell "22% 0.2222" [ref=f1e443]:
                    - generic [ref=f1e444]:
                      - generic [ref=f1e445]: 22%
                      - progressbar "PROD-BILLET 생산 진행률" [ref=f1e446]
                - row [ref=f1e447]:
                  - cell [ref=f1e448]:
                    - button "PROD-HR" [ref=f1e449] [cursor=pointer]
                  - cell "용강 MAT-PROD-HR:02" [ref=f1e450]:
                    - strong [ref=f1e451]: 용강
                    - generic [ref=f1e452]: MAT-PROD-HR:02
                  - cell "후공정 소재" [ref=f1e453]
                  - cell "열연" [ref=f1e455]
                  - cell "제강·출강" [ref=f1e456]
                  - cell "21 t" [ref=f1e457]
                  - cell "27% 0.2727" [ref=f1e458]:
                    - generic [ref=f1e459]:
                      - generic [ref=f1e460]: 27%
                      - progressbar "PROD-HR 생산 진행률" [ref=f1e461]
                - row [ref=f1e462]:
                  - cell [ref=f1e463]:
                    - button "PROD-CR" [ref=f1e464] [cursor=pointer]
                  - cell "용강 MAT-PROD-CR:02" [ref=f1e465]:
                    - strong [ref=f1e466]: 용강
                    - generic [ref=f1e467]: MAT-PROD-CR:02
                  - cell "후공정 소재" [ref=f1e468]
                  - cell "냉연" [ref=f1e470]
                  - cell "운송 중 제강·출강 → 연주 · VEHICLE-CR-ladle_car" [ref=f1e471]:
                    - generic [ref=f1e472]: 운송 중
                    - generic [ref=f1e473]: 제강·출강 → 연주 · VEHICLE-CR-ladle_car
                  - cell "22 t" [ref=f1e474]
                  - cell "29% 0.2857" [ref=f1e475]:
                    - generic [ref=f1e476]:
                      - generic [ref=f1e477]: 29%
                      - progressbar "PROD-CR 생산 진행률" [ref=f1e478]
                - row [ref=f1e479]:
                  - cell [ref=f1e480]:
                    - button "PROD-GI" [pressed] [ref=f1e481] [cursor=pointer]
                  - cell "용강 MAT-PROD-GI:02" [ref=f1e482]:
                    - strong [ref=f1e483]: 용강
                    - generic [ref=f1e484]: MAT-PROD-GI:02
                  - cell "후공정 소재" [ref=f1e485]
                  - cell "GI · 용융아연" [ref=f1e487]
                  - cell "연주" [ref=f1e488]
                  - cell "23 t" [ref=f1e489]
                  - cell "27% 0.2667" [ref=f1e490]:
                    - generic [ref=f1e491]:
                      - generic [ref=f1e492]: 27%
                      - progressbar "PROD-GI 생산 진행률" [ref=f1e493]
                - row [ref=f1e494]:
                  - cell [ref=f1e495]:
                    - button "PROD-GA" [ref=f1e496] [cursor=pointer]
                  - cell "슬래브 MAT-PROD-GA:03" [ref=f1e497]:
                    - strong [ref=f1e498]: 슬래브
                    - generic [ref=f1e499]: MAT-PROD-GA:03
                  - cell "후공정 소재" [ref=f1e500]
                  - cell "GA · 합금화아연" [ref=f1e502]
                  - cell "연주" [ref=f1e503]
                  - cell "24 t" [ref=f1e504]
                  - cell "31% 0.3125" [ref=f1e505]:
                    - generic [ref=f1e506]:
                      - generic [ref=f1e507]: 31%
                      - progressbar "PROD-GA 생산 진행률" [ref=f1e508]
                - row [ref=f1e509]:
                  - cell [ref=f1e510]:
                    - button "PROD-EG" [ref=f1e511] [cursor=pointer]
                  - cell "슬래브 MAT-PROD-EG:03" [ref=f1e512]:
                    - strong [ref=f1e513]: 슬래브
                    - generic [ref=f1e514]: MAT-PROD-EG:03
                  - cell "후공정 소재" [ref=f1e515]
                  - cell "EG · 전기아연" [ref=f1e517]
                  - cell "운송 중 연주 → 열연 · VEHICLE-EG-flatbed_truck" [ref=f1e518]:
                    - generic [ref=f1e519]: 운송 중
                    - generic [ref=f1e520]: 연주 → 열연 · VEHICLE-EG-flatbed_truck
                  - cell "25 t" [ref=f1e521]
                  - cell "40% 0.4" [ref=f1e522]:
                    - generic [ref=f1e523]:
                      - generic [ref=f1e524]: 40%
                      - progressbar "PROD-EG 생산 진행률" [ref=f1e525]
                - row [ref=f1e526]:
                  - cell [ref=f1e527]:
                    - button "PROD-HGI" [ref=f1e528] [cursor=pointer]
                  - cell "슬래브 MAT-PROD-HGI:03" [ref=f1e529]:
                    - strong [ref=f1e530]: 슬래브
                    - generic [ref=f1e531]: MAT-PROD-HGI:03
                  - cell "후공정 소재" [ref=f1e532]
                  - cell "HGI · 열연도금" [ref=f1e534]
                  - cell "열연" [ref=f1e535]
                  - cell "26 t" [ref=f1e536]
                  - cell "46% 0.4615" [ref=f1e537]:
                    - generic [ref=f1e538]:
                      - generic [ref=f1e539]: 46%
                      - progressbar "PROD-HGI 생산 진행률" [ref=f1e540]
          - generic [ref=f1e541]: 생산 전용 합성 배치 · 소재 변환 이력은 중복 재고로 합산하지 않습니다.
        - paragraph [ref=f1e542]: 공정·설비·질량은 설명용 합성 데이터입니다. 블룸·빌렛은 반제품 판매 경로이며, 봉형강·선재 후공정은 이번 범위에 포함하지 않습니다.
```

# Test source

```ts
  1   | import { test, expect, type Page, type APIRequestContext } from '@playwright/test';
  2   | import { mkdir, writeFile } from 'node:fs/promises';
  3   | import { OrthographicCamera, Vector3 } from 'three';
  4   | import { WorldSchema, type World } from '../src/contracts';
  5   | 
  6   | const evidence = 'docs/evidence';
  7   | const inspector = (page: Page) => page.getByRole('complementary', { name: '선택 소재 상세' });
  8   | const logs = new WeakMap<Page, { errors: string[]; external: string[] }>();
  9   | async function getWorld(request: APIRequestContext): Promise<World> {
  10  |   const response = await request.get('/api/v1/world');
  11  |   expect(response.ok()).toBe(true);
  12  |   return WorldSchema.parse(await response.json());
  13  | }
  14  | async function clickCommand(page: Page, label: string, endpoint: string) {
> 15  |   const pending = page.waitForResponse(response => response.url().endsWith(`/simulation/${endpoint}`) && response.request().method() === 'POST');
      |                        ^ Error: page.waitForResponse: Test timeout of 45000ms exceeded.
  16  |   await page.getByRole('button', { name: label, exact: true }).click();
  17  |   const response = await pending;
  18  |   expect(response.ok()).toBe(true);
  19  |   return WorldSchema.parse(await response.json());
  20  | }
  21  | async function synchronizeClock(page: Page, request: APIRequestContext) {
  22  |   const playing = await clickCommand(page, 'Play simulation', 'play');
  23  |   await expect.poll(async () => (await getWorld(request)).simulation.tick, { intervals: [20] }).toBeGreaterThan(playing.simulation.tick);
  24  |   await clickCommand(page, 'Pause simulation', 'pause');
  25  |   await clickCommand(page, 'Reset simulation', 'reset');
  26  |   await page.mouse.move(0, 0);
  27  | }
  28  | async function save(name: string, value: unknown) { await writeFile(`${evidence}/transport-${name}.json`, JSON.stringify(value, null, 2)); }
  29  | async function capture(page: Page, name: string) { return page.locator('canvas').screenshot({ path: `${evidence}/transport-${name}.png` }); }
  30  | async function difference(page: Page, before: Buffer, after: Buffer) {
  31  |   return page.evaluate(async ([first, second]) => {
  32  |     const decode = async (encoded: string) => {
  33  |       const image = new Image(); image.src = `data:image/png;base64,${encoded}`; await image.decode();
  34  |       const canvas = document.createElement('canvas'); canvas.width = image.width; canvas.height = image.height;
  35  |       const context = canvas.getContext('2d'); if (!context) throw new Error('Missing image context');
  36  |       context.drawImage(image, 0, 0); return { width: image.width, height: image.height, data: context.getImageData(0, 0, image.width, image.height).data };
  37  |     };
  38  |     const a = await decode(first!); const b = await decode(second!);
  39  |     let count = 0; let x0 = a.width; let y0 = a.height; let x1 = -1; let y1 = -1;
  40  |     for (let pixel = 0; pixel < a.width * a.height; pixel++) {
  41  |       const x = pixel % a.width; const y = Math.floor(pixel / a.width);
  42  |       if (x < 2 || y < 2 || x >= a.width - 2 || y >= a.height - 2) continue;
  43  |       const offset = pixel * 4;
  44  |       if (Math.abs(a.data[offset]! - b.data[offset]!) + Math.abs(a.data[offset + 1]! - b.data[offset + 1]!) + Math.abs(a.data[offset + 2]! - b.data[offset + 2]!) > 15) {
  45  |         count++;
  46  |         x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y);
  47  |       }
  48  |     }
  49  |     return { count, bounds: count ? { x0, y0, x1, y1 } : null, width: a.width, height: a.height };
  50  |   }, [before.toString('base64'), after.toString('base64')]);
  51  | }
  52  | 
  53  | test.beforeEach(async ({ page, request }) => {
  54  |   await mkdir(evidence, { recursive: true });
  55  |   const log = { errors: [] as string[], external: [] as string[] }; logs.set(page, log);
  56  |   page.on('pageerror', error => log.errors.push(error.message));
  57  |   page.on('request', request => { if (!request.url().startsWith('http://127.0.0.1:5174/') && !request.url().startsWith('data:') && !request.url().startsWith('blob:')) log.external.push(request.url()); });
  58  |   expect((await request.post('/api/v1/scenarios/NORMAL/activate')).ok()).toBe(true);
  59  |   await page.goto('/?workspace=production');
  60  |   await expect(page.getByRole('heading', { name: '생산 오버뷰', exact: true })).toBeVisible();
  61  | });
  62  | test.afterEach(async ({ page }, testInfo) => {
  63  |   await testInfo.attach('transport-browser-health', { body: JSON.stringify(logs.get(page)), contentType: 'application/json' });
  64  |   expect(logs.get(page)).toEqual({ errors: [], external: [] });
  65  | });
  66  | 
  67  | test('transport arrival gates processing and never duplicates facility inventory', async ({ page, request }) => {
  68  |   await page.getByRole('button', { name: '2D 공정', exact: true }).click();
  69  |   const states: World['production'][] = [];
  70  |   for (let tick = 0; tick <= 24; tick++) {
  71  |     const state = tick === 0 ? await getWorld(request) : await clickCommand(page, 'Advance one step', 'step');
  72  |     expect(state.simulation.tick).toBe(tick); states.push(state.production);
  73  |     expect(state.production.total_mass_kg).toBe(198000);
  74  |     for (const batch of state.production.batches) {
  75  |       const active = state.production.transports.filter(leg => leg.batch_id === batch.id && leg.status === 'in_transit');
  76  |       const facilities = state.production.stages.filter(stage => stage.batch_ids.includes(batch.id));
  77  |       expect(active.length).toBeLessThanOrEqual(1);
  78  |       if (active[0]) {
  79  |         expect(batch.status).toBe('in_transit'); expect(batch.active_transport_id).toBe(active[0].id);
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
```