# L1P1x2 독립 replica 1 ns 탐색 비교 규칙

> **사전 고정 시각:** 2026-08-07T04:23:55+09:00  
> **적용 범위:** Packmol seed와 GROMACS 초기 속도 seed가 모두 다른 R1·R2·R3의 NVT 100 ps + NPT 1 ns 결과  
> **해석 한계:** 이 규칙은 초기 반복 간 일치 여부와 동일 길이 연장 필요성을 고르는 탐색 규칙이다. 평형, production 가능성, force field 정확도 또는 수송 물성을 판정하지 않는다.

이 문서는 R1 결과가 `SCREEN_EXTEND`임을 확인한 뒤, R2·R3의 NPT 결과가 나오기 전에 고정했다. 결과를 보고 특정 replica만 선택하거나 문턱을 완화하지 않는다.

## 필수 독립성 및 비교 가능성

- Packmol seed는 R1/R2/R3에서 각각 240101/240102/240103이어야 한다.
- GROMACS NVT `gen-seed`는 각각 110101/110102/110103이어야 한다.
- Packmol 초기 좌표, EM 후 좌표 및 NVT 산출물 hash는 replica 간 달라야 한다.
- 조성, 요청 밀도, topology, 활성 force-field, 전하 스케일 0.75, EM/NPT protocol, GROMACS 버전과 OpenMP 스레드 수는 같아야 한다.
- NVT MDP의 전체 hash는 `gen-seed` 때문에 달라질 수 있으므로, 비교 때는 seed 줄만 정규화한 protocol fingerprint를 사용한다.
- 위 조건을 확인하지 못하면 결과가 좋아 보여도 `ONE_NS_REPLICA_NOT_COMPARABLE`로 판정한다.

## 단일 replica 판정

`run_equilibration.py`가 미리 구현한 `SCREEN_FAIL`, `SCREEN_EXTEND`, `SCREEN_STATIONARITY_PASS`를 그대로 사용한다. strict `grompp` warning, Fatal, NaN/Inf, LINCS/segfault, 시간·파일 불연속, 평균온도 범위 이탈, 과도한 부피 jump 또는 `min(box)/(2×rlist) ≤ 1.0`은 실패다.

안전한 체인 중 다음 stationarity 문턱을 모두 통과해야 `SCREEN_STATIONARITY_PASS`다.

- NVT/NPT cutoff 여유 ≥ 1.10
- 마지막 500 ps 밀도 slope ≤ 1.0%/ns
- 마지막 두 100 ps 밀도 block 차이 ≤ 1.0%
- 최대 인접 밀도 block 차이 ≤ 2.0%
- NVT 온도 slope 절댓값 ≤ 2 K/ns
- NVT 마지막 두 온도 block 차이 ≤ 3 K
- NPT 온도 slope 절댓값 ≤ 2 K/ns

안전하지만 하나라도 stationarity 문턱을 넘으면 `SCREEN_EXTEND`다.

## Replica 간 밀도 통계

각 replica의 마지막 500 ps 평균 밀도를 하나의 독립 관측치로 사용한다. 501개 energy frame을 서로 독립인 표본으로 간주해 SEM을 계산하지 않는다.

- spread = `(최댓값 - 최솟값) / replica 평균 × 100`
- pairwise 대칭 차이 = `|a-b| / ((|a|+|b|)/2) × 100`
- replica 평균, 표본표준편차, 기술적 CV, 최솟값·최댓값을 함께 기록한다. CV는 hard gate로 쓰지 않는다.

## 최종 판정 우선순위

1. 3개 중 미완료가 있으면 `ONE_NS_REPLICA_COMPARISON_PENDING`
2. 독립성·동일 protocol/hash가 확인되지 않으면 `ONE_NS_REPLICA_NOT_COMPARABLE`
3. technical failure, `SCREEN_FAIL` 또는 hard fail이 있으면 `ONE_NS_REPLICA_SET_FAIL`
4. cutoff 여유가 1.0보다 크지만 1.10보다 작으면 `ONE_NS_REPLICA_SIZE_REVIEW_REQUIRED`
5. 밀도 spread 또는 최대 pairwise 차이가 5%를 넘으면 `ONE_NS_REPLICA_DISPERSION_OR_INCOMPLETE`
6. 하나라도 `SCREEN_EXTEND`이거나 spread/최대 pairwise 차이가 2%를 넘으면 `ONE_NS_REPLICA_UNIFORM_EXTENSION_REQUIRED`
7. 세 체인이 모두 `SCREEN_STATIONARITY_PASS`이고 두 교차 지표가 모두 2% 이하면 `ONE_NS_REPLICA_EARLY_AGREEMENT_CANDIDATE`

마지막 판정도 1 ns 초기 일치 후보일 뿐이다. 대표 replica는 선정하지 않는다. 다음 단계가 허용되면 안전한 세 replica를 모두 같은 총 길이로 연장한다. hard fail 체인은 제외한 채 3-replica 결과로 부르지 않고, 새 seed와 새 chain ID로 처음부터 대체한다.

## 검증 수준

- **Implemented**: 판정 규칙을 결과 전에 이 문서로 고정했다.
- **Unit-verified**: 비교 구현과 테스트는 아직 작성 전이다.
- **Physical-device-verified**: R1의 실제 1 ns 산출물은 존재하지만, 세 replica 비교는 아직 완료되지 않았다.
- **Not verified / 미검증**: 독립 3-replica 비교 결과, 평형, production, 구조·수송 물성, 연구실 서버 재현성.
