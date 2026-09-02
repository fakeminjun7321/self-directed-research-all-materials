# 분석 결과 요약

이 폴더는 50 ps 연습용 trajectory에서 만든 자동 분석 결과입니다.
강의에서 요구한 RDF, coordination number, MSD/diffusion, 온도/압력 확인 그래프를 모아 두었습니다.

주의: 강의자료에는 production MD가 50 ns 수준으로 제시되어 있습니다. 현재 결과는 50 ps라서 값 자체를 논문식 결론으로 쓰기보다는, 분석 방법을 연습하고 보고서 예시 그림으로 쓰는 용도입니다.

## 핵심 파일

- `summary.csv`: 조성별 숫자 요약
- `overall_diffusion_coefficients.png`: Li, Pyr13, FSI diffusion estimate 비교
- `overall_li_obt_coordination.png`: Li-O(FSI) coordination number 비교
- `overall_temperature_check.png`: 온도 안정성 확인

## 조성별 폴더

각 조성 폴더에는 다음 그림이 있습니다.

- `*_energy_temperature_pressure.png`: potential energy, temperature, pressure
- `*_rdf_li_obt.png`: Li와 FSI 산소(OBT)의 RDF 및 coordination
- `*_msd_comparison.png`: Li, Pyr13, FSI MSD 비교

## 조성별 숫자 요약

| label | T avg (K) | CN Li-O | D Li (m2/s) | D Pyr13 (m2/s) | D FSI (m2/s) |
|---|---:|---:|---:|---:|---:|
| L1P1 | 298.99 | 4.30 | 4.489e-08 | 2.402e-08 | 2.459e-08 |
| L1P2 | 299.94 | 4.48 | 5.204e-08 | 3.391e-08 | 3.940e-08 |
| L2P1 | 300.40 | 4.18 | 2.643e-08 | 1.497e-08 | 1.533e-08 |
| L3P1 | 301.80 | 4.12 | 2.153e-08 | 1.369e-08 | 1.682e-08 |
| L1P3 | 298.76 | 4.43 | 4.590e-08 | 5.870e-08 | 4.911e-08 |
