# 가상 해안 제철소 공간 v2

이 파일은 T8의 합성 공간·물리 경로를 설명한다. 실제 공장 측량, 완성된 Blender 자산, 동적 교통 예약 또는 운영 화면 활성화의 완료 보고는 아니다. 승인 시안 A/B/C의 긴 공정동·야드·분리 부두·밝은 미니어처 방향을 지원하는 같은 미터 좌표계를 사용한다. 설비별 실제 자산의 치수·소켓은 T12와 이후 배치 단계에서 이 공간에 다시 대조한다.

T56의 독립 공간 게이트가 승인한 `repair-02/candidate02.json`의 동일 바이트를 [현재 월드](../shared/factory-world-v2.json)에 설치했다. SHA256은 `d2b9ab5afdb064f4f22da193c806ded0af43a2110f815d2ac4b9213b6411562b`이다. [전체 도면](evidence/factory-world-v2/overview.png), [캠퍼스 도면](evidence/factory-world-v2/campus-overview.png), [38장 manifest](evidence/factory-world-v2/manifest.json), [번호 위치 기록](evidence/factory-world-v2/callouts.json)은 승인된 원본 바이트다. 증거 기준 경로는 `.omo/evidence/uniform-fidelity/uf-20261027-resume02/task-56/`이며 `repair-02/`에 소스·생성 proof·개별 38장 열람, `verify-02/`에 독립 수락, `install/`에 설치·실제 MAIN 검증과 복구 기록이 있다. 생성 proof/owner는 원래 출력 경로에 묶인 채 보존하며 공유 경로용으로 다시 쓰지 않았다. MAIN 설치의 독립 검토와 이후 3D 단계는 별도다. 원래 T8과 candidate01의 실패 기록도 보존한다.

## 재현 명령

프로젝트 루트 `/Users/ethanlee/Desktop/ERP`에서 이미 설치된 런타임을 사용한다. 출력 경로는 **필수**다. 다음은 설치 소스로 새 증거 경로에 재현하는 예시다. 실행마다 아직 없는 출력 경로를 선택한다.

```sh
backend/.venv/bin/python tools/build_factory_world_v2.py --output .omo/evidence/uniform-fidelity/uf-20261027-resume02/task-56/install/reproduce-new.json
```

이미 존재하는 출력은 기본적으로 거절한다. 새 실행은 새 경로를 사용한다. 동일 작업의 증거를 명시적으로 교체할 때만 `--replace-owned`를 추가할 수 있으며, 정규화된 경로가 프로젝트 `.omo/evidence` 안에 있고 기존 바이트·절대 경로·생성기 이름이 `.owner.json`과 정확히 일치해야 한다. 심볼릭 링크와 그 하위 경로, 보호된 기존 공유 파일, 기존 동반 파일의 임의 덮어쓰기를 거절한다. 표준 출력에 성공 문구가 있어도 종료값과 실제 파일·proof SHA를 확인한다. 검증 실패 시 최종 출력은 게시하지 않는다. 취소가 게시 중간에 발생했다면 소유 marker와 바이트가 불일치한 출력을 정상으로 재사용하지 않으며 새 명시 경로로 재생성한다.

도면 렌더러는 설치된 **bundled Python 3.12의 Pydantic와 Pillow를 함께** 사용한다. backend Python 3.13의 site-packages를 섞지 않는다. 과거 ABI 혼용 하네스 실패와 복구 기록은 원래 증거에 보존했다.

```sh
PYTHONPATH="$PWD/backend:$PWD" /Users/ethanlee/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tools/factory_world/blueprints.py --world .omo/evidence/uniform-fidelity/uf-20261027-resume02/task-56/install/reproduce-new.json --output .omo/evidence/uniform-fidelity/uf-20261027-resume02/task-56/install/blueprints-new
```

도면 디렉터리는 새 경로여야 한다. 렌더러도 동일 raw bytes를 전체 물리 검증한 뒤 그 `ValidatedFactoryLayout.world`에서만 그린다. 전체·캠퍼스 확대·31개 구역·5개 운송 모드 주차 확대의 38장과 `manifest.json`, 실제 번호·연결점 위치를 담은 `callouts.json`을 만든다. 번호 원은 배경 공정동까지 포함한 모든 투영 footprint와 접점·다른 번호를 피한다. 지도 영역에만 그리므로 외곽 경로가 제목과 범례를 덮지 않는다. 수면 색은 실제 sea node와 항만 크레인 위치에서 얻은 문맥 표시이며, 항행 판정은 sea segment/profile/berth가 소유한다. 도면의 위치를 별도 3D 좌표로 재사용하지 않는다.

