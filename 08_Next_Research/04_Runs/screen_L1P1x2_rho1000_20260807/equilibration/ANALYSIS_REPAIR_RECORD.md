# 분석 경로 수정 기록

- 최초 계산 구간: 2026-08-07 00:07–00:33 KST
- NVT: 0–100 ps, 101 energy frames, `Finished mdrun`
- NPT: 0–1000 ps, 1001 energy frames, `Finished mdrun`
- 최초 후처리 실패: NVT EDR에 존재하지 않는 Density/Volume/Box 항목까지 다중 선택한 뒤 요청 순서로 열을 해석하려 해 `unexpected nvt thermo column count` 발생
- 실패 원본: `analysis_failure_initial.json`

## 수정

- NVT는 Temperature/Pressure/Potential만 항목별로 추출한다.
- NVT 고정 박스는 최종 GRO 박스 벡터에서 읽는다.
- NPT도 모든 항목을 하나씩 추출해 GROMACS 내부 메뉴 순서에 의존하지 않는다.
- 시간축 일치·단조 증가·finite 값·TPR nsteps×dt·EDR 실제 구간을 검사한다.

## 실제 재검증

- 패치된 `--resume`은 기존 NVT/NPT를 다시 계산하지 않고 완성된 EDR을 재분석했다.
- NVT 101프레임은 독립 GROMACS 추출과 일치했다.
- NPT 1001프레임은 메뉴 순서 다중항목 출력과 새 통합 파일을 전 프레임 대조해 최대 절대차 0을 확인했다.
- 최종 기술 상태: `PASS_COMPLETE`
- 탐색 판정: `SCREEN_EXTEND`
- 물리 상태: `EXPLORATORY_ONLY`; 평형·production은 미검증
