# L1P1x2 초기 밀도 민감도 탐색 보고서

## 결과 요약

- 교차 초기조건 판정: `SAME_BASIN_CANDIDATE`
- 마지막 500 ps 평균 밀도의 체인 간 spread: 1.515%
- 후속 검토 우선 체인: `pilot_L1P1x2_rho1400_v6`
- 물리 상태: `EXPLORATORY_ONLY`

| chain | 초기 밀도 (kg/m³) | 마지막 500 ps 밀도 (kg/m³) | 밀도 slope (%/ns) | 마지막 두 block 차이 (%) | min box/(2rlist) | screen verdict | hard fail |
|---|---:|---:|---:|---:|---:|---|---|
| screen_L1P1x2_rho1000_20260807 | 1000.0 | 1491.87 | 2.474 | 0.638 | 1.2488 | SCREEN_EXTEND | 없음 |
| screen_L1P1x2_rho1200_clean_20260807 | 1200.0 | 1501.68 | 0.527 | 0.484 | 1.2486 | SCREEN_EXTEND | 없음 |
| pilot_L1P1x2_rho1400_v6 | 1400.0 | 1514.63 | 0.275 | 0.166 | 1.2450 | SCREEN_EXTEND | 없음 |

## 검증 수준

- **Implemented**: 동일 조성의 세 초기 밀도 후보, 고정 seed NVT 100 ps, C-rescale NPT 1 ns, 자동 QC와 교차 비교가 기록되었다.
- **Unit-verified**: 열 매핑·시간축·TPR 길이·비교 가능성·screen 수식의 집중 테스트를 통과했다.
- **Physical-device-verified**: 각 표에 포함된 체인은 이 Mac에서 실제 GROMACS 경로가 끝나고 EDR 시간 범위·로그·에너지 열을 확인한 경우에만 포함된다.
- **Not verified / 미검증**: 연구실 서버 재현, 교수님 승인 프로토콜, 장시간 평형, 독립 packing/seed replica, force-field 및 0.75 전하 스케일의 물리 타당성, production·RDF·확산·전도도.

`SCREEN_STATIONARITY_PASS`와 `SAME_BASIN_CANDIDATE`는 1 ns 탐색 window의 임시 기준일 뿐 평형 또는 production 준비를 뜻하지 않는다. `best_exploratory_chain`도 연구 결과의 우수성을 뜻하지 않고 다음 연장·반복 검토의 우선순위다.
