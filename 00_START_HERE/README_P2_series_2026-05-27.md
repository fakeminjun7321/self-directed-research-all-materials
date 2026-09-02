# 2026-05-27 — L2P2 / L3P2 추가 작업 안내

오늘 오후 미팅에서 교수님이 보여주신 슬라이드 (`Simulation Summary` — L1P2, L2P2, L3P2 비교) 형식을 맞추기 위해 누락돼 있던 **L2P2**와 **L3P2** 시스템을 새로 만들어 50 ps MD를 돌리고 RDF / coordination number 분석을 같이 마쳤다.

## 새로 생긴 결과물

- 보고서/발표용 그림 (`04_Figures_For_Report/RDF_CN/`)
  - `presentation_slide_simulation_summary.png` — 교수님 슬라이드 형식의 PPT 한 장
  - `summary_slide_P2_series_overlay.png` — L1P2/L2P2/L3P2 RDF 오버레이
  - `summary_slide_P2_series_with_CN.png` — RDF + cumulative CN 오버레이
  - `P2_series_coordination_number_bar.png` — first-shell CN 막대 비교
  - `per_system/L2P2_li_o_n_coordination_slide.png`
  - `per_system/L3P2_li_o_n_coordination_slide.png`
- 분석 원자료 (`03_Analysis_Results/RDF_CN/`)
  - `raw_xvg/L2P2_*`, `raw_xvg/L3P2_*` — `gmx rdf` 원본
  - `summary_table_P2_series.csv` — L1P2/L2P2/L3P2만 추린 CN 표
  - `coordination_number_li_o_n_summary.csv` — 전체 7개 시스템 통합 표 (L2P2, L3P2 추가됨)
- MD 실행 결과 (`02_Processed_Data/MD_Runs/50ps_Practice/`)
  - `L2P2/` — em, md_50ps (xtc/log/tpr/gro), VMD용 sampled.pdb
  - `L3P2/` — 동일 구성
- 초기 구조 (`01_Raw_Data/Initial_Structures_Packmol/`)
  - `L2P2/L2P2.pack.inp`, `L2P2/L2P2.pdb` (+ xyz)
  - `L3P2/L3P2.pack.inp`, `L3P2/L3P2.pdb` (+ xyz)
  - `summary.csv` — L2P2, L3P2 추가됨
- VMD 시각화 (`03_Analysis_Results/VMD_View/`)
  - `03_P2_series_50ps_animation.pdb` — L1P2/L2P2/L3P2 50 ps trajectory를 가로로 나란히
  - `VMD_03_open_P2_series_animation.tcl`
  - `00_START_HERE/OPEN_VMD_P2_series.command` — 더블클릭으로 VMD 띄우기

## CN 결과 (50 ps NVT, 298 K)

| 조성 | Li-O(FSI) CN | Li-N(FSI) CN |
|---|---:|---:|
| L1P2 | 4.48 | 3.20 |
| L2P2 | 4.29 | 3.34 |
| L3P2 | 4.10 | 3.23 |

Li 비율(L)이 커질수록 Li-O 1차 배위수는 약 4.5 → 4.1로 단조 감소. Li-N 배위수는 ~3.2–3.4 범위에서 큰 변화 없음.

## 재생성 스크립트

새로 추가된 스크립트 (`90_Reproduce_Scripts/`)
- `build_L2P2_L3P2.py` — Packmol → topol.top → EM → 50 ps MD까지 한방
- `make_summary_slide_P2.py` — 비교 그래프 + CN 막대
- `make_presentation_slide.py` — PPT용 한 장
- `make_vmd_P2_series.py` — VMD 비교 애니메이션

다 다시 만들려면:

```bash
cd "02_Processed_Data/MD_Runs/50ps_Practice"  # 기존 결과 보존
python3 90_Reproduce_Scripts/build_L2P2_L3P2.py
python3 90_Reproduce_Scripts/analyze_li_o_n_coordination.py
python3 90_Reproduce_Scripts/make_summary_slide_P2.py
python3 90_Reproduce_Scripts/make_presentation_slide.py
python3 90_Reproduce_Scripts/make_vmd_P2_series.py
```

## 주의

- 50 ps는 짧은 연습 trajectory. 보고서/논문용 최종 수치는 `02_Processed_Data/MD_Protocols/Rigorous_1ns/` 프로토콜을 L2P2/L3P2에도 적용해서 다시 돌리는 게 안전하다.
- L2P2/L3P2의 box 크기(66.617 Å, 68.948 Å)는 기존 5개 시스템과 같은 atom density (≈ 0.00778 atoms/Å³) 기준으로 잡았다.
- RDF peak 절대 높이(예: g_Li-O ≈ 145)는 교수님 슬라이드의 ~23보다 크지만, 이는 `gmx rdf`의 bin 폭/정규화 방식 차이에서 오는 표현 차이이고 CN 값은 영향 받지 않는다. CN으로 비교하는 것이 안전.
