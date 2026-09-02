# 보고서/발표용 메모

## 현재 준비된 산출물

- 다섯 조성 초기 구조: `03_Analysis_Results/VMD_View/02_all_five_initial_structure.pdb`
- 다섯 조성 50 ps 애니메이션: `03_Analysis_Results/VMD_View/01_all_five_50ps_animation.pdb`
- 보고서용 RDF/CN 그림: `04_Figures_For_Report/RDF_CN/`
- MSD 및 diffusion estimate: `03_Analysis_Results/General_Analysis/*/*_msd_comparison.png`
- 전체 비교 그래프: `04_Figures_For_Report/Overview/`
- 숫자 요약: `03_Analysis_Results/General_Analysis/summary.csv`
- RDF/CN 요약: `03_Analysis_Results/RDF_CN/coordination_number_li_o_n_summary.csv`
- 3쪽 요약 PDF: `05_Report/Report_Materials/CILE_practice_analysis_summary.pdf`

## 보고서에 넣기 좋은 문장

본 연구에서는 LiFSI/Pyr13FSI 계열 ionic liquid electrolyte의 조성 변화에 따른 구조 및 이동 특성을 GROMACS 기반 MD 시뮬레이션으로 예비 분석하였다. Packmol로 초기 구조를 구성하고, energy minimization 이후 50 ps의 짧은 연습용 MD trajectory를 생성하였다. 이후 Li와 FSI 산소 원자 사이의 radial distribution function(RDF), coordination number, mean square displacement(MSD), diffusion coefficient estimate를 계산하였다.

현재 trajectory 길이는 50 ps이므로 diffusion coefficient와 RDF는 최종 정량 결론이 아니라 분석 workflow 검증 및 예비 결과로 해석해야 한다. 강의자료 기준의 production MD는 ns 단위 이상, 특히 50 ns 수준이 권장된다.

## 그림 캡션 예시

Figure 1. VMD visualization of five LiFSI/Pyr13FSI electrolyte compositions after short MD simulation.

Figure 2. Li-O(FSI) radial distribution function and cumulative coordination number for each composition.

Figure 3. Mean square displacement comparison of Li, Pyr13, and FSI species from 50 ps practice trajectories.

Figure 4. Estimated diffusion coefficients obtained from linear fitting of MSD between 10 ps and 45 ps.

## 발표할 때 조심할 점

- 50 ps는 매우 짧기 때문에 diffusion 값의 절대값보다 조성별 경향과 분석 방법을 보여주는 데 초점을 둔다.
- 현재 결과는 NVT 기반 짧은 연습 trajectory이므로, 실제 연구 결론에는 NPT equilibration과 더 긴 production MD가 필요하다.
- Coordination number는 Li-O(FSI) RDF의 첫 번째 minimum 근처에서 계산한 예비값이다.
