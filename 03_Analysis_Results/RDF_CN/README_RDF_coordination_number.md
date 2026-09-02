# RDF와 Coordination Number 결과

이 폴더는 50 ps MD trajectory에서 계산한 `Li-O(FSI)` 및 `Li-N(FSI)` RDF와 coordination number 결과입니다.
교수님 슬라이드 형태에 맞춰 RDF 곡선과 누적 coordination number를 함께 표시했습니다.

## 분석 기준

- Reference: Li 이온
- Selection 1: FSI 음이온의 산소 원자 `OBT`
- Selection 2: FSI 음이온의 질소 원자 `NBT`
- Coordination number: RDF peak 이후 첫 번째 shell minimum까지 누적한 값
- 현재 trajectory 길이: `50 ps`

주의: 50 ps는 연습용 짧은 trajectory입니다. 정량적인 최종 결론을 위해서는 더 긴 production MD 결과로 다시 계산하는 것이 안전합니다.

## Coordination Number 요약

| 조성 | Li-O peak r (nm) | Li-O min r (nm) | Li-O CN | Li-N peak r (nm) | Li-N min r (nm) | Li-N CN |
|---|---:|---:|---:|---:|---:|---:|
| L1P1 | 0.22 | 0.33 | 4.30 | 0.38 | 0.55 | 3.24 |
| L1P2 | 0.23 | 0.33 | 4.48 | 0.37 | 0.57 | 3.20 |
| L2P1 | 0.22 | 0.32 | 4.18 | 0.38 | 0.56 | 3.56 |
| L3P1 | 0.22 | 0.32 | 4.12 | 0.38 | 0.57 | 3.56 |
| L1P3 | 0.23 | 0.33 | 4.43 | 0.37 | 0.58 | 3.22 |
| L2P2 | 0.22 | 0.33 | 4.29 | 0.37 | 0.56 | 3.34 |
| L3P2 | 0.22 | 0.32 | 4.10 | 0.37 | 0.55 | 3.23 |

## 파일 설명

- `../../04_Figures_For_Report/RDF_CN/per_system/*_li_o_n_coordination_slide.png`: 교수님 슬라이드와 비슷한 2-panel RDF/CN 그래프
- `../../04_Figures_For_Report/RDF_CN/combined_li_o_n_coordination_number.png`: 조성별 Li-O(FSI), Li-N(FSI) coordination number 비교
- `raw_xvg/`: GROMACS `gmx rdf`에서 나온 원본 RDF/CN 데이터
- `coordination_number_li_o_n_summary.csv`: 보고서 표에 넣기 쉬운 요약 CSV

## 보고서에 쓸 수 있는 문장

Li 이온 주변의 국소 배위 구조를 확인하기 위해 FSI 음이온의 산소 원자(OBT)와 질소 원자(NBT)를 대상으로 RDF 및 coordination number를 계산하였다. Li-O(FSI)는 약 0.22 nm 부근에서 뚜렷한 첫 번째 peak가 나타났고, Li-N(FSI)는 더 긴 거리 영역에서 첫 번째 배위 shell이 관찰되었다. 각 RDF의 첫 번째 shell minimum까지 적분한 coordination number를 비교함으로써 조성 변화에 따른 Li 주변 FSI 배위 환경을 정량적으로 확인할 수 있다.
