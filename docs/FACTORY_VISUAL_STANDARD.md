# 공장 미술·상호작용·시각 검수 기준

기준일 2026-10-25. T7은 후속 자산·화면 구현의 **설계 및 증거 접수 계약**이다. 현재 앱이 아래 외관·기구·상호작용을 구현했다거나 실제 GLB/픽셀 검수를 통과했다는 보고가 아니다. [검수표](../shared/visual-review-matrix.json)의 모든 행은 `pending`, 증거는 빈 배열이다. 기존 T4 메타데이터 시험도 실제 형상·동작의 증거로 승격하지 않는다.

구현 수치는 [visualTokens.ts](../src/operations/scene/visualTokens.ts), 등록·증거 접수는 [visualReview.ts](../src/operations/scene/visualReview.ts)가 소유한다. 이 문서는 이번 범위에서 사용하는 디자인 시스템 계약이며 새 DESIGN.md나 별도 화면·패키지를 만들지 않는다. 자산의 좌표·기구·라이선스·semantic ID는 [ASSET_STANDARD.md](ASSET_STANDARD.md), [asset-requirements.json](../shared/asset-requirements.json), [asset-manifest.schema.json](../shared/asset-manifest.schema.json)을 따른다. 제조 의미는 [FACTORY_PROCESS_REFERENCES.md](FACTORY_PROCESS_REFERENCES.md)와 exact source/requirement ID가 우선한다.

## 1. 참조를 읽은 결과와 채택 범위

세 PNG와 [생성 프롬프트](../design/mockups/2026-10-25/prompts.md)를 직접 열람했다. 아래는 정적 합성 콘셉트의 관찰이며 실존 공장 측량이나 현재 제품 화면이 아니다.

| 참조 | 채택할 시각 구조 | 제품에서 교정할 점 |
| --- | --- | --- |
| [A — miniature overview](../design/mockups/2026-10-25/a-miniature-overview.png) | 미색 지면·밝은 일광, 길고 청회색인 shed, 서로 다른 제강 설비 실루엣, 얇은 지형 가장자리, 황토색 크레인, 오른쪽 수면과 원료/제품 두 부두. 작은 우측 패널과 바닥 여백의 라벨. | 파이프·롤·크레인 수나 조합을 이미지에서 복사해 기구 근거로 쓰지 않는다. 따뜻한 선택 표시를 소재 발열과 구별한다. 조감도에서 코일/슬래브/벌크 적재 형태를 읽을 수 있어야 한다. |
| [B — operations map](../design/mockups/2026-10-25/b-operations-map.png) | 넓은 곡선 차로, 대기장·회차장, 별도 용선선과 출하 철도, 원료 conveyor, 실제 이동면에 붙는 가는 teal 경로. 빈차와 적재차의 차이를 보여준다. | 선이 지붕을 관통하거나 도로 밖을 직선으로 잇지 않는다. 큰 검은 라벨 판·일괄 neon 경로·주문 목록의 색줄을 그대로 이식하지 않는다. 모든 라벨은 설비 실루엣과 겹침 검사를 한다. |
| [C — material follow](../design/mockups/2026-10-25/c-material-follow.png) | 주변 야드·도로·부두 맥락을 유지하며 같은 열연 hall의 지붕만 절개한다. 가열→조압연→사상압연→냉각→권취의 긴 작업축과 받침 구조를 읽는다. | 여러 발광 구간을 선택 소재의 복제본으로 해석하지 않는다. 절개용 전시 모델·두 번째 clock·복제 설비를 생성하지 않는다. inset이 필요하면 동일 상태/카메라 projection만 사용한다. |

세 이미지의 날짜·주문·치수·텍스트는 합성 UI 예시다. 이미지 유사도 자체는 기구 정확성이나 완료 판정이 아니다. PNG를 plane/background로 깔고 보이지 않는 pick proxy만 붙이는 방식은 실패다. 실제 3D 형상·접촉면·선택 identity·변환을 독립 검수한다.

## 2. 색·재질·조명·축척

