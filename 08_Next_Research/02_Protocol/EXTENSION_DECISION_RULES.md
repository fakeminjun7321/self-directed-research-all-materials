# 1 ns → 총 3 ns NPT 연장 결정 규칙

> **PROVISIONAL / EXPLORATORY ONLY**  
> 이 문서는 L1P1x2 초기 밀도 1,000·1,200·1,400 kg/m³ 민감도 탐색에서, 첫 1 ns C-rescale NPT 후 어떤 chain을 총 3 ns까지 연장할지 사전에 결정하는 잠정 규칙이다. 이 규칙의 통과는 평형, force field, production trajectory, 구조·수송 물성을 검증하지 않는다.

## 1. 연장의 정확한 의미

- 연장 목표는 **NPT 총 3 ns**이다. 첫 1 ns에 3 ns를 더하는 것이 아니라, checkpoint에서 **2 ns를 추가**한다.
- 첫 1 ns의 박스·좌표·속도·barostat/thermostat 상태를 checkpoint로 이어받는다.
- NVT를 다시 실행하거나 속도를 새로 생성하지 않는다.
- topology, 전하 스케일, cutoff, thermostat, barostat, `tau-p`, `compressibility`, 온도·압력 조건을 연장 중에 바꾸지 않는다. 조건을 바꾸면 같은 chain의 연장이 아니라 새 protocol 실험으로 분리한다.
- 원본 1 ns 산출물은 불변으로 보존하고, 연장 산출물은 같은 chain의 별도 extension stage/record ID로 기록한다.

`scripts/run_equilibration.py`의 현재 manifest는 seed·NPT 길이·입력 hash를 불변으로 만든다. 따라서 완료된 1 ns 폴더에 `--npt-ps 3000 --resume`을 적용해 현재 manifest를 덮어쓰면 안 된다. 연장은 원본 `npt.cpt`를 출처로 기록하는 별도 후속 stage로 생성하고, 전·후 checkpoint·TPR·MDP·topology hash를 남겨야 한다.

## 2. 1 ns 후 chain별 연장·중단 규칙

### 2.1 즉시 중단

다음 중 하나라도 해당하면 해당 chain을 3 ns로 연장하지 않는다.

- technical status가 `PASS_COMPLETE`가 아님
- Fatal error, NaN/Inf, LINCS warning, segmentation fault, 설명되지 않은 `grompp` warning 존재
- `SCREEN_FAIL`이거나 `hard_fail_reasons`가 하나 이상
- NVT 또는 NPT의 `min(box)/(2×rlist) ≤ 1.0`
- NVT/NPT 평균온도가 293–303 K 밖
- 인접 energy frame 간 부피 변화가 5% 초과
- checkpoint·EDR·XTC 시간 범위나 입력 hash의 연속성을 증명할 수 없음

중단 chain을 단순히 더 길게 돌려 구제하지 않는다. 원인을 수정하면 새 chain ID로 처음부터 다시 검증한다.

### 2.2 cutoff 여유 부족

`SCREEN_EXTEND`이더라도 NVT 또는 NPT의 `min(box)/(2×rlist)`가 1.0 초과 1.10 미만이면 현재 크기로 시간만 연장하지 않는다. 이 경우는 시스템 크기·시작 밀도·cutoff 설계를 재검토하고 새 입력을 만든다.

### 2.3 총 3 ns까지 연장

다음을 모두 만족한 chain은 상태를 시정하지 않고 2 ns를 추가한다.

- technical status = `PASS_COMPLETE`
- `hard_fail_reasons = []`
- NVT·NPT `min(box)/(2×rlist) ≥ 1.10`
- 원본 checkpoint와 연장 입력의 연속성·hash 확인
- `SCREEN_EXTEND` 또는 `SCREEN_STATIONARITY_PASS`

`SCREEN_STATIONARITY_PASS`도 1 ns 평형 증명이 아니므로, 세 초기 밀도를 공정하게 비교할 때는 위 조건을 만족한 chain을 모두 같은 총 3 ns까지 연장한다. 첫 1 ns에서 가장 좋아 보이는 chain 하나만 고르면 selection bias가 생긴다.

