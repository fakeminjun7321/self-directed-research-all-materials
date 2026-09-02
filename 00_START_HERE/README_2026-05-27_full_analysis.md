# 2026-05-27 — 5개 시스템 전체 분석 정리

교수님이 손글씨로 지정해주신 5개 조성 **L1P1, L1P2, L2P1, L3P1, L1P3**
에 대해 50 ps NVT MD trajectory(298 K)를 기반으로 가능한 분석을 묶어서 끝냈다.

## ⭐ 한 장으로 보기

- `05_Report/comprehensive_report_2026-05-27.pdf` — 모든 분석을 묶은 보고서 PDF
- `04_Figures_For_Report/Comprehensive/structure_property_dashboard.png` — 한 장 dashboard
- `04_Figures_For_Report/Comprehensive/equilibration_check.png` — 평형 점검

## 보고서 그림 (04_Figures_For_Report/Comprehensive/)

| 파일 | 내용 |
|---|---|
| `five_systems_rdf_grid.png` | 5×2 RDF (Li-O, Li-N) per system + CN |
| `composition_series_overlay.png` | L=1 라인, P=1 라인 비교 |
| `coordination_number_summary_bar.png` | 5개 시스템 1차 CN 막대 |
| `cn_distribution_histograms.png` | Li 주변 O/N 개수 분포 |
| `speciation_stacked_bar.png` | Free/CIP/AGG-I/AGG-II 누적 |
| `extended_rdf_overview.png` | Li-N4, Li-Li, NBT-NBT, N4-NBT |
| `equilibration_check.png` | E/T/P 시계열 점검 |
| `nernst_einstein_conductivity.png` | NE 전도도·t_Li |
| `structure_property_dashboard.png` | 모든 결과 한 장 dashboard |

## 분석 원자료 (03_Analysis_Results/)

| 폴더 | 내용 |
|---|---|
| `RDF_CN/` | Li-O, Li-N RDF + CN (5개 + 보너스 2개) |
| `Extended_RDF/` | Li-N4, Li-Li, NBT-NBT, N4-NBT (5개) |
| `Speciation/` | Free/CIP/AGG-I/AGG-II 비율 (5개) |
| `CN_Distribution/` | Li당 1차 shell n=0,1,2,... 히스토그램 |
| `Equilibration_Check/` | gmx energy E/T/P 시계열 + 요약 |
| `Conductivity/` | Nernst-Einstein σ, c_Li, t_Li |
| `General_Analysis/` | (기존) MSD, diffusion, energy |
| `VMD_View/` | 5개 합쳐 보는 VMD 애니메이션 |

## 핵심 결과 요약

### 1차 배위수 (50 ps 평균)

| 시스템 | Li-O(FSI) CN | Li-N(FSI) CN | AGG-II 비율 | t_Li (NE) |
|---|---:|---:|---:|---:|
| L1P1 | 4.30 ± 1.20 | 3.24 ± 1.02 | 78.0% | 0.38 |
| L1P2 | 4.48 ± 1.21 | 3.15 ± 1.05 | 74.4% | 0.22 |
| L1P3 | 4.43 ± 1.24 | 3.17 ± 1.05 | 73.4% | 0.11 |
| L2P1 | 4.27 ± 1.12 | 3.52 ± 1.06 | 81.7% | 0.46 |
| L3P1 | 4.22 ± 1.12 | 3.49 ± 1.12 | 79.3% | 0.44 |

### 트렌드
- **Li 비율 ↑ (L2P1, L3P1)**: AGG-II 강화, t_Li 증가(0.44–0.46), Li-O CN 미세 감소
- **Pyr 비율 ↑ (L1P2, L1P3)**: AGG-II 약화, t_Li 감소(0.11–0.22), 확산 빨라짐
- Free Li⁺는 모든 조성에서 2% 미만 → 자유 양이온이 거의 없는 농축 IL 영역

## 진행 중

엄밀(EM → 100 ps NVT → 500 ps NPT → 1 ns production) MD를
5개 시스템에 대해 백그라운드로 실행 중. 진행 상황:
`02_Processed_Data/MD_Runs/Rigorous_1ns/_background_status.log`

1 ns 결과가 모두 끝나면 같은 분석 스크립트를 그쪽 trajectory에 돌리면 더 정확한 수치가 나온다.

## 재생성 (전체)

```bash
cd "2026_자율연구"
# (선택) 엄밀 MD 다시 돌리기:  90_Reproduce_Scripts/run_rigorous_all_background.sh
python3 90_Reproduce_Scripts/extended_rdf_analysis.py
python3 90_Reproduce_Scripts/speciation_analysis.py
python3 90_Reproduce_Scripts/cn_distribution_analysis.py
python3 90_Reproduce_Scripts/check_equilibration.py
python3 90_Reproduce_Scripts/conductivity_estimate.py
python3 90_Reproduce_Scripts/make_comprehensive_figures.py
python3 90_Reproduce_Scripts/make_comprehensive_report_pdf.py
```

## 주의

- 50 ps는 짧음 → 확산/전도도 절대값은 신뢰 X (트렌드만 의미있음)
- 1 ns 결과 들어오면 같은 스크립트를 새 trajectory로 다시 돌리면 됨
- `L2P2`, `L3P2`는 교수님 슬라이드 예시 비교용 보너스(공식 5개에 포함 X)