| 용도 | token 값 | 적용 |
| --- | --- | --- |
| 바탕 / 지면 | `#f7f5ef` / `#e8e4d9` | 따뜻한 흰 gallery 배경, 얇은 실제 부지. 두꺼운 보드게임 받침 금지. |
| shed blue / teal | `#7895a5` / `#638f94` | 기능별 긴 외피·기둥·트러스의 명암. 동일 상자 격자로 치환하지 않는다. |
| 구조용 / 노출 금속 | `#58656c` / `#aeb8bb` | 프레임과 작업 롤·코일의 물성 차이. 세부 silhouette는 금속색 하나로 뭉개지지 않는다. |
| 크레인 도장 / 선택 | `#ce8c39` / `#b86b00` | 도장은 물체 색. 선택은 한 개체의 2px contour·glyph·패널. 선택 emissive=0. |
| 고온 소재 / 경로 | `#ff581c` / `#317f82` | 고온은 서버 material 상태, 경로는 실제 이동면 위 2px·opacity 0.45. 전역 bloom 없음. |
| 본문 / 보조 / 면 | `#25313d` / `#52606b` / `#fffefa` | 색 대비는 실제 합성된 배경에서 검사. 3D 색만으로 경고를 전달하지 않는다. |

PBR roughness/metalness: painted shed 0.72/0.12, 구조용 steel 0.55/0.72, 노출 steel 0.38/0.90, 도로 0.95/0, 지면 0.92/0, 물 0.28/0. 모든 수치는 **미술 설계값**이다. 원문 공장 치수·산업 재료 측정값·온도계 보정값이라고 표기하지 않는다. 과도한 mirror reflection, 동일 plastic 재질, 검은 금속 뭉침은 실패다.

key `#fff2db`, intensity 2.4, 방향 [-0.6,1,0.5]; fill `#e6eff6`, intensity 1.1; exposure 1; 그림자 opacity 0.22/softness 1.2m를 초기 설계값으로 쓴다. 렌더러별 밝기 보정은 모든 가족을 같은 기준으로 캡처해 검토하며 임의 설비에만 광원을 추가해 결함을 숨기지 않는다. 기초·바퀴·코일 받침의 접촉 그림자는 읽히고 내부 작업부는 검게 소실되지 않아야 한다.

좌표는 m, Y-up, +X 전방, physicalScale=1. 소재 mm는 /1000으로 변환한다. 카메라 확대와 LOD는 물리 형상 크기·지지점·시간을 바꾸지 않는다. 나무·사람·울타리·도로·hall도 동일 meter 환경에 속한다. 특정 설비만 보기 좋게 축소하거나 렌더러마다 다른 시계/단위를 쓰지 않는다. 원거리 항로는 연결된 외부 구간으로 표시한다.

## 3. 기구 의미와 출처 교정

모든 40 기존 kind의 최소 silhouette·작업부·socket은 ASSET_STANDARD의 **기존 40 kind 제작표**와 T4 정책을 그대로 적용한다. `steelmaking`, `hot-rolling`, `finishing`, `stainless`, `titanium`, `transport`, `campus`의 실제 허용 family는 T4 binding 값이 권위다. 같은 kind라도 variant·family·placement 검수를 공유 승인하지 않는다. 정확한 family 문자열은 matrix의 `family_ids`에 기록하며 이름 유사성으로 대체하지 않는다.

