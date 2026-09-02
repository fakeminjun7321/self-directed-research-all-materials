# 후속 연구 QC 요약

실행 결과가 생성되면 다음을 분리해 기록한다.

- **Implemented**: 입력·스크립트 존재
- **Unit-verified**: 계산 및 정적 검증 통과
- **Physical-device-verified**: 이 Mac에서 실제 GROMACS 경로를 실행한 범위
- **Not verified / 미검증**: 평형·물리 타당성·장시간 통계·연구실 서버

## 현재 QC 기준의 성격

`05_QC/qc_criteria.csv`가 현재 `scripts/run_equilibration.py`의 `SCREEN_*` 분기와 대응하는 QC 기준표다. 표의 모든 기준은 **PROVISIONAL / EXPLORATORY**이며, 교수님이 승인한 평형·production 프로토콜이 아니다.

`02_Protocol/qc_criteria.csv`는 초기 EM·입력 검증에서 사용한 이전 제안표다. 현재 NVT/NPT runner의 `SCREEN_*` 판정을 해석할 때는 `05_QC/qc_criteria.csv`를 우선한다.

### 분석 window

- NVT: 마지막 50 ps, 10 ps 블록 5개
- NPT: 마지막 500 ps, 100 ps 블록 5개
- 밀도 slope: NPT 100 ps 블록 평균 5개에 대한 선형 기울기를 평균 밀도로 나눈 %/ns
- block 차이: `|a-b| / ((|a|+|b|)/2) × 100`의 대칭 백분율 차이
- box 여유: 각 단계의 모든 frame에서 `min(Box-X, Box-Y, Box-Z) / (2 × rlist)`의 최솟값

### runner verdict의 정확한 의미

| verdict | runner 조건 | 해석 |
|---|---|---|
| `SCREEN_FAIL` | NVT/NPT box 비율 ≤ 1.0, NVT/NPT 평균온도가 293–303 K 밖, 또는 인접 에너지 frame 부피 변화 >5% 중 하나 이상 | 현재 경로를 연장·production에 사용하지 않고 원인 점검 |
| `SCREEN_EXTEND` | hard fail은 없지만 임시 stationarity 문턱 중 하나 이상 미충족 | 평형 인증이 아니며 추가 NPT 후 재판정 후보 |
| `SCREEN_STATIONARITY_PASS` | hard fail 없음; NVT/NPT box 비율 ≥1.10; 밀도 slope ≤1%/ns; 마지막 두 밀도 block 차이 ≤1%; 인접 block 최대 차이 ≤2%; NVT 온도 slope ≤2 K/ns; NVT 마지막 두 10 ps block 차이 ≤3 K; NPT 온도 slope ≤2 K/ns | **1 ns 탐색 window에서 임시 문턱을 통과했다는 뜻뿐**. 평형·물리·production 검증이 아님 |

runner는 verdict와 무관하게 `physics_status = EXPLORATORY_ONLY`, `equilibrium_validated = false`, `production_ready = false`를 기록한다. 세 초기 밀도 run의 마지막 500 ps 평균 밀도가 2% 이내로 모여 `SAME_BASIN_CANDIDATE`가 되어도 같은 제한이 적용된다.

### verdict에 직접 쓰지 않는 관측량

현재 runner는 다음을 저장하지만 `SCREEN_*` verdict에는 직접 사용하지 않는다.

- 마지막 500 ps의 첫 250 ps–뒤 250 ps 밀도 차이
- 마지막 500 ps 부피·압력·potential energy 통계
- 100 ps 압력 block 평균

이 값들이 그럴듯해 보이는 것은 평형의 증거가 아니다. 압력 신뢰구간·자기상관, 에너지 정상성, 장시간 구조 수렴은 후속 프로토콜에서 별도로 승인·검증해야 한다.

## 1 ns 탐색의 해석 한계

- NVT의 밀도는 고정되므로 평형 밀도를 검증하지 않는다.
- NPT 1 ns의 마지막 500 ps 평탄성은 느린 이온 재배열·구조 상관·유리화 가능성을 배제하지 못한다.
- 세 초기 밀도는 독립 replica를 뜻하지 않는다.
- 목표 밀도, 0.75 전하 스케일, barostat·compressibility, production 길이는 아직 과학적으로 승인되지 않았다.
- 따라서 1 ns 결과는 초기 밀도 민감도와 추가 평형화 필요성만 판정한다. RDF·CN·확산·전도도를 연구 결과로 제시하면 안 된다.

## 대표 실행 결과

`pilot_L1P1x2_rho1400_v6`를 로컬 Mac에서 실제 실행했다.

- **Implemented**: 독립 후보 생성·계산·검증 스크립트 존재
- **Unit-verified**: Python compile, 조성 계산, 입력 checksum 6/6, topology/좌표 검사 12/12 통과
- **Physical-device-verified**: Packmol, PDB→GRO 변환, strict `grompp`, EM, TPR dump, TRR check 종료코드 0
- strict `grompp` warning 0
- EM 874 step 수렴, 최대 힘 440.67331 kJ mol⁻¹ nm⁻¹
- Fatal / NaN / LINCS warning 0 / 0 / 0
- 실제 EM `rlist = 1.26 nm`, `min(box)/(2 × rlist) = 1.224484`

초기 `gmx editconf`가 PDB의 CONECT record를 무시한다는 경고 1건은 있다. 이 경고는 좌표 변환 단계에서 발생하며 strict `grompp` warning은 0이다.

**Not verified / 미검증**:

- NVT/NPT와 298 K 밀도 plateau
- 목표 밀도의 과학적 승인
- 0.75 전하 스케일의 이 계에 대한 검증
- production 길이와 replica 수
- 구조·수송 물성의 수렴
- 연구실 서버 재현

앞선 세 시도는 각각 fftool 출력 형식, 원자명 불일치, 잘못된 `gmx check` 옵션을 드러냈으며 삭제하지 않고 실패 기록으로 보존했다.
