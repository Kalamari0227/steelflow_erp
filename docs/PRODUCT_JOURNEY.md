# 20개 제품의 통합 제조 경로

제품 제조 뷰는 선택한 주문/소재의 읽기 전용 투영입니다. 새 소재나 별도 실행 시계를 만들지 않습니다. 기준 카탈로그는 `backend/app/data/operations_routes.json`, 공개 공정 단계는 `journey_products.json`이며 route compiler가 연결과 소재 형태 연속성을 검사합니다.

| 제품 ID | 시작 경계 | 주요 경로와 최종 형태 |
| --- | --- | --- |
| slab | ORE | 제선·제강 → 슬래브 주조 → SLAB |
| bloom | ORE | 제선·제강 → 블룸 주조 → BLOOM |
| billet | ORE | 제선·제강 → 빌렛 주조 → BILLET |
| hr | ORE | 슬래브 계통 → 열연 → HR_COIL |
| plate | ORE | 슬래브 계통 → 후판 → 분할 → PLATE |
| wire | ORE | 블룸 계통 → 선재 → WIRE_COIL |
| cr | ORE | 슬래브 → 열연 → 냉연 → CR_COIL |
| gi | ORE | 열연 → 냉연 → 용융아연 → GI_COIL |
| ga | ORE | 열연 → 냉연 → 합금화아연 → GA_COIL |
| hgi | ORE | 열연 → 열연도금(냉연 생략) → HGI_COIL |
| eg | ORE | 열연 → 냉연 → 전기아연 → EG_COIL |
| go | ORE | 열연 → 방향성 전기강판 → GO_COIL |
| ngo | ORE | 열연 → 무방향성 전기강판 → NGO_COIL |
| sts-hr | SCRAP | 스테인리스 열연 → STS_HR_COIL |
| sts-cr | SCRAP | 스테인리스 열연 → 냉연 → STS_CR_COIL |
| sts-plate | SCRAP | 스테인리스 후판 → STS_PLATE |
| ti-hr | TI_INGOT | 티타늄 열연 → TI_HR_COIL |
| ti-cr | TI_INGOT | 티타늄 열연 → 냉연 → TI_CR_COIL |
| ti-sheet | TI_INGOT | 티타늄 열연 → 박판 → 분할 → TI_SHEET |
| ti-plate | TI_INGOT | 티타늄 후판 → TI_PLATE |

모든 경로는 공통 최종 검사와 포장 후 가용 재고·출하로 연결됩니다. 같은 HR/CR이라도 주문이 hr/cr이면 판매 제품이고, GA 등 후공정 주문이면 중간 투입 소재입니다. 상태와 용도를 구분해서 읽습니다.

티타늄은 합성 잉곳 입고부터 추적하며 잉곳 제조 이전의 광물 추출·정련·용해는 경계 밖입니다. 탄소강 ORE도 추적 금속량을 나타내는 합성 원료이며 실제 광석 투입량이 아닙니다. 스테인리스는 합성 스크랩부터 시작합니다. 합성 수율·첨가·손실은 [생산 규칙](PRODUCTION.md)을 따릅니다.

공장 전경에서 주문/소재를 선택하고 공정 버튼·설비·소재 따라가기를 사용합니다. 형상은 서버의 현재 소재 형태, 가공 진행률, 확인된 운송 구간을 표시합니다. 소재 여권에서 이전 버전·부모/자식·검사 대상 버전·출하 명세를 추적합니다. 2D 전환은 선택과 run을 유지합니다.

[공개 참고 자료](evidence/posco-reference/README.md)는 제품별 제조 원리를 확인한 자료입니다. 장면은 SteelFlow의 절차적 설명 모형이며 공개 화면이나 영상을 실제 대화형 장면으로 붙여 넣지 않습니다. 실제 POSCO CAD·측량 치수·사내 운영 데이터·검증된 열역학 시뮬레이션이 아닙니다. 현재 버전의 영상/화면 승인 여부는 [검증 기록](TEST_RESULTS.md)을 참조하십시오.