## 3. 총 3 ns 후 단일 chain QC

### 3.1 분석 window

- 총 NPT 시간: 0–3 ns
- 주 판정 window: **2–3 ns, 마지막 1 ns**
- block: 200 ps씩 5개
- 보조 비교: 1–2 ns 평균과 2–3 ns 평균
- 첫 0–1 ns와 연장 1–3 ns의 EDR·XTC 시간이 중복·공백 없이 연속인지 먼저 확인

현재 `run_equilibration.py`의 `SCREEN_*`는 NPT 길이가 3 ns여도 마지막 500 ps만 판정한다. 따라서 **현재 runner의 verdict만으로 아래 3 ns 규칙을 통과했다고 표현하면 안 된다**. 마지막 1 ns를 별도로 추출해 잠정 QC를 다시 계산한다.

### 3.2 3 ns 잠정 stationarity 문턱

다음은 평형 합격이 아니라 `THREE_NS_STATIONARITY_CANDIDATE`를 부여하는 임시 문턱이다.

| 항목 | 2–3 ns 잠정 문턱 | 판정 |
|---|---:|---|
| Fatal·NaN/Inf·LINCS·segfault·설명 안 된 warning | 0 | 1개라도 있으면 `THREE_NS_FAIL` |
| `min(box)/(2×rlist)` | 전체 0–3 ns에서 ≥1.10 | ≤1.0은 fail; 1.0–1.10은 시간 연장 금지 |
| 인접 energy frame 부피 변화 | ≤5% | >5%면 fail |
| 2–3 ns 평균온도 | 293–303 K | 밖이면 fail |
| 온도 slope | ≤1 K/ns | 초과하면 `THREE_NS_EXTEND_OR_REVIEW` |
| 밀도 slope | ≤0.5%/ns | 200 ps block 평균 5개로 계산 |
| 마지막 두 밀도 block 대칭 차이 | ≤0.5% | 초과하면 `THREE_NS_EXTEND_OR_REVIEW` |
| 인접 밀도 block 최대 대칭 차이 | ≤1.0% | 초과하면 `THREE_NS_EXTEND_OR_REVIEW` |
| 첫 500 ps–뒤 500 ps 밀도 대칭 차이 | ≤1.0% | 초과하면 `THREE_NS_EXTEND_OR_REVIEW` |
| 1–2 ns vs 2–3 ns 밀도 대칭 차이 | ≤2.0% | 초과하면 장시간 드리프 우려 |

대칭 차이는 `|a-b| / ((|a|+|b|)/2) × 100`으로 계산한다. 밀도 slope는 200 ps block 평균 5개의 선형 기울기를 2–3 ns 평균 밀도로 나눈 %/ns이다.

압력, potential energy, 부피 통계는 전체 시계열과 200 ps block별로 보존하되, 현재 3 ns 규칙에서 단일 수치 hard gate로 사용하지 않는다. 압력의 큰 자기상관·유한 크기 변동을 무시한 짧은 window 평균으로 평형을 선언하지 않는다.

## 4. 총 3 ns 후 cross-start 판정

세 chain의 비교는 같은 총 3 ns 길이와 같은 분석 window에서만 한다. 각 chain의 2–3 ns 평균 밀도 ρ̄를 사용하여 다음을 계산한다.

`spread = (max(ρ̄) - min(ρ̄)) / mean(ρ̄) × 100`

| 조건 | cross-start 판정 | 다음 결정 |
|---|---|---|
| 세 chain 모두 `THREE_NS_STATIONARITY_CANDIDATE`, spread ≤2% | `THREE_NS_SAME_BASIN_CANDIDATE` | 독립 replica 계획용 임시 후보만 선정 |
| 세 chain이 안전하지만 하나라도 잠정 문턱 미충족, 또는 spread >2% 및 ≤5% | `THREE_NS_INITIAL_CONDITION_DEPENDENCE_OR_INCOMPLETE` | 안전 chain을 총 5 ns까지 동일하게 연장하거나 protocol 재검토 |
| spread >5% | `THREE_NS_NOT_CONVERGED` | production 금지; 초기 구조·barostat·평형화 길이 재검토 |
| 하나라도 `THREE_NS_FAIL` 또는 3 ns로 연장하지 못한 chain 존재 | `THREE_NS_CROSS_START_INCOMPLETE` | 세 시작 조건이 같은 basin에 수렴했다고 주장하지 않음 |

