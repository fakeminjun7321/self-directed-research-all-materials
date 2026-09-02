# Claude Max 20 independent review prompt

아래 작업은 LiFSI/Pyr13FSI 조성별 GROMACS 입력 패키지의 독립 검토다.
목표는 계산을 대신 수행하거나 결과를 낙관적으로 해석하는 것이 아니라, 교수님 연구실
서버에 전달하기 전에 과학적·재현성 위험을 찾아내는 것이다.

## 검토 대상

- 공식 조성: L1P1, L1P2, L2P1, L3P1, L1P3
- 패키지 루트: `CILE_MD_Handoff_v0_DRAFT`
- 핵심 파일: `systems/*/initial.gro`, `systems/*/topol.top`, `mdp/*.mdp`,
  `README_FIRST_KOR.md`, `SCOPE_AND_ASSUMPTIONS.md`,
  `SCIENTIFIC_REVIEW_REQUIRED.md`, 실행 스크립트 및 검증표

## 반드시 지킬 제한

1. topology, 좌표, MDP를 직접 수정하지 말 것.
2. 과학 조건을 임의로 확정하지 말고 제안과 근거만 제시할 것.
3. 명령 종료 성공과 물리적 타당성을 구분할 것.
4. 기존 알려진 문제를 숨기지 말 것: 초기 밀도 약 130–140 kg/m3,
   500 ps NPT 부족, L1P1 production box divergence, L3P1 중단, L1P3 미실행.
5. `-maxwarn` 사용을 해결책으로 제안하지 말 것.
6. 실제 실행하지 않은 항목은 `Not verified / 미검증`으로 표시할 것.

## 검토 항목

- 좌표와 topology의 원자 수·분자 수·총전하 일치
- CL&P 계열 force field의 출처와 패키지 내 추적 가능성
- 0.75 전하 스케일링의 적용 일관성과 설명 누락
- 초기 박스 크기와 목표 밀도 결정 근거
- EM → NVT → pre-compression → NPT → production 순서의 적절성
- C-rescale/Berendsen/Parrinello–Rahman 선택과 전환 시점
- thermostat/barostat time constant, cutoff, timestep, seed 정책
- 문서 설명과 실제 MDP 값의 불일치
- Linux/GROMACS 버전 이식성, 상대경로, checkpoint/restart 정책
- 교수님에게 반드시 확인받아야 할 결정

## 출력 형식

1. 한 문장 결론: 지금 production용으로 보낼 수 있는지
2. P0/P1/P2 위험 표: 근거 파일, 영향, 권장 조치
3. 조성별 상태표
4. 교수님 승인 질문 7개 이내
5. 전달 전 acceptance criteria
6. `Implemented / Unit-verified / Physical-device-verified / Not verified` 구분

추측과 확인 사실을 분리하고, 가능하면 GROMACS 공식 문서나 원 논문을 링크하라.
