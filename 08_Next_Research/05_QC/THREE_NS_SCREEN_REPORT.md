# L1P1x2 총 3 ns 초기조건 비교 보고서

> **PROVISIONAL / EXPLORATORY ONLY**  
> 이 보고서는 2–3 ns 구간의 잠정 stationarity 및 세 시작 밀도의 민감도 비교다. 평형·독립 replica·production 조건을 검증한 결과가 아니다.

## 핵심 판정

- 교차 시작조건 판정: `THREE_NS_SAME_BASIN_CANDIDATE`
- 판정 의미: 세 체인이 잠정 stationarity 문턱을 통과했고 마지막 1 ns 평균 밀도 spread가 2% 이하인 상태다. 독립 replica 설계를 위한 임시 후보일 뿐이다.
- 2–3 ns 평균 밀도의 chain 간 spread: 1.256%
- 임시 대표 chain: `pilot_L1P1x2_rho1400_v6` — 독립 replica 설계용 임시 후보
- 공통 seed: `110001`
- protocol 동일성: 확인됨
- 독립 replica 여부: **아님** — 세 chain은 같은 seed를 사용한 시작 밀도 민감도 비교다.

## Chain별 마지막 1 ns QC

주 분석 구간은 2–3 ns이며, block 지표는 200 ps × 5개로 계산된 값이다.

| chain | 초기 밀도 (kg/m³) | 2–3 ns 평균 밀도 (kg/m³) | 밀도 slope (%/ns) | 마지막 두 block 차이 (%) | 인접 block 최대 차이 (%) | 1–2 vs 2–3 ns 차이 (%) | min box/(2rlist) | THREE_NS 판정 | fail/review 사유 | 임시 대표 |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| screen_L1P1x2_rho1000_20260807 | 1000.0 | 1505.35 | 0.269 | 0.360 | 0.360 | 0.178 | 1.2472 | `THREE_NS_STATIONARITY_CANDIDATE` | 없음 | 아니오 |
| screen_L1P1x2_rho1200_clean_20260807 | 1200.0 | 1524.39 | 0.373 | 0.045 | 0.425 | 0.221 | 1.2419 | `THREE_NS_STATIONARITY_CANDIDATE` | 없음 | 아니오 |
| pilot_L1P1x2_rho1400_v6 | 1400.0 | 1518.93 | 0.061 | 0.037 | 0.098 | 0.006 | 1.2418 | `THREE_NS_STATIONARITY_CANDIDATE` | 없음 | 예 (replica 설계용 임시 후보) |

`THREE_NS_STATIONARITY_CANDIDATE`는 마지막 1 ns의 잠정 문턱을 통과했다는 뜻뿐이며, 열역학적 평형 판정이 아니다. 임시 대표 chain도 후속 독립 replica 설계를 위한 계산상 후보일 뿐 물리적으로 참인 밀도나 우수한 chain을 뜻하지 않는다.

## 검증 상태

- 입력 비교 technical status: `PASS_COMPLETE`
- 입력 비교 analysis status: `PASS_COMPLETE`
- 물리 상태: `EXPLORATORY_ONLY`
- 평형 검증: **Not verified / 미검증** (`equilibrium_validated=false`)
- production 준비 상태: **Not verified / 미검증** (`production_ready=false`)

### 추가 미검증 항목

- 열역학적 평형
- 독립 Packmol 배치와 독립 속도 seed를 사용한 replica 재현성
- production 조건 및 준비 상태
- 구조·수송 물성의 수렴
- 연구실 서버 재현

## 출처

- 비교 JSON: `three_ns_screen.json`
- 비교 JSON SHA-256: `f30ecb8c1fb44d369fb30b2e1f7b7bd2eb0831a6af0170329b4b0271c5016438`

이 Markdown은 비교 JSON을 사람이 읽기 쉽게 옮긴 파생 보고서이며 새로운 물리 판정을 추가하지 않는다.
