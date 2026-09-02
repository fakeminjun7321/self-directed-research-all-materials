# 검증 한계와 보고서 표현 규칙

## Not verified / 미검증

- 열역학적 평형
- production readiness
- 0.75 전하 스케일의 물리 정확도
- 조성별 승인 목표 밀도
- 독립 R1·R2·R3 총 3 ns 결과
- RDF·coordination number의 장시간 수렴
- diffusion coefficient·전도도의 장시간 수렴
- 연구실 Linux 서버 재현
- CPU die 온도

## 보고서에서 사용하지 않을 표현

- “평형에 도달했다”
- “실제 밀도를 재현했다”
- “확산계수를 정확히 계산했다”
- “전도도가 향상됐다”
- “force field가 검증됐다”

위 문장은 해당 실제 검증이 추가되기 전에는 사용하지 않는다.

## 허용되는 표현

- “탐색적 1 ns NPT를 기술적으로 완료했다.”
- “마지막 500 ps 평균 밀도의 replica 간 spread는 0.1846%였다.”
- “세 replica 모두 사전 규칙에서 `SCREEN_EXTEND`로 판정됐다.”
- “결과는 동일 길이 연장 필요성을 지지하지만 평형을 입증하지 않는다.”

## 기존 50 ps 자료

2026-05-27에 만든 RDF·MSD·diffusion 그림은 분석 workflow 구현 증거다. 정량적인 최종 물성 비교나 실험 일치의 증거로 사용하지 않는다.
