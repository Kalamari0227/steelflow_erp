# 전체 공장 공정·물류 참고 근거

작성·조사 기준일: **2026-10-25 KST**. 이 문서는 공개 공정 근거, 승인된 합성 운영 범위, 현재 구현 목록을 구분한다. T2의 출처·커버리지 계약이며, 후속 공장 구현이나 제품 시험의 완료 보고가 아니다. 기계 판독 연결은 [coverage-registry.json](../shared/coverage-registry.json), 범위 결정은 [승인 계획](../.omo/ulw-execute/steelflow-uniform-fidelity-factory/approved-plan.md)에 있다.

## 근거의 종류와 분모

| 구분 | 의미와 사용 규칙 |
| --- | --- |
| 공개 제조 근거 | 공개 도식·공식 제품 설명에서 확인한 기능, 소재 형태, 연결·분기. `source_requirements`에 등록하며 현재 코드에서 역생성하지 않는다. |
| 승인 범위·합성 설계 | 입고·반제품 판매·내부 운송·차량·철송·항만·고객 인수와 업무 계약. `approved_scope_requirements`에 등록하고 공개 자료가 설명하는 개념과 세부 설계 가정을 구별한다. |
| 관찰된 구현 목록 | `observed_inventory`는 현재 데모·컴파일 경로·배치의 목록이다. 해당 숫자나 코드가 원문 정확성·완성도를 증명하지 않는다. |
| 향후 구현·검증 | `implementation_mapping.status=pending_delivery`, QA의 `status=pending`, `evidence=[]`는 아직 작업·증거가 필요하다는 뜻이다. T2 등록 성공을 제품 완료로 승격하지 않는다. |

승인 제품은 **20개**다. 기존 [journey_products.json](../backend/app/data/journey_products.json)의 **17개 데모 경로·187개 단계**는 제품 선택과 데모 단계의 분모다. 공식 전시관은 **8개 URL·14개 도식 변형·15개 로컬 PNG**다. 후판의 한 변형을 두 장으로 캡처했다. 용융도금 도식 하나에서 GI/GA/HGI를 구분하고 Ti 냉연 도식에서 코일/시트 경로를 구분하므로, 17개 경로를 17개 원문 도식으로 세지 않는다. SLAB/BLOOM/BILLET은 승인 범위의 반제품 경로이며 별도 전시관 도식 3개가 있다는 뜻이 아니다.

187개 중 **49개 경계 치환·138개 유지 단계**를 전수 추적한다. 이 숫자는 원문 상세 기구나 새로운 물류 요구의 상한이 아니다. 현재 컴파일 제품 20개, 기존 배치 설비 158개·40 kind·24 stage·source binding 148개는 [factory-layout.json](../shared/factory-layout.json), [operations_routes.json](../backend/app/data/operations_routes.json), [catalog.py](../backend/app/operations/catalog.py)의 관찰 인벤토리다. 후속 구현에서 추가되는 배치·연결·leg도 요구사항과 QA 행이 필요하다.

## 조회일·관찰 방식·접근 제한

- **2026-10-24 원본 관찰:** [원본 캡처 설명](evidence/posco-reference/README.md)은 공개 myPOSCO 제조공정 탭과 변형을 실제 브라우저에서 관찰했다고 기록한다. 아래 PNG는 그때의 원문 화면이며 SteelFlow 화면이 아니다.
- **2026-10-25 읽기 전용 조사:** [조사 메모](../.omo/drafts/uniform-execution-source-coverage.md)와 [기계 판독 조사 기록](../.omo/drafts/uniform-execution-source-coverage.json)은 기존 PNG 15개 열람, myPOSCO 8개 URL의 현재 텍스트 조회 실패, 공식 대체 자료 7개 확인 방식과 제한을 기록한다. 이 문서는 그 기록을 승계하며, 원본 관찰일을 새 조회일로 바꾸지 않는다.
- **2026-10-25 문서 교차 확인:** Ti 냉연 분기, 도금 Air Knife, EG Oven and Cooler, GO 자구 처리, 후판 검사·절단·마킹, 선재 가위, 냉연 Scale Breaker·용접기·Looper, STS HAPL의 Shot Blasting을 로컬 PNG에서 직접 재열람했다. 파일·링크·ID·원본 데모 개수는 문서 감사로 별도 대조한다.
- **파일 형식 주의:** 기존 캡처 15개는 모두 `.png` 파일명이지만 실제 파일 헤더는 JPEG/JFIF다. 이 문서의 “15개 PNG”는 보존된 파일명 목록을 뜻한다. 원본 바이트와 경로를 보존하며, 이미지 인코딩을 PNG로 검증했다고 주장하지 않는다.
- 현재 전시관 구조나 모든 원문 페이지를 생방문 재검증했다고 주장하지 않는다. 대체 자료의 개념 설명도 개별 도식 전체와 일대일 동등하다는 뜻은 아니다. 외부 페이지 재접근·제품 시험은 이번 문서 감사의 결과가 아니다.
- 비공개 ERP, 로그인·자격증명, 실회사 운영 데이터, 원본 CAD·3D 자산을 사용하지 않는다. 공개 그림의 모양은 제조 개념 근거이며 실측 치수·축·속도·안전거리·현장 SOP·공학 안전 인증 근거가 아니다.