| 의미군 | 반드시 읽히는 구조·실패 예 | 근거 |
| --- | --- | --- |
| 제선/제강/연주 | 고로 출선층, BOF의 trunnion/tilt/lance, LF/EAF 전극, AOD vessel/tuyere, caster의 tundish/mold/strand/cutter를 구별. 모든 기계에 roller만 붙이면 실패. | `scope:carbon-upstream`, `showroom:M15`, `official:P4`; T4 각 kind 정책. |
| 가열/압연/선재/후판 | 가열 chamber와 장입·추출, 압연 stand·roll·guide, 냉각 header/bed, coiler mandrel/wrapper, laying head, shear/leveler/heat treatment의 작업 의미와 전후 support를 구별. | `showroom:M0z`, `M10`, `M11`; `src:wire-shears`, `src:plate-gas-cut`. |
| 냉연/도금 | uncoiler·용접·Scale Breaker·Looper·bath·roll stand·청정·소둔·조질·도유·도금·합금화·전기도금·후처리를 각각 유지. Air Knife는 고정 nozzle의 가스 wiping 상태이며 임의 왕복 부품이 아니다. GA는 Air Knife→합금화→냉각, GI는 합금화 강제 없음. | `showroom:M12/M13`, `src:cold-*`, `src:coating-air-knife`, `src:gi-coating-cooling`, `src:ga-coating-cooling`; [직접 열람 coated 원문](evidence/posco-reference/coated.png), T4 mechanical_basis. |
| 전기강판 | GO 베이스 도포와 최종 절연코팅·자구 미세화를 별도 위치/기능으로 표현. 자구 처리를 일반 inspection으로 바꾸거나 NGO에 GO 전체 처리를 추가하면 실패. | `showroom:M14`, `official:P2`, `src:go-base-coating`, `src:go-domain-refinement`; [직접 열람 GO 원문](evidence/posco-reference/electrical.png). |
| STS/Ti | STS의 CAF/HAPL/CAPL·Shot Blasting과 Ti 단조 press/anvil/manipulator·VAF·TLL/STL/SHL을 구별. Ti는 구매 잉곳부터 시작. TLL 이후 코일 OR STL Skelp OR SHL Sheet이며 STL→SHL을 유일 경로로 만들지 않는다. | `showroom:M15/M16`, `official:P3`, `src:ti-tll-coil`, `src:ti-stl-skelp`, `src:ti-shl-sheet`; [직접 열람 Ti 냉연 원문](evidence/posco-reference/titanium-cold.png). |
| 검사/포장/보관/인도 | probe/scanner와 소재 받침, strap/wrapper, coil cradle/slab dunnage, dispatch/load socket을 구별. 정적 rack은 정상이나 적재 소재가 공중에 뜨면 실패. | `scope:quality:*`, `scope:dispatch`, `src:plate-ultrasonic`, `src:plate-marking`. |
| 운송/항만/입고 | wheels/steering/lift, torpedo vessel/bogie/coupler, rail consist, crane trolley/hoist/grab, ship hold/hatch, unloader·stacker·reclaimer·belt의 기능/상태를 구별. wake·먼지·연기만 움직여 작업으로 세면 실패. | `scope:fleet:*`, `scope:raw-sea:*`, `scope:receiving:*`, `scope:road:*`, `scope:rail:*`, `scope:sea:*`, `official:P5/P6/P7`. |

위 짧은 source 이름은 설명용이다. 기계 판독 exact ID는 registry의 `showroom:M0z` 등과 matrix `source_ids`다. 공개 그림은 기능 개념만 뒷받침하며 자세한 축·치수·속도·SOP는 합성 설계로 남긴다. 전시관 현재 접근 제한, HGI 전용 도식 미확인, Ti 역사 자료 한계는 원문 문서대로 유지한다. 로컬 공정 PNG는 기존 보존명이며 일부 실제 인코딩은 JPEG다. 새 시각 증거는 PNG 확장자와 실제 헤더가 일치해야 한다.

## 4. 라벨·패널·접근성

배경 없는 작은 라벨을 빈 지면에 배치한다. 일반 12px/선택 14px, 최대 폭 160px·2줄·간격 8px, overview 최대 8개가 초기 예산이다. **설비 projected silhouette·작업/접촉부·선택 소재와 라벨의 겹침은 0**이어야 한다. 겹치면 낮은 우선순위 라벨을 숨기고 선택 대상은 외곽 callout/상세 패널로 보낸다. 우선순위는 선택→장애→구역이다. 숨겨진 라벨도 목록·검색·접근성 트리에서 찾을 수 있어야 한다. 검사·오류 의미를 작은 scene text에만 담지 않는다.

데스크톱 패널 248px/외곽 간격16px, scene 가용 폭 최소80%. 1280px 이하 또는 safe rect를 지킬 수 없으면 패널을 접거나 scene 아래로 이동한다. 패널·toolbar를 제외한 safe rect에 카메라 framing을 맞춘다. 긴 한국어·빈 상태·긴 ID·200% 확대·390/1440/1920 폭에서 잘림·가림·가로 넘침을 검사한다. 스크롤은 각 패널 한 곳만 소유한다.

로컬 시스템 sans와 한국어 fallback을 사용한다. 본문 desktop14px/compact17px, line-height1.5, weight400/500/600. 아이콘만 있는 버튼도 이름·tooltip·focus-visible·44px hit target·8px gap을 갖는다. 상태는 색+glyph+문구로 표시하고 본문4.5:1/큰 text·control3:1 대비를 실제 배경에서 측정한다. 선택한 소재/차량/설비의 같은 상태를 접근 가능한 표에서도 읽는다. 새 dark theme는 이번 범위가 아니며 후속 제공 시 별도 캡처 검수한다.

