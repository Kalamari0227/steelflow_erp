# T2 공개 공정 출처 조사 — 실행 준비

조사일 2026-10-25 KST. 조사자 `/root/uf_t02_source_research`의 읽기 전용 결과를 루트가 보존했다. 제품 구현·시험 결과가 아니다. T1 의존성 충족을 주장하지 않는다.

## 분모와 출처 수준

- 17개는 `journey_products.json`의 데모 제품 경로 수다. 고유 공개 전시관 URL은 8개, 도식 변형은 14개, 로컬 PNG는 15개(후판 2장)다.
- 187개는 기존 데모 경로의 단계 합계이며 합성 입출고 경계도 포함한다. 공개 원문 도식의 모든 기구·단계가 포함됐다는 뜻이 아니다.
- 기존 컴파일 제품 20개, 설비 158개, 종류 40개, 구역 24개, source binding148개는 현재 구현 인벤토리다. 독립 expected 요구사항으로 역생성하지 않는다.
- `docs/evidence/posco-reference/README.md:3`, 7–16행: 기존 브라우저 관찰일2026-10-24. 이번 조사에서 PNG15개 전부 실제 열람했다. myPOSCO8개 URL의 현재 텍스트 접근은 전부 실패했다.
- 비공개 ERP·로그인·자격증명·운영 데이터·외부 3D 자산을 사용하지 않았다. 공개 도식은 제조 개념 근거이며 실측 치수·안전거리·기계 설계 인증이 아니다.

## 원본 경로 인벤토리

각 단계 ID는 제품 ID 뒤 `-01`부터 아래 개수까지 연속이다.

| 제품 | 단계 수 | journey JSON 시작 줄 | source suffix | 로컬 도식 |
|---|---:|---:|---|---|
| hr |9|3|M0z|hot-rolled.png|
| plate |10|97|M10|plate.png, plate-line.png|
| wire |11|200|M11|wire-rod.png|
| cr |11|312|M12|cold-rolled.png|
| gi |11|424|M13|coated.png|
| ga |12|536|M13|coated.png|
| hgi |11|657|M13|coated.png (전용 도식 미확인)|
| eg |11|769|M13|electrogalvanized.png|
| go |13|881|M14|electrical.png|
| ngo |10|1011|M14|electrical-non-oriented.png|
| sts-hr |15|1114|M15|stainless.png|
| sts-cr |11|1262|M15|stainless-cold.png|
| sts-plate |12|1374|M15|stainless-plate.png|
| ti-hr |10|1495|M16|titanium.png|
| ti-cr |10|1598|M16|titanium-cold.png|
| ti-sheet |11|1701|M16|titanium-cold.png|
| ti-plate |9|1813|M16|titanium-plate.png|

이미지 루트: `docs/evidence/posco-reference/`.
URL 형식: `https://my.posco.com/s/exshowrmproductmain?lv1=a0uTJ000004p{suffix}YAE`.
20개 제품에는 위17개와 slab/bloom/billet이 포함된다. 반제품은 별도 합성 상류 블록과 공개 개념 출처를 구분해 등록한다.

앵커: `backend/app/data/operations_routes.json:4` 경계, `:140` 상류, `:319` 레시피; `tests/fixtures/operations_route_expectations.json:10` 단계, `:32` 경계, `:38` 제품; `shared/factory-layout.json:4` 구역, `:222` 설비, `:25739` 바인딩, `:26333` 경로.

## 직접 접근한 공식 대체 자료

| ID | 자료 | 확인 범위와 제한 |
|---|---|---|
| P1 | https://www.poscointl.com/eng/steelProduct | 본문 접근. HR 슬래브→압연/냉각/권취, GI/GA/GI(H)/EG, STS 상위 공정. 개별 현장 배치·치수 근거 아님. |
| P2 | https://www.posco.com/homepage/servlet/FileDownLoad?fileCategory=prdMda&fileNum=12 | 전기강판 PDF 본문, PDF4페이지/인쇄6–7. GO 탈탄/고온소둔/평탄화/절연/자구 처리, NGO 소둔/절연. 역사 자료의 생산능력을 현행 사실로 사용 금지. |
| P3 | https://posco.com/homepage/docs/kor5/dn/product/info/Titanium.pdf | PDF 본문과 검색 추출 인쇄14–15 제조 도식. 해당 페이지 이미지 추출 실패; 분기는 로컬PNG로 교차 확인. 2014년 계획을2026년 실제 설비 구성으로 주장 금지. |
| P4 | https://www.posco.com/homepage/docs/eng6/jsp/dn/company/archive/2011_eng_brochure.pdf | PDF 접근과 공개 검색 추출: 연주 slab/bloom/billet 및 압연. 현재 판매조건 근거 아님. |
| P5 | https://www.poscoflow.com/en/business/steel | 본문 직접 확인. 도로·철송·해상 dispatch/yard/terminal/loading/transport/customer, 계약별 경로 차이. |
| P6 | https://www.poscoflow.com/en/business/raw-materials/steel | 본문 직접 확인. 철광석/석탄/석회석/니켈광 및 적항→벌크해상→양하항. |
| P7 | https://www.poscoflow.com/en/business/cts | 본문 직접 확인. 접안/양하/야드·창고/가공/연안·도로·철도. |

구주소 `https://www.poscoflow.com/en/business/domestic.do` 직접 접근404 → P5 사용. 뉴스룸 `https://newsroom.posco.com/en/factories-produce-steel-smart-way/` 직접502 → 핵심 근거로 사용하지 않음.

## 원문 의미와 현행 구현의 차이