## 공개 전시관과 로컬 도식

아래 `source ID`는 등록부의 `sources[].id`다. 8개 모두 원본 브라우저 관찰일은 2026-10-24, 후속 조사일은 2026-10-25이며 현재 텍스트 접근은 실패한 것으로 기록한다.

| source ID / 공식 URL | 도식 변형 | 적용 데모 제품 | 로컬 근거 |
| --- | --- | --- | --- |
| `showroom:M0z` / [열연](https://my.posco.com/s/exshowrmproductmain?lv1=a0uTJ000004pM0zYAE) | HR 1개 | hr | [hot-rolled.png](evidence/posco-reference/hot-rolled.png) |
| `showroom:M10` / [후판](https://my.posco.com/s/exshowrmproductmain?lv1=a0uTJ000004pM10YAE) | 후판 1개, 캡처 2장 | plate | [plate.png](evidence/posco-reference/plate.png), [plate-line.png](evidence/posco-reference/plate-line.png) |
| `showroom:M11` / [선재](https://my.posco.com/s/exshowrmproductmain?lv1=a0uTJ000004pM11YAE) | 선재 1개 | wire | [wire-rod.png](evidence/posco-reference/wire-rod.png) |
| `showroom:M12` / [냉연](https://my.posco.com/s/exshowrmproductmain?lv1=a0uTJ000004pM12YAE) | CR 1개 | cr | [cold-rolled.png](evidence/posco-reference/cold-rolled.png) |
| `showroom:M13` / [도금](https://my.posco.com/s/exshowrmproductmain?lv1=a0uTJ000004pM13YAE) | 용융도금·전기도금 2개 | gi, ga, hgi, eg | [coated.png](evidence/posco-reference/coated.png), [electrogalvanized.png](evidence/posco-reference/electrogalvanized.png) |
| `showroom:M14` / [전기강판](https://my.posco.com/s/exshowrmproductmain?lv1=a0uTJ000004pM14YAE) | GO·NGO 2개 | go, ngo | [electrical.png](evidence/posco-reference/electrical.png), [electrical-non-oriented.png](evidence/posco-reference/electrical-non-oriented.png) |
| `showroom:M15` / [스테인리스](https://my.posco.com/s/exshowrmproductmain?lv1=a0uTJ000004pM15YAE) | HR·CR·후판 3개 | sts-hr, sts-cr, sts-plate | [stainless.png](evidence/posco-reference/stainless.png), [stainless-cold.png](evidence/posco-reference/stainless-cold.png), [stainless-plate.png](evidence/posco-reference/stainless-plate.png) |
| `showroom:M16` / [티타늄](https://my.posco.com/s/exshowrmproductmain?lv1=a0uTJ000004pM16YAE) | HR·CR·후판 3개 | ti-hr, ti-cr, ti-sheet, ti-plate | [titanium.png](evidence/posco-reference/titanium.png), [titanium-cold.png](evidence/posco-reference/titanium-cold.png), [titanium-plate.png](evidence/posco-reference/titanium-plate.png) |

HGI 전용 3D 도식은 확인되지 않았다. 용융도금 도식의 공유 기구와 아래 P1의 HR 기재 설명을 함께 쓰며, HGI를 CR 경유 경로로 강제하지 않는다.

## 공식 대체 자료

아래 관찰 방법·결과는 2026-10-25 조사 기록 기준이다. `official:P1`부터 `official:P7`까지가 등록부 source ID다. 출처 페이지의 모든 진술을 채택하지 않고 아래 범위만 근거로 사용한다.

| ID | 공식 자료 | 확인 방식·사용 범위 | 제한 |
| --- | --- | --- | --- |
| `official:P1` | [POSCO INTERNATIONAL 철강 제품](https://www.poscointl.com/eng/steelProduct) | 본문 접근. HR의 슬래브→압연·냉각·권취, GI/GA/GI(H)/EG와 STS 상위 공정 구분. | 개별 설비 치수·배치·현장 SOP나 모든 도식 부품을 증명하지 않는다. |
| `official:P2` | [POSCO 전기강판 PDF](https://www.posco.com/homepage/servlet/FileDownLoad?fileCategory=prdMda&fileNum=12) | PDF 본문, PDF 4페이지/인쇄 6–7. GO 탈탄·고온소둔·평탄화·절연·자구 처리와 NGO 소둔·절연. | 역사 자료의 생산능력·설비 정보를 2026년 실제 가동 현황으로 사용하지 않는다. |
| `official:P3` | [POSCO Titanium PDF](https://posco.com/homepage/docs/kor5/dn/product/info/Titanium.pdf) | PDF 본문·검색 추출, 인쇄 14–15 제조 도식. 해당 페이지 이미지 추출은 실패하여 분기는 로컬 PNG로 교차 확인. | 2014년 계획을 2026년 실제 설비 구성으로 주장하지 않는다. 상세 로딩·기구 치수 미확인. |
| `official:P4` | [POSCO 2011 영문 브로슈어](https://www.posco.com/homepage/docs/eng6/jsp/dn/company/archive/2011_eng_brochure.pdf) | PDF 접근·공개 검색 추출. 연주 slab/bloom/billet 형상과 압연 소재 개념. | 현재 판매조건·현재 공장 구성의 근거가 아니다. 반제품 직판 SOP는 승인된 합성 범위다. |
| `official:P5` | [POSCO FLOW 철강 물류](https://www.poscoflow.com/en/business/steel) | 본문 직접 확인. 도로·철송·해상, dispatch/yard/terminal/loading/transport/customer와 계약별 경로 차이. | 모든 주문이 세 모드를 모두 거친다고 해석하지 않는다. 세부 배차·결박·인수 규칙은 합성 설계다. |
| `official:P6` | [POSCO FLOW 제철 원료 물류](https://www.poscoflow.com/en/business/raw-materials/steel) | 본문 직접 확인. 철광석·석탄·석회석·니켈광, 적항→벌크 해상→양하항. | 소재별 실제 공급·조달 계약이나 이번 공장 내부 공정 범위 확장의 근거가 아니다. |
| `official:P7` | [POSCO FLOW CTS](https://www.poscoflow.com/en/business/cts) | 본문 직접 확인. 접안·양하·야드/창고·가공·연안/도로/철도. | 개별 장비 모델·안전거리·속도·배치와 실제 작업표준은 미확인이다. |

구주소 [domestic.do](https://www.poscoflow.com/en/business/domestic.do)는 직접 접근 404여서 P5로 대체했다. [뉴스룸 스마트 공장 글](https://newsroom.posco.com/en/factories-produce-steel-smart-way/)은 직접 502로 핵심 근거에서 제외했다. 링크 존재를 성공 접근으로 표시하지 않는다.

## 20개 제품의 제조 의미와 판매·후공정 분기

제품 행의 `scope:product:<id>`는 승인 제품 요구사항이다. 표의 원본 단계 수는 현재 데모의 연속 ID `<product>-01`부터 마지막 번호까지를 뜻한다. 공정 설명은 공개 근거·승인 범위를 읽어 정리한 요구이며 단계 수에 맞춰 축소하지 않는다.

| 제품 ID | 제품 요구 ID | 원본 데모 단계 | 제조 연결·판매/후공정 의미 | 주 근거 |
| --- | --- | ---: | --- | --- |
| slab | `scope:product:slab` | 없음 | 원료→제선→전로·정련→슬래브 연주·절단·냉각. 반제품 판매 또는 HR/후판 공급, 구입 슬래브는 실제 입고 지점부터 시작. | P4, 승인 계획 |
| bloom | `scope:product:bloom` | 없음 | 원료→제선→전로·정련→블룸 연주·절단·냉각. 반제품 판매 또는 빌렛·선재 계열 공급. | P4, 승인 계획 |
| billet | `scope:product:billet` | 없음 | 원료→제선→전로·정련→빌렛 연주·절단·냉각. 반제품 판매 또는 후공정 소재. 블룸→빌렛 압연 경로와 구별. | P4, 승인 계획 |
| hr | `scope:product:hr` | 9 | 슬래브→가열→조압연→사상압연→냉각→권취·정정. HR 판매와 CR/HGI 등 후공정 공급 구별. | M0z, P1 |
| plate | `scope:product:plate` | 10 | 슬래브→가열·압연→냉각/냉각대→기계·가스 절단→열처리·교정·마킹·초음파 검사. 기구별 기능 유지. | M10 |
| wire | `scope:product:wire` | 11 | 블룸 가열→빌렛 조/사상압연·정정→선재 가열·압연→권취·냉각·검사. 황삭가위·절단기 별도 보존. | M11 |
| cr | `scope:product:cr` | 11 | HR→풀기·용접·Scale Breaker·산세→냉간압연→전해청정·소둔·조질·도유·권취. CR 판매/도금 공급 구별. | M12 |
| gi | `scope:product:gi` | 11 | CR→전처리·소둔→용융아연도금·Air Knife→냉각→조질·후처리·도유→출측 절단·권취. | M13, P1 |
| ga | `scope:product:ga` | 12 | CR→용융아연도금·Air Knife→합금화 가열→냉각→조질·후처리·도유→출측 절단·권취. GI와 합금화 유무·순서를 구별. | M13, P1 |
| hgi | `scope:product:hgi` | 11 | HR 기재 용융도금. 공유 도식에 대한 명시적 adaptation이며 CR 공정 강제 금지. | M13 제한, P1 |
| eg | `scope:product:eg` | 11 | CR→전처리→전기화학 도금→표면처리·Oven and Cooler→도유·권취/검사. 용융욕 기구와 구별. | M13, P1 |
| go | `scope:product:go` | 13 | 방향성 강판의 냉간압연·탈탄소둔·베이스 도포·고온소둔·평탄화·절연·자구 미세화와 구간별 절단. 베이스 도포와 최종 절연은 다른 위치·기능이며 자구 미세화는 제조 기능. | M14, P2 |
| ngo | `scope:product:ngo` | 10 | 무방향성 강판의 예비/최종 소둔·냉간압연·절연코팅·권취. GO 전용 처리를 무조건 추가하지 않는다. | M14, P2 |
| sts-hr | `scope:product:sts-hr` | 15 | 스크랩→EAF/정련(AOD)→연주→열간압연→CAF/HAPL·Shot Blasting·산세. 제품 판매/냉연 공급 구별. | M15, P1 |
| sts-cr | `scope:product:sts-cr` | 11 | STS HR→냉간압연→CAPL→조질→TLL/STL 정정·절단 계열. 용접·Looper 연결 유지. | M15 |
| sts-plate | `scope:product:sts-plate` | 12 | STS 슬래브→가열·압연→열간교정·냉각·절단·냉간교정·열처리. | M15 |
| ti-hr | `scope:product:ti-hr` | 10 | 외부 조달 Ti 잉곳→단조→슬래브→가열·압연→HAPL. 판매 또는 Ti 냉연 공급. | M16, P3 |
| ti-cr | `scope:product:ti-cr` | 10 | Ti HR→냉간압연→VAF→TLL→냉연코일, 또는 STL→Skelp. 원문은 STL 필수 단일 경로가 아니다. | M16, P3 제한 |
| ti-sheet | `scope:product:ti-sheet` | 11 | Ti 냉연·VAF·TLL 뒤 SHL→Sheet 분기. STL→SHL을 유일한 원문 연결로 주장하지 않는다. | M16, P3 제한 |
| ti-plate | `scope:product:ti-plate` | 9 | 외부 조달 Ti 잉곳→단조·압연·소둔·산세·교정·가스 절단. 코일 제조 경로와 구별. | M16, P3 |

Ti 상류는 **구매 잉곳 입고**에서 시작한다. 역사 카탈로그의 sponge·VAR·전자빔 용해(EBM)를 이번 공장 내부에 추가하거나 실제 수행한 상류 이력으로 만들지 않는다. ORE를 금속 추적량으로 쓰는 기존 가정은 실제 철광석 물질수지가 아니다. 질량·첨가·손실은 승인된 합성 업무 계약으로 검증한다.

## 원본 187개 단계 disposition과 49개 경계 치환

등록부는 모든 원본 단계에 `disposition:<source-step-id>`를 하나씩 둔다. `source_step_dispositions`의 `category`, `replaced_by`, `condition` 및 QA 참조가 연결 의미를 보존한다. 다음 49개는 현재 통합 경로의 경계 치환이다. 제외된 데모 단계를 없던 요구로 취급하지 않는다.

| category | 수 | 원본 단계 ID | 대체 요구 ID·적용 조건 |
| --- | ---: | --- | --- |
| receiving | 17 | hr-01, plate-01, wire-01, cr-01, gi-01, ga-01, hgi-01, eg-01, go-01, ngo-01, sts-hr-01, sts-cr-01, sts-plate-01, ti-hr-01, ti-cr-01, ti-sheet-01, ti-plate-01 | `scope:receiving`. 외부 구입 소재면 입고 검수·계량·하역·보관과 실제 후공정 진입을 추적한다. 내부 블록 간 공급이면 외부 입고를 중복 생성하지 않고 해당 인계를 추적한다. |
| inspection | 2 | plate-09, wire-09 | `scope:inspection`. 제품 최종 품질/hold/retest 경계에 연결한다. 후판 원문 초음파 기능은 `src:plate-ultrasonic`로 별도 유지한다. |
| packaging | 13 | hr-08, wire-10, cr-10, gi-10, ga-11, hgi-10, eg-10, go-12, ngo-09, sts-hr-14, sts-cr-10, ti-hr-09, ti-sheet-10 | `scope:packaging`. 최종 출하 제품에 적합한 포장·보관 상태를 연결하고 내부 후공정 투입에 출하 포장을 중복 강제하지 않는다. |
| dispatch | 17 | hr-09, plate-10, wire-11, cr-11, gi-11, ga-12, hgi-11, eg-11, go-13, ngo-10, sts-hr-15, sts-cr-11, sts-plate-12, ti-hr-10, ti-cr-10, ti-sheet-11, ti-plate-09 | `scope:dispatch`. 판매 시 선택된 도로/철송/해상 shipment leg와 고객 인도로 연결한다. 중간재 후공정 공급은 내부 인계 조건으로 구별한다. |

나머지 138개는 `retained` disposition으로 원본 기능 요구 `src:<source-step-id>`에 연결한다. 이 명명은 원본 데모 단계의 추적 키이며 각 데모 단계가 원문 모든 세부를 완전하게 재현했다는 인증이 아니다. 동일 원본 단계가 여러 컴파일 제품 경로에서 재사용되면 각 단계·연결·배치 매핑을 남겨야 한다. [현재 경로 기대값 fixture](../tests/fixtures/operations_route_expectations.json)는 기존 동작 비교 자료이며 독립 제조 근거를 대신하지 않는다.

## 데모 단계 밖의 원문 기능과 향후 책임

아래는 187개를 모두 매핑해도 놓칠 수 있는 원문 기능이다. 별도 설비 또는 기존 설비의 subassembly로 표현할 수 있지만 기능·부품 ID·동작·접점·QA를 생략할 수 없다. **아래 구현 및 제품 증거는 모두 pending**이며 현재 generic kind나 이름만으로 통과시키지 않는다.

| 요구 ID | 확인된 의미·근거 | 후속 구현·검증 책임 |
| --- | --- | --- |
| `src:plate-ultrasonic`, `src:plate-marking`, `src:plate-gas-cut` | 후판 PNG의 초음파검사·마킹·Gas 절단. 일반 외관검사나 동일 shear 이름으로 세 기능을 합치지 않는다. | T18 경로/기능, T20 열간 자산, T29 검사 구역, T31 동작, T40 연결 검증. |
| `src:wire-shears` | 선재 PNG의 황삭가위·절단기와 빌렛/선재 소재의 차이. | T18, T20, T31, T40. |
| `src:cold-scale-breaker`, `src:cold-welder`, `src:cold-looper` | 냉연 PNG의 Scale Breaker·용접기·Looper. 단순 롤러 대체 금지. | T18, T21 냉연 자산, T31, T40. |
| `src:coating-air-knife`, `src:coating-welder`, `src:coating-looper` | 용융도금 PNG의 Air Knife·용접·Looper. 도금욕/합금화/조질과 구별. | T18, T21, T31, T40. |
| `src:eg-oven-cooler` | 전기도금 PNG의 Oven and Cooler. 도금 셀·표면처리·냉각 기능 구별. | T18, T21, T31, T40. |
| `src:coating-inspection` | 용융/전기도금 도식의 검사 기능. 표면 후처리와 품질 검사를 구별. | T18, T21, T31, T40. |
| `src:go-domain-refinement` | GO PNG·P2의 자구 미세화는 제조 처리. 현재 go-10이 inspection kind인 사실로 의미를 축소하지 않는다. | T18 의미·경로 정정, T21 자산/기구, T31 동작, T40 제조 연결·QA. |
| `src:electrical-shot-blasting`, `src:electrical-welder`, `src:electrical-looper` | 전기강판 PNG의 Shot Blasting·용접·Looper. GO/NGO별 적용은 각 도식으로 구별. | T18, T21, T31, T40. |
| `src:ngo-electrocleaning`, `src:ngo-drying` | NGO 도식의 전해청정·건조설비. 소둔·절연코팅·권취와 기능을 구별. | T18, T21, T31, T40. |
| `src:sts-shot-blasting`, `src:sts-welder`, `src:sts-looper` | STS HAPL/CAPL 계열의 Shot Blasting·용접·Looper. CAF/HAPL/CAPL/TLL/STL 기능을 일반 냉연 이름으로 지우지 않는다. | T18, T26 STS 자산, T31, T40. |
| `src:ti-tll-coil`, `src:ti-stl-skelp`, `src:ti-shl-sheet` | Ti 냉연 PNG에서 TLL 이후 **냉연코일 OR STL→Skelp OR SHL→Sheet**. 현재 ti-cr의 STL 필수 경유는 구현 adaptation이다. 중간 권취·재투입·VAF 로딩의 구체 방식은 설계 가정. | T18 경로 분기 정정·명시, T27 Ti 자산·형상·접점, T31 로딩/재투입 동작, T40 전수 분기 연결, T43 연속 제품 증거. |
| `src:hgi-hr-feed` | P1의 GI(H)는 HR 기재. HGI 전용 도식 미확인 상태를 유지하면서 CR 강제를 금지. | T18 원료 진입, T21 도금 variant, T40 경로 검사, T43 연속 제품 증거. |

제강·연주·slab/bloom/billet 형상은 T18/T19, 전체 자산군은 T19–T21/T26–T29가 소유한다. T31 동작·T32 인계·T40 전수 연결 및 T43–T45 실제 화면/연속 동작 검증은 제조 근거 문서와 별도로 수행한다. 원문 자산을 가져오거나 원문 PNG를 상호작용 장면 대신 사용하지 않는다.

## 독립 출처 검토 후 보완한 구간별 기능

2026-10-25 독립 검토 S1–S3에 따라 아래 7개 원본 이미지를 원래 해상도로 다시 열람했다. 종전 등록부에 빠졌던 기능을 추가했으며, 후속 구현·증거는 모두 **pending**이다. 절단기는 소재 지지·이송, 날의 절단/분리 동작, 분리된 끝단의 코일 인계가 필요하다. 베이스 도포는 도포 기구·롤 동작과 도포 상태, 냉각은 구간 내 소재 진행·지지·냉각 상태와 전후 인계를 검증한다. 그림이 밝히지 않는 화학 조성·냉각 매체·정밀 축·치수·속도는 단정하지 않는다.

| 요구 ID | 제품·구간·순서 | 직접 재열람한 근거 |
| --- | --- | --- |
| `src:go-base-coating` | GO 중간 행: 탈탄소둔→출측 Looper→베이스 도포→절단·중간 코일→고온소둔. 평탄화소둔 뒤 최종 절연코팅과 다른 기능·위치다. 도포 화학 조성은 미확인. | [electrical.png](evidence/posco-reference/electrical.png) |
| `src:cr-cold-mill-output-cutter` | CR 위쪽 행: 냉간압연→출측 절단→중간 코일, 이후 전해청정·소둔 구간. | [cold-rolled.png](evidence/posco-reference/cold-rolled.png) |
| `src:cr-finished-output-cutter` | CR 아래쪽 행: 도유→완제품 출측 절단→최종 권취·포장. | [cold-rolled.png](evidence/posco-reference/cold-rolled.png) |
| `src:go-pickling-output-cutter` | GO 위쪽 행: 산세→출측 Looper→절단→중간 코일·냉간압연 투입. | [electrical.png](evidence/posco-reference/electrical.png) |
| `src:go-basecoat-output-cutter` | GO 중간 행 왼쪽: 베이스 도포→절단→중간 코일·고온소둔. | [electrical.png](evidence/posco-reference/electrical.png) |
| `src:go-finished-output-cutter` | GO 아래쪽 행: 평탄화소둔·절연코팅·자구 미세화→출측 절단→완제품 권취. | [electrical.png](evidence/posco-reference/electrical.png) |
| `src:ngo-pickling-output-cutter` | NGO 위쪽 행: 산세→출측 Looper→절단→중간 코일·냉간압연 투입. | [electrical-non-oriented.png](evidence/posco-reference/electrical-non-oriented.png) |
| `src:ngo-finished-output-cutter` | NGO 아래쪽 행: 최종 소둔·절연코팅·건조설비→출측 절단→완제품 권취. | [electrical-non-oriented.png](evidence/posco-reference/electrical-non-oriented.png) |
| `src:sts-hapl-output-cutter` | STS 열연 아래쪽 행: HAPL 산세→출측 Looper→절단→제품 권취. | [stainless.png](evidence/posco-reference/stainless.png) |
| `src:sts-capl-output-cutter` | STS 냉연 중간 행: CAPL 산세→출측 Looper→절단→중간 코일, 이후 조질·TLL·STL. 출측 끝단 분리 절단과 STL 길이방향 슬리팅은 별도 기능이다. | [stainless-cold.png](evidence/posco-reference/stainless-cold.png) |
| `src:hotdip-output-cutter` | GI와 GA 각각: 도유→출측 절단→완제품 권취·포장. 공유 절단기를 사용해도 두 제품의 위치·접점 QA를 각각 수행. | [coated.png](evidence/posco-reference/coated.png) |
| `src:hgi-output-cutter` | HGI의 HR 기재 공유 도식 adaptation: 도유→출측 절단→권취. HGI 전용 도식·현장 배치는 미확인. | [coated.png](evidence/posco-reference/coated.png) |
| `src:eg-output-cutter` | EG 아래쪽 행: 도유→출측 절단→완제품 권취·포장. EG Oven and Cooler와 별도 기능. | [electrogalvanized.png](evidence/posco-reference/electrogalvanized.png) |
| `src:gi-coating-cooling` | GI: 용융욕→Air Knife→오른쪽 회전 구간의 냉각→조질압연. GA 합금화 경유를 강제하지 않는다. | [coated.png](evidence/posco-reference/coated.png) |
| `src:ga-coating-cooling` | GA: 용융욕→Air Knife→합금화처리→냉각→조질압연. 합금화 뒤 냉각 순서를 보존. | [coated.png](evidence/posco-reference/coated.png) |
| `src:hgi-coating-cooling` | HGI 공유 도식 adaptation: HR 기재 용융욕→Air Knife→냉각→조질. 전용 도식 미확인이고 EG 냉각과 구별. | [coated.png](evidence/posco-reference/coated.png) |

각 행은 별도 요구와 `qa:<요구 ID>`를 가진다. T18은 기능·선후행 경로, T21은 CR/도금/전기강판 자산, T26은 STS 자산, T31은 동작, T40은 전수 연결, T43은 연속 제품 실행, T45는 각 제품·구간 배치 검수를 소유한다. GI/GA 공용 자산을 사용해도 제품별 순서·접점을 확인하고, STS CAPL 절단을 STL로 대체하거나 GO 베이스 도포를 최종 절연코팅으로 대체하지 않는다. 용융도금 냉각과 EG Oven and Cooler 역시 서로 대체하지 않는다.

## 입고·내부 이송·물류·고객 인도

공개 물류 자료 P5–P7은 운영 개념을 뒷받침한다. 아래 세부 기구·검수·예약·custody 전환은 `scope:approved-plan`을 근거로 하는 승인 범위 또는 합성 설계이며, 실제 사업장의 작업표준이라고 주장하지 않는다. 각 추가 leg·운영 장비·배치에는 독립 요구와 QA가 필요하다.

| 범위 | 필요한 연결·가정 | 전달 책임 |
| --- | --- | --- |
| 원료 해상 입고 | 적항→벌크선→접안→양하→야드/창고→공정 공급(P6/P7). 세부 검수·계량·컨베이어·stacker/reclaimer의 치수/속도는 합성 설계. | T8 공간, T9 입고, T11 fleet, T17 원료, T24 항만, T28/T29 자산. |
| 육상·구입재 입고 | 도착·검수·계량·하역·보관. scrap, Ti ingot, slab/bloom/billet, HR/CR/STS_HR/TI_HR 코일의 실제 후공정 진입. 수행하지 않은 상류 이력 생성 금지. | T9, T17, T18, T25 업무 연결. |
| 반제품/중간재 판매 | 반제품 및 HR/CR 판매와 내부 후공정 공급을 분리. 검사·출하 준비→운송→고객 인수. P4는 형상, P5는 물류 개념, 판매 분기는 승인 범위. | T18, T25, T43. |
| 내부 이송 | 크레인·롤러·용선/래들차·지게차·캐리어의 접근→적재→이동→하역→빈차복귀. 작업이 없어도 같은 운영 개체 유지. | T11, T15/T16 스케줄러, T28, T31/T32. |
| 도로 | 배차·대기·상차·결박·계량·출문·운송·고객하역·인수. 실제 계약·시간표는 합성. | T22 도로, T25 이행, T28 자산, T44 인계 검증. |
| 철송 | 편성·입환·화차 적재·블록 이동·목적지 하역/보관·선택 last-mile·고객 인도. 블록 예약·coupler 계약은 합성 실행 규칙. | T23 철송, T25, T28, T44. |
| 해상 제품 | 부두 이송·대기·선적/검정·해상·양하/검정·선택 허브/last-mile·고객 인도. 원료 부두와 제품 부두 구별. | T24 항만, T25, T28/T29, T44. |
| 품질·보관 | 검사·격리·재검·포장·보관과 custody. 원문 초음파와 GO 제조 자구 처리를 일반 품질 경계로 흡수하지 않는다. | T25 업무, T29 구역, T32, T40/T43/T44. |

## 등록부 연결 계약과 완료 판정

`schema_version=1`에서 source ID는 위 표, 제품 ID는 제품 표, 단계 disposition ID는 `disposition:<source-step-id>`를 사용한다. `scope:product:<id>`는 20개 제품 요구, `src:<source-step-id>`는 138개 유지 단계 요구, 네 경계 요구는 `scope:receiving`, `scope:inspection`, `scope:packaging`, `scope:dispatch`다. 원문 추가 기능의 exact ID는 위 기능 표에 기록했다. 새 물류 요구의 ID 계열은 `scope:road:`, `scope:rail:`, `scope:sea:`, `scope:raw-sea:`, `scope:internal:`, `scope:quality:`이며 실제 전체 ID는 등록부 행이 정한다.

`scope:approved-plan`의 해시 근거는 승인 당시 동결한 [approved-plan.md](../.omo/ulw-execute/steelflow-uniform-fidelity-factory/approved-plan.md)다. 진행 체크박스와 후속 작업이 바뀌는 활성 실행 계획은 작업 관리 메타데이터이며, 그 변경으로 승인 범위의 출처 해시를 다시 고정하지 않는다.

각 요구는 `requirement_origin`, `products`, `variant`, `source_ids`, `expected_function`, `uncertainty`, `delivery_tasks`, `implementation_mapping`, `proof_requirement`, `qa_row_ids`, `source_branch`, `adaptation`을 보존한다. `sources`는 `url`, `observed_at`, `research_date`, `access_status`, `observation_method`, `local_evidence`, `limitations`를 보존한다. 원본에 없는 설계와 원본 분기는 같은 필드 값으로 감추지 않는다.

각 제품·원본 단계·컴파일 단계/연결·배치·kind·semantic variant·새 물류 leg를 해당 요구 및 QA 행에 연결한다. 코드가 바뀌었다고 expected 요구를 자동 추가해 일치시키지 않는다. 누락·중복·알 수 없는 ID, 고아 매핑, QA 없는 관찰 개체, generic fallback은 검증 실패여야 한다. 원문 범위를 보완할 때는 출처/승인 범위·불확실성·전달 작업·증거 요구를 함께 갱신한다.

T2 감사는 문서·등록부의 정직성과 추적 가능성을 확인한다. 최종 제품 완료에는 각 행의 실제 구현·단계/분기·부품 동작·소재 지지·custody·ERP 상태·화면/연속 영상 증거와 독립 검토가 필요하다. 현재 도식 재접근 제한, HGI 전용 도식 부재, 역사 자료 한계, Ti 분기 수정, 기구 치수/속도/현장 SOP 미확인, 후속 제품 증거 부재를 완료로 바꾸지 않는다. 공정 관찰 화면은 같은 공장·주문·소재·run·업무 시계의 상세 보기이며 별도의 전시 데모 시계를 만들지 않는다.