## 5. 카메라·상태·시간 계약

| 입력·모드 | 관찰되어야 할 결과 | 실패 |
| --- | --- | --- |
| overview/detail/follow | 각각 elevation42°/32°/38°, padding12/15/18%의 초기 설계. 선택 run/entity/variant/bundle·material/attachment·sim_ms는 동일. | 보기 전환이 새 공정·복제 material·새 clock을 만듦. |
| 네 방향 pan 버튼 | 위/아래/왼쪽/오른쪽 접근성 이름. `north/south/east/west` 키는 **화면 기준**: 카메라 forward/right의 XZ 투영을 정규화하고 viewport8%씩 camera와 target을 함께 이동. 세계 방위가 아님. | 위에서 보거나 회전했을 때 방향 반전·Y 이동·업무 명령 발생. |
| orbit/zoom | selected 또는 world center를 중심으로 orbit; polar12–80°, zoom2–3000m 초기 bounds. wheel/pinch와 확대/축소 버튼 모두 제공. 세계/선택 bounds와 safe rect에 clamp. | 지면 아래 진입·선택 대상 손실·카메라 때문에 시간 진행. |
| follow | 한 entity의 현재 attachment 위치 추적. 수동 pan/orbit/zoom은 follow만 중지하며 선택 유지. 재추적 버튼으로 같은 entity 재개. | 과거 경로의 복제 소재 추적, 카메라 이동이 배차/생산 명령. |
| cutaway | 동일 asset root의 명시 shell/roof node만 숨김. 내부 부품·collision·소켓·소재·선택 identity 유지. 복귀 시 같은 roof를 복원. | 별도 scene의 정적 전시 장비로 교체. |
| 정상/대기/장애 | 실제 phase/progress에 따라 작업; 대기는 이유+정지, 장애는 이유+경고+정지. 고정 구조는 그대로, state-bound 고정 기능은 작동 상태 표현. | 일이 없는데 blade·hoist·vessel이 무한 왕복. |
| 일시정지/재개 | 승인 pose·attachment를 고정하고 pause glyph. 같은 서버 상태에서 이어짐. | 정지 중 바퀴·소재가 이동하거나 재개 때 원점으로 튐. |
| offline/stale/error | 마지막 확인 상태 고정, 오프라인·원인·재시도 표시; 새 상태 도착 전 extrapolation 금지. | 서버 실패를 empty factory로 표시하거나 자동 reset. |
| 1x/2x/4x·reduced motion | 속도는 wall→server sim에 한 번 적용. reduced motion은 camera easing·decor만 제거, 물리 상태·위치·진행·custody는 보존. | 재생속도 제곱 적용, reduced motion 때문에 소재 숨김/작업 중단. |

hover/pressed/focused/disabled는 각 control의 공유 primitive 상태이며 focus는 색 외 형태로 식별한다. Tab/Enter/Space와 방향 pan 버튼, Escape로 overlay 닫기, gesture의 버튼 대안을 유지한다. 자동 follow에 강제 편입하거나 모션 때문에 입력을 막지 않는다. 인터페이스 전환180ms는 미술값이며 공정 duration과 무관하다.

## 6. 공통 시각 rubric

아래는 실제 자산/variant/placement에 적용한다. 고정 자산도 상태 변화가 없다는 **관찰 증거와 이유**를 기록하며 `N/A=PASS`로 바꾸지 않는다. 하위 점수 평균으로 치명 결함을 상쇄하지 않는다.