각 명령의 실제 QA는 `RUN_TMP`, `TMPDIR`, Python/Node/Bun 캐시, pytest 임시 경로를 증거 디렉터리 아래로 지정했다. 이번 설치는 승인된 소스 8개 교체·2개 생성, 공유 월드 1개와 도면 증거 40개만 게시했다. 서버·기본 dist·DB·보호 포트는 변경하지 않는다. 정확한 환경·시간 제한·종료값과 MAIN 소스 바인딩은 `install/commands/`에 있다.

## 공간과 실제 접점

북쪽은 입고·구입재·원료장, 중앙은 탄소강 제선/제강→연주→열연/후판/선재→냉연/도금/전기강판, 남쪽은 STS/Ti와 검사·포장·출하, 동쪽은 분리된 원료/제품 부두다. 외곽 고객은 해상 항로·외부 우회 도로·철송으로 연결한다. 해상 두 회랑은 동측 항로로 연결되며 육상 도로는 수면 북쪽을 우회한다.

공정동 길이는 각 설비의 합성 치수와 작업 간격에서 계산한다. 북측 입고와 중앙 열연·냉연·도금은 공유 간선에 연결한다. GO·NGO는 중앙 동쪽의 긴 남북 공정동이며, 남쪽 STS·Ti는 중앙 서비스 간선과 동측 외곽 간선으로 나뉘어 연결한다. 전기강판 블록 북·남쪽의 공유 회랑이 순환 동선을 이루고, 공정별 접근로는 실제 도크/정차점에 연결된다. 도로 교차점은 공통 노드로 분할한다. 서측 x=-250과 동측 x=3050 간선 전체를 잇는 동서 회랑은 z=-1490, 1180, 3520의 세 곳이며, 나머지는 실제 도크·정차점으로 끝나는 국소 접근로다. 도로 노드 375개는 양방향으로 연결되고 기존 396개 수송 route의 실제 경로 형상을 보존한다. 72개 육상 주차 위치는 북측 네 줄로 묶었다. 일반 철송·용선·래들 선로에는 실제 정차점 앞뒤로 편성과 하중 전체를 받치는 여유 선로가 있다. 100개 위치는 truck32/slab-carrier12/coil-carrier12/forklift16/torpedo4/ladle-car4/locomotive4/railcar12/ship4이며, 고정 크레인을 이 수에 넣지 않는다. 이는 주차·접근·복귀의 **설계 수용량**이고 100대 동시 운영이나 성능 측정 결과가 아니다.

기존 158개 설비, 31개 hall, 24개 기존 구역을 포함한 31개 구역, 20개 제품의 348개 컴파일 단계·428개 제품별 연결을 T2의 exact ID와 대조한다. T2에서 누락되었던 41개 원문 기능은 적용 제품마다 독립 작업 위치를 갖는다. 개수만 맞춘 ID 치환, 외부 운송 패드를 작업 포트로 치환, 잘못된 구입재 진입, GO 베이스 도포/후단 절연코팅 혼동, cutter/cooling 순서 위반을 거절한다. Ti의 TLL 코일 출구, STL skelp 출구, 별도 sheet line의 SHL 출구는 각각 작업→크레인→운송 도크에 연결되어 다른 출구를 반드시 통과하도록 강제하지 않는다. 다른 선택 분기의 작업·내부 이송 접점은 차단한다. 해당 설비의 `dock`이 포트와 노드 모두 road 전용일 때에는 원래 road segment의 통행만 허용하며, 그 도크를 이용한 크레인 인계는 허용하지 않는다. 제품의 업무 레시피 실행과 형상 변환은 이후 T18/T27이 소유한다.

