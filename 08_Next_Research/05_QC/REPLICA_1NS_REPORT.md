# L1P1x2 독립 replica 1 ns 탐색 보고서

> **EXPLORATORY ONLY / NOT EQUILIBRIUM**  
> 서로 다른 Packmol 배치와 초기 속도를 사용한 R1·R2·R3를 로컬 Mac에서 NVT 100 ps + NPT 1 ns까지 실행했다. 이 결과는 짧은 시간의 반복 간 일치와 다음 연장 결정을 위한 자료이며, 평형·production·물성을 검증하지 않는다.

## 결과

| replica | Packmol seed | velocity seed | 마지막 500 ps 평균 밀도 (kg/m³) | 단일 체인 판정 |
|---|---:|---:|---:|---|
| R1 | 240101 | 110101 | 1513.9613 | `SCREEN_EXTEND` |
| R2 | 240102 | 110102 | 1515.5650 | `SCREEN_EXTEND` |
| R3 | 240103 | 110103 | 1516.7580 | `SCREEN_EXTEND` |

- replica 평균: **1515.4281 kg/m³**
- replica 간 표본표준편차: **1.4034 kg/m³**
- 기술적 CV: **0.0926%**
- 최댓값–최솟값 spread: **0.1846%**
- 최대 pairwise 대칭 차이: **0.1846%**
- 최종 탐색 판정: **`ONE_NS_REPLICA_UNIFORM_EXTENSION_REQUIRED`**

세 밀도는 1 ns 마지막 절반에서 매우 가깝지만 세 체인 모두 사전 고정한 짧은-window stationarity 문턱 중 하나 이상을 넘었다. 특히 NVT 마지막 50 ps의 온도 slope는 짧고 잡음이 큰 구간에서 R1/R2/R3 각각 47.20, 74.56, -92.03 K/ns였다. R2는 NVT 마지막 두 온도 block 차이 3.42 K와 NPT 온도 slope -2.34 K/ns도 문턱을 넘었다. hard fail은 없으므로 실패가 아니라 **세 체인을 동일 길이로 연장해야 하는 상태**다.

## 독립성·비교 가능성

강화된 비교기가 다음을 실제 파일과 hash로 다시 확인했고 모두 통과했다.

- 계획된 Packmol seed와 NVT `gen-seed`의 입력·manifest·시도 기록·최종 metrics 교차 일치
- Packmol 초기 좌표, EM 좌표, NVT 출력 좌표의 replica 간 고유성
- 동일 조성 Li 50 / Pyr13 50 / FSI 100, 초기 밀도 1400.0339 kg/m³, 전하 스케일 0.75
- 동일 topology·force-field source·EM/NPT MDP·정규화된 NVT MDP·GROMACS 버전
- 실제 GROMACS 로그의 OpenMP 스레드 6개
- NVT EDR 0–100 ps, NPT EDR 0–1000 ps와 주요 EDR/log/TPR/CPT/XTC/GRO·시도 snapshot provenance
- 사전 입력 감사 v3와 실행 입력 `initial.gro`의 SHA-256 결속

대표 replica는 선정하지 않았다. 분석 단위는 동일 길이의 세 replica 집합이며, 다음 단계도 특정 체인이 아니라 안전한 세 체인을 함께 총 3 ns로 연장하는 것이다.

## Mac 안전 기록

- 보호 기준: 가용 battery/virtual 센서 60 °C 일시정지 / 50 °C 재개, 15초 간격
- 실행 제한: 한 번에 한 replica, OpenMP 스레드 6개
- 세 Packmol→EM 및 세 NVT/NPT guard 전체 최고 관측값: **41.25 °C**
- guard 종료 6/6건 rc 0, pause/resume 0건, macOS 열·성능 경고 0건
- **Not verified / 미검증**: CPU die 온도. 관리자 권한 없이 읽을 수 없어 위 기준은 가용 battery/virtual 센서에만 적용됐다.

## 불변 근거

- 비교 JSON: `replica_1ns_comparison.json`
  - SHA-256: `3aad60a8f2a32a2209627b6e765de81b0958f1e659f493afe6123ac45db110d8`
- 사전 고정 비교 규칙: `02_Protocol/REPLICA_1NS_COMPARISON_RULES.md`
  - SHA-256: `c9d3608be93162bb0eea9ef03b061c3734a09d8c3758c4b0559d164724eec627`
- 사전 입력 감사 v3: `replica_input_audit_v3.json`
  - SHA-256: `72b18746ffb250dedc26b15864d4780b4420fca6efbd75da8910c55c9c469a5b`

## 검증 수준

- **Implemented**: 사전 고정 규칙, provenance-hard 1 ns replica 비교기, 불변 비교 JSON과 이 보고서가 존재한다.
- **Unit-verified**: 전체 104개 테스트가 통과했다.
- **Simulator-verified**: 해당 없음.
- **Physical-device-verified**: 로컬 Mac에서 R1·R2·R3 각각 Packmol → strict grompp → EM → NVT 100 ps → NPT 1 ns를 한 번에 하나씩 실제 실행했다. 세 기술 상태는 `PASS_COMPLETE`, strict warning·hard fail은 0건이며 실제 산출물 비교는 `PASS_COMPLETE`다.
- **Not verified / 미검증**: 열역학적 평형, production readiness, force-field 물리 정확도, 구조·수송 물성 수렴, 총 3 ns 독립 replica 결과, 연구실 서버 재현성.