| rubric ID | PASS 조건 | FAIL 사례 / 필요한 증거 |
| --- | --- | --- |
| `silhouette` | 기능·형상·family 차이가 조감도와 근접에서 식별됨. | 이름만 바꾼 같은 상자/roller. 3각도 실제 이미지+노드. |
| `mechanism` | T4 function/part ID의 실제 작업부·축·피벗과 서버 phase가 일치. | generic fallback, 장식 loop, 고정 nozzle의 허구 이동. API+part transform+연속영상. |
| `support` | 기초·프레임·적재면과 entry/work/exit/grip/load 지지가 목적에 맞음. 접점·인계 불연속≤0.01m. | 중심만 맞고 바닥/받침 관통·공중부양. 실제 geometry/normal/socket 및 before/mid/after. |
| `materials` | painted metal/구조재/노출재/지면이 구별되고 작업부가 읽힘. | 모두 plastic/거울, 과한 glow로 접점 소실. 같은 조명 조건 이미지. |
| `three_angles` | front/side/rear detail을 같은 run/bundle/source/revision/sim_ms에서 직접 검수. | 한 overview나 정적 reference를 3번 재사용. 각각의 카메라·노드·픽셀. |
| `states` | normal/waiting/blocked/paused/resumed의 원인·pose·연속성이 관찰됨. | 정상 영상만으로 장애/정지를 통과시킴. 상태별 API+image와 연속 video. |
| `single_material` | 한 물리 단위 한 현재 custody; 분할은 parent소비/child등장 시각 일치. | preview와 scene 또는 두 차량에 같은 material 복제. node/API/영상. |
| `same_world` | overview/detail/follow/cutaway가 같은 세계와 업무상태를 사용. | 새 설비/clock/공정 전시. 상태 hash·entity ID·shell 변화 비교. |
| `labels` | 주요 기구·접점·소재와 배경/글자가 겹치지 않음. | 불투명 큰 카드로 열연 stand를 가림. viewport/label bounds+actual pixels. |
| `transport_modes` | road/dispatch rail/hot-metal rail/conveyor/sea를 형상·표식·경계로 구별. | teal 선 하나로 교통모드를 혼합, 화차 도로 주행. 실제 경로/차량/픽셀. |
| `identity_lod` | LOD0/1/2 전환이 identity·socket·attachment·sim_ms·선택을 보존. | 특정 공정만 저정밀 최종품, LOD에서 hook 소실. 같은 run 전환 영상·노드. |
| `accessibility` | keyboard·표·focus·상태 문구·대비·reduced motion이 같은 업무 정보를 전달. | 색만으로 장애 표시, 드래그 전용 pan, 축소 시 라벨 소실만 남음. 실제 입력 trace·픽셀. |

equal polygon count는 요구하지 않는다. LOD 초기 거리180/650m와10% hysteresis는 화면 예산을 위한 설계값이다. bolt/외장 장식은 줄여도 기능 silhouette·작업부·소켓은 유지한다. 신규 kind와 원거리 hall에도 같은 품질 rubric을 적용하며, 성능 측정 전 FPS 달성을 주장하지 않는다.

## 7. 검수표와 완료 권한

`parseVisualReviewMatrix`는 exact ID 집합과 각 행의 target/profile/requirement/source/QA/policy/family 대응을 검증한다. 순서는 자유지만 중복·누락·알 수 없는 행·같은 개수를 유지한 치환은 실패다. 현행 수량은 고정 승인 분모가 아니다. 새 registry/binding/hall이 추가되면 그 행을 명시 추가해야 한다. matrix를 매 실행 자동 재생성해 누락을 숨기지 않는다. 후속 renderer는 `admitVisualInventory(matrix, actualTargetIds)`에 실제 kind/variant/placement ID 목록을 전달해야 한다. 이 함수는 입력 matrix를 먼저 검증하고 등록 밖의 새 실체를 거절한다. 현재 기존 renderer에 연결되었다는 주장은 하지 않는다.

현재 연결은 coverage의 모든 QA 2,195행, T4 policy62행·binding180행(기존158+계획22)·계획 placement22행, 기존 hall31행, 명시 semantic proposal18행이다. 이는 **현재 관찰 수량**이며 테스트는 2,508이라는 상수를 승인 조건으로 사용하지 않는다. 기존 crane/vehicle/path와 새 raw receiving/customer/port 요구도 exact QA ID로 포함된다.