동일 seed를 사용한 세 초기 밀도 chain은 경로 민감도 비교이지 독립 replica가 아니다. `THREE_NS_SAME_BASIN_CANDIDATE`는 세 시작점의 밀도 평균이 짧은 window에서 모였다는 뜻뿐이다.

## 5. 임시 대표 chain 선정

세 chain 모두 잠정 문턱을 통과하고 spread가 2% 이하일 때만 후속 replica 설계용 임시 대표 chain 하나를 고를 수 있다. 선정 순서는 다음과 같다.

1. hard fail·warning·시간 불연속이 없음
2. 2–3 ns 밀도 slope가 가장 작음
3. 마지막 두 밀도 block 차이와 인접 block 최대 차이가 가장 작음
4. `min(box)/(2×rlist)` 최솟값이 가장 큰 chain
5. 동률이면 중간 시작 밀도에 가까운 chain

이 선정은 계산 효율을 위한 것이며 해당 chain이 “정답 밀도”나 “평형 구조”임을 의미하지 않는다.

## 6. 독립 replica와 production 상태

3 ns 연장을 통과한 뒤에도 다음은 각각 **Not verified / 미검증**다.

- 독립 Packmol 초기 구조와 독립 속도 seed를 사용한 replica 재현성
- 조성별 실험·문헌 목표 밀도
- 0.75 전하 스케일과 force field의 해당 계에 대한 정확도
- 장시간 에너지·구조 평형
- production ensemble·길이·저장 간격·폐기 구간
- RDF·coordination number·확산·전도도의 block·replica 수렴
- 연구실 서버 재현

후속 물리 판정을 위해서는 임시 대표 조건에서 독립 Packmol 배치·속도 seed를 사용한 replica를 최소 3개 준비하고, 각 replica가 동일한 잠정 stationarity 점검을 통과하는지 확인해야 한다. 이 replica 계획과 production 조건은 교수님의 승인 전에 실행 완료로 간주하지 않는다.

## 7. 보고 용어

사용 가능:

- `1 ns SCREEN_EXTEND 후 2 ns 추가 NPT를 수행할 후보`
- `3 ns 마지막 1 ns 잠정 stationarity 통과/미통과`
- `THREE_NS_SAME_BASIN_CANDIDATE`
- `추가 평형화·독립 replica 필요`

사용 금지:

- `3 ns에서 평형을 완료했다`
- `production-ready`
- `물리적으로 검증된 밀도`
- `구조·확산·전도도가 수렴했다`

## 8. 검증 레벨

- **Implemented**: 이 연장 결정 규칙이 문서로 존재한다.
- **Unit-verified**: `scripts/analyze_npt_extension.py`의 0–3 ns 시간 범위, 마지막 1 ns 5×200 ps block, 1–2 ns 대 2–3 ns 비교, source hash, write-once 거부 및 `THREE_NS_*` 판정을 포함한 현재 전체 104개 테스트가 통과했다. 이는 실제 3 ns trajectory 검증을 대신하지 않는다.
- **Physical-device-verified**: 로컬 Mac에서 세 chain을 각각 1 ns checkpoint에서 총 3 ns까지 연장했다. 각 누적 산출물의 0–3000 ps, 3001 frame, 1 ps 간격과 append provenance를 검증하고, 마지막 1 ns QC와 cross-start 비교를 실행했다. 교차 판정은 `THREE_NS_SAME_BASIN_CANDIDATE`, 밀도 spread는 1.256%이다.
- 평형·production·독립 replica: **Not verified / 미검증**.