`work`는 실제 설비 내부 접점이고 `transfer`·`dock`은 별도의 이송 접점이다. T12 대표의 CUT-SLAB local work `(0.3, 1.05, 0)`와 galvanizing local work `(0, 1.76, 0)`를 physicalScale=1로 보존하며, 외부 transfer `(0, 2, -30)`와 구별한다. roller가 설비 본체를 관통하지 않고 검증된 crane reach가 그 내부 작업 접점을 인계한다. 지지판의 상면은 0m이며, 차량 body/load의 중심은 graph support/contact에 대한 **signed** offset으로 계산한다. 낮춘 proxy나 출발/도착 owner 면제로 충돌을 숨기지 않는다.

## 물리 검증 경계

`validate_factory_layout(raw_bytes, LayoutRequirements.read(root))`는 일반 world parser와 구분되는 전체 공간 입구다. spatial 없는 구형 작은 fixture는 일반 parser에서 계속 유효하지만 전체 공간 입구에서는 실패한다. 반환 proof는 immutable world, 원본 바이트 SHA256, 독립 requirements/policy SHA256에 묶이며 world 안에 재귀 self-hash를 넣지 않는다. T3 bundle manifest와 T5 DI manifest의 기존 의미는 그대로다.

- 모든 segment와 route, segment 사이 junction에 같은 `fillet_trajectory`의 접선 직선·원호를 적용한다. 반경·접선 길이가 부족하면 거절하며 꺾인 각도로 대체하지 않는다. 원호는 analytic primitive이고 충돌 계산의 chord에는 실제 sagitta 오차를 더한다.
- body/load/consist를 모두 포함한 보수적인 수평 원형 sweep과 signed 수직 구간으로 고정 footprint를 검사한다. 허용 hall 내부는 해당 mode/profile/segment·실제 개구부의 폭/높이를 갖는 범위에 한정한다. fixed body나 owner를 통째로 제외하지 않는다.
- 모든 기하학적 경로 충돌은 두 수직 envelope가 실제로 겹치는지 확인한다. 1cm 이상의 중심 높이 차이만으로 입체 교차라고 인정하지 않는다. 평행 근접 구간과 junction fillet도 놓치지 않도록 수평 conflict 구간은 차량 원형 envelope에 최소 회전 반경을 더한 보수적인 경계를 사용한다. 그에 따른 추가 자원 점유는 안전한 과대 근사다. 실제 interval 예약은 T15의 책임이다.
- 크레인은 실제 hook 소켓의 world transform에서 모든 pick/drop 작업 포트의 반경과 높이를 검사한다. 일반 철송/용선/래들의 길이·후진·편성 끝 정차 여유, 부두 길이·깊이·접근 구간을 검사한다.
- 주차 위치의 body 바닥과 지지판 상면은 0m다. 초기 차량·적재물 overlap은 양쪽 실제 수직 envelope로 검사하며 입력 배열 순서에 의존하지 않는다. 각 위치에는 적재 접근·빈차 복귀·안전 holding route가 있다. 차량이 다른 운송 모드의 그래프를 빌려 접근 가능한 것으로 처리하지 않는다.

이 파일은 스케줄러·입고 원장·품질·출하의 업무 정책, 실제 GLB의 완성도, 가감속/조향 rig·선박 유체역학을 구현하지 않는다. T9/T11/T15 이후는 이 검증된 world와 profile·접점·trajectory를 소비하고 같은 바이트를 번들에 고정해야 한다. 실제 자산 형상 변경이나 공간 변경 시 영향을 받는 검증과 도면을 다시 만든다.

## 검증 근거

이번 실행의 실제 Python 전체 대상 검사, TS 공간 계약 검사, 전체 TypeScript 타입 검사, Python/TS가 동일 후보 바이트를 읽은 SHA 비교를 증거로 남겼다. 장애 입력은 실제 후보 복사본으로 보존하며 obstruction/deadend/turn/interior/crane/coverage/parking/crossing/rail/berth/hash를 구체적으로 거절한다. 단순 PNG 존재나 진행 로그를 시각 검수로 승격하지 않는다. 작성자와 독립 Astra High 검토자가 최종 38장 전부를 실제 열람했다. `repair-02/visual-review.json`과 `verify-02/visual-review.json`에 관찰을 기록했다. 배경 공정동을 포함한 353개 번호의 footprint·접점·다른 번호 겹침은 0개다. 독립 private 공간 게이트 수락은 `verify-02/AdversarialVerify.json`에 있으며, MAIN 설치 수락은 별도 독립 게이트가 결정한다.