| profile | 적용·증거 책임 |
| --- | --- |
| `physical_asset` | 실제 모델/kind/variant/placement 및 해당 policy/binding. 위 공통 rubric, 같은 시각의 3각도, 5상태·기구/지지·소재 증거. 정책 행은 각 구성 variant/placement 보고서를 연결하며 대표 모델 하나로 전체 통과 금지. |
| `spatial_view` | stage와 hall. overview/detail/cutaway의 맥락·가림·내부/외부 동일세계·개별 배치 clearance. 같은 자산을 두 번 생성하지 않는다. |
| `operational_flow` | 제품·단계·연결·path. T40/T43/T44의 해당 흐름·handoff·같은 소재 follow 증거를 연결한다. 전 경로에 자산 3각도를 추가 강제하지 않는다. |
| `reference_link` | source requirement/disposition/binding. T2 출처·T40 연결 및 해당 T43/T44 보고서를 QA ID로 참조한다. 이 행 자체에 기계 픽셀을 만들지 않으며 visual submission으로 승인하지 않는다. |

`proposed-variant:*`는 ASSET_STANDARD의 dump/flatbed, coil/slab/bulk railcar, bulk/product ship, overhead/yard/port crane, raw/product berth, receiving/production/warehouse hall, road/rail/sea 고객 인도 요구를 놓치지 않기 위한 **계획 행**이다. 세부 고객 연결은 선택된 실제 leg를 뜻하며 모든 고객이 세 모드를 거친다는 뜻이 아니다. T4 `standard` binding을 상세 제작 완료로 간주하지 않는다. 실제 variant/placement가 확정되면 T4 정책·registry 검토와 함께 명시적으로 등록하고 해당 제안 행과 대응을 보존한다. 제안 ID를 실존 asset ID로 사용하지 않는다.

현재 상태는 `pending`과 `evidence:[]`. 향후 `evidence_submitted`는 다음 구조가 갖추어진 **접수**일 뿐이며 `visual_approval`은 계속 `pending_actual_evidence`다. `complete`, `pass`, `approved`, reference PNG를 실제 증거로 대입하는 payload는 이 계약에서 거절한다.

접수 레코드: author_id/reviewer_id(서로 다름), exact target_id, source_bundle_sha256, captured_at, captures[]. 각 capture에는 id, run_id/bundle_sha256/source_sha256/seed/revision/sim_ms, view/angle/state, image/API/scene_nodes의 `.omo/evidence/...` 경로+SHA256을 기록한다. video, artifact_manifest, independent_report도 경로+SHA256으로 연결한다. 모든 캡처는 같은 run/bundle/source/seed이고, 3각도는 같은 revision/sim_ms여야 한다. 상태 전이의 시각은 실제 순서를 유지한다. 임의 path/hash 문자열만으로 바이트 검증이 되지는 않는다.

후속 T45 독립 검토자는 같은 소스 리비전의 실제 artifact를 열어 해시·헤더·크기·target/run/time·영상 연속성을 검증하고 각 rubric을 판정한다. 실제 API/scene의 pose·소켓·custody와 캡처를 대조하고, T12의 원본/GLB 재생성 검증을 연결한다. 해당 독립 보고서가 exact matrix row IDs를 열거하며, T43/T44 흐름 증거와 교차 연결한다. 최종 승인 ledger/판정은 별도 검증 게이트가 소유한다. **이 파서는 존재하지 않는 파일을 열어 검사하지 않으며, 접수 JSON의 verdict를 시각 PASS로 반환하지 않는다.** 기능·시각 검수 후 소스가 바뀌면 영향 행의 증거를 다시 캡처한다.

## 8. 실행·검증·남은 작업

프로젝트 루트에서 `npm test -- src/operations/scene/visualTokens.test.ts -t complete`, `-t unreviewed_variant`, 전체 해당 파일 시험을 실행한다. `tsc --noEmit --incremental --tsBuildInfoFile <owned-temp>/tsconfig.tsbuildinfo`로 개인 빌드정보를 사용한다. `parseVisualReviewJson`은 중복 JSON key까지 거절한다. actual module invocation과 failure 로그는 현재 T7 evidence 디렉터리에 기록한다.

이번 작업은 토큰/검수표/입구 계약과 문서만 변경한다. 화면·CSS·기존 SceneLabel·자산 생성·DB·서버·dist를 바꾸지 않는다. 후속 T8/T12/T13/T19–29/T31–32/T43–45가 실제 세계·기구·controls·시각 증거를 구현/검증해야 한다. 따라서 현재 라벨 겹침0, 실제 기구 접촉≤1cm, 카메라 제어, 접근성, 성능은 **설계 목표 및 미검증 요구**이며 이번 테스트 통과를 그 실제 달성으로 표현하지 않는다.