- **상류/반제품:** P4가 연주 형상과 후공정 소재 개념을 뒷받침한다. 반제품 직판·구입재 입고의 구체 SOP는 승인 범위/합성 설계로 구분한다. ORE를 금속 추적량으로 쓰는 현행 가정은 실제 철광석 물질수지가 아니다.
- **후판/선재/냉연:** `plate-line.png`의 마킹·가스절단, `wire-rod.png`의 황삭가위·절단기, `cold-rolled.png`의 scale breaker·용접기·looper를 독립 의미 요소로 등록한다. 후판 초음파 검사를 일반 외관검사로 대체하지 않는다.
- **도금:** P1의 GI=냉연기재 아연도금, GI(H)=열연기재, GA=Zn-Fe 합금화 가열, EG=냉연기재 전기화학 도금. HGI에 냉간압연을 강제하지 않는다. `coated.png`의 air knife/looper/용접기/검사, `electrogalvanized.png`의 Oven and Cooler가 필요하다. HGI 전용 3D 도식 미확인 제한을 유지한다.
- **GO/NGO:** GO 자구 미세화는 제조 기능이며 현행 go-10 kind가 inspection이어도 일반 검사로 축소 금지. shot blasting, looper, 절단·용접 연결도 원문 요소로 등록한다.
- **STS:** EAF/정련/연주, CAF/HAPL, 냉연CAPL/TLL/STL, 후판 열간교정/냉각/절단/냉간교정/열처리의 의미를 보존한다. HAPL shot blasting과 loopers/welders도 등록한다. 상세 기구 치수는 미확인이다.
- **Ti:** 잉곳→단조→슬래브→가열/압연→HAPL, 후판 단조/압연/소둔/산세/교정/가스절단. `titanium-cold.png`의 TLL 뒤 냉연코일 / STL→skelp / SHL→sheet 출력 분기를 명시한다. 현행 ti-cr의 STL 필수 경유를 유일한 원본 경로라고 주장하면 안 된다. VAF·중간 권취·재투입은 코일 처리 의미를 보존하되 상세 로딩은 설계 가정이다. 역사 카탈로그의 Ti sponge/VAR/전자빔 용해를 이번 공장 내부 범위에 추가하지 않는다.

원문 부품을 별도 장비로 만들지 기존 장비의 subassembly로 표현할지 등록하되 의미/동작/QA를 누락하지 않는다. 연결 책임은 T18 공정/경로, T19–21·T26–29 자산, T31 동작, T40 전수 연결 검증이다.

## 경계49개 disposition

- receiving17: 모든17제품의 `-01`.
- inspection2: plate-09, wire-09.
- packaging13: hr-08, wire-10, cr-10, gi-10, ga-11, hgi-10, eg-10, go-12, ngo-09, sts-hr-14, sts-cr-10, ti-hr-09, ti-sheet-10.
- dispatch17: hr-09, plate-10, wire-11, cr-11, gi-11, ga-12, hgi-11, eg-11, go-13, ngo-10, sts-hr-15, sts-cr-11, sts-plate-12, ti-hr-10, ti-cr-10, ti-sheet-11, ti-plate-09.

나머지138개도 source-step disposition을 가진다. 내부 블록 연결로 입고/출하가 생략돼도 적용 조건과 replaced_by를 기록한다. 위187개 계산은 추가 원문 요소나 신규 물류 요구를 면제하지 않는다.

## 신규 물류/입고/고객 인도 요구

- 원료 해상 입고: 적항→벌크선→접안→양하→야드/창고→공정 공급(P6/P7); 세부 검수/계량/컨베이어/stacker/reclaimer는 승인 범위와 설계 가정 구분.
- 육상·구입재: 도착/검수/계량/하역/보관, scrap/Ti ingot/slab/bloom/billet/HR·CR·STS_HR·TI_HR coil의 후공정 진입(승인 범위; 현장SOP 미확인).
- 반제품 직판: 검사·출하 준비→운송→고객 인수(P4 형상, P5 물류, 승인 판매 분기).
- 도로: 배차/대기/상차/결박/계량/출문/운송/고객하역/인수.
- 철송: 편성/입환/화차적재/블록이동/목적지하역·보관/선택last-mile/고객 인도. 블록예약·coupler는 합성 실행 계약.
- 해상 제품: 부두이송/대기/선적·검정/해상/양하·검정/선택허브·last-mile/고객 인도.
- 내부: 크레인/롤러/용선·래들차/지게차/캐리어 접근·적재·이동·하역·빈차복귀.
- 품질: 검사/격리/재검/포장/보관/custody. 초음파·자구 처리 등 제조 의미 보존.

## T2 작성 규칙

1. observed_inventory, source_requirements, approved_scope_requirements를 분리한다.
2. stable ID, origin, 제품/변형, 출처URL·조회일·관찰방식·로컬증거, 기대기능, 불확실성, 구현매핑, source_step_disposition, source_branch/adaptation, QA행을 기록한다.
3. 원문187개 disposition은 전수 관리하지만 전체 expected 요구의 상한으로 삼지 않는다.
4. HR/CR/반제품의 판매 경로와 후공정 공급 경로를 구분한다.
5. 미확인 geometry/axes/speed/clearance/현장SOP를 verified로 승격하지 않는다. 전시관 생방문 재확인/HGI전용도식 부재/Ti출력분기 적용/역사자료 제한을 남긴다.

정리 영수증: 생성 파일0, RUN_TMP 없음, 서버·지속 프로세스0, 제품 테스트0, 외부 자산 다운로드0. 이 문서/JSON은 루트의 실행 기록 저장이며 제품 변경이 아니다.
