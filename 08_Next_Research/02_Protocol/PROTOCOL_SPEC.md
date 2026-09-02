# Protocol v0.2-candidate

## 고정한 것

- 분자 모델과 결합 파라미터: 기존 CL&P 계열 topology 유지
- 전하: 현재 topology의 0.75 스케일 유지
- 비결합 설정: PME, `rcoulomb = 1.2 nm`, `rvdw = 1.2 nm`
- 후보 조성: L1P1과 같은 비율, 분자 수만 2배인 Li 50 / Pyr13 50 / FSI 100

## 이번에 실행하는 것

- Packmol 초기 구조 생성
- strict energy minimization 전처리
- `grompp`에서 `-maxwarn` 사용 금지
- 에너지 최소화 실행 및 로그·box·density 점검

## 아직 실행 조건으로 확정하지 않은 것

- 1,400 kg/m³는 Packmol/EM 기술 시험용 시작 밀도이다. 승인된 물리 목표 밀도가 아니다.
- 0.75 전하 스케일은 기존 조건을 보존한 것이며 이 계에 대해 새로 검증한 값이 아니다.
- NVT/NPT 길이, barostat, production 길이, replica 수는 교수님 결정 및 예비 평형 결과가 필요하다.

## 2026-08-07 초기 밀도 민감도 탐색

사용자의 후속 연구 진행 요청에 따라, 물리 검증이 아닌 탐색용으로 L1P1x2의 초기 밀도 1,000·1,200·1,400 kg/m³를 비교한다.

- 각 후보: strict EM → 동일한 고정 seed(`110001`) NVT 100 ps → C-rescale NPT 1 ns
- 공통 상태점: 298 K, 1 bar
- 세 밀도는 서로 다른 목표 상태가 아니라 같은 상태점으로 출발하는 세 초기 조건이다.
- `02_Protocol/mdp`에 복사·고정한 MDP만 사용한다.
- `compressibility = 4.5e-5 bar⁻¹`는 탐색용 수치 결합 가정이며, 이 전해질에서 측정·검증한 물성값이나 승인된 production 설정이 아니다.
- 결과가 안정적으로 보여도 `EXPLORATORY_ONLY`이며 production에 자동 진입하지 않는다.
- 세 후보의 마지막 500 ps 평균 밀도와 기울기·block 차이를 비교해 연장 여부만 결정한다.

## 다음 단계로 넘어가기 위한 조건

- `grompp` 경고를 `-maxwarn`으로 숨기지 않을 것
- fatal, NaN, LINCS warning이 없을 것
- 최종 최소 박스 길이가 실제 neighbor-list 반경의 2배보다 클 것
- 에너지 최소화가 종료되고 최대 힘과 잠재 에너지가 기록될 것
- 승인 전 NPT는 위 초기 밀도 민감도 탐색에만 한정하며 연구 결과 또는 최종 평형으로 주장하지 않을 것
