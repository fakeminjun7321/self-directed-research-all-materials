# 2026 자율연구 폴더 안내

이 폴더는 보고서/발표 준비를 기준으로 다시 정리한 작업 공간입니다.

## 2026-05-27 업데이트

교수님 미팅(2026-05-27) 슬라이드 "Simulation Summary"(L1P2, L2P2, L3P2 비교)에 맞춰
**L2P2와 L3P2 시스템을 새로 추가**했습니다. 변경 내역과 결과 요약은
`00_START_HERE/README_P2_series_2026-05-27.md`에 있습니다.

핵심 그림: `04_Figures_For_Report/RDF_CN/presentation_slide_simulation_summary.png`

## 가장 먼저 볼 곳

- `04_Figures_For_Report/`: 보고서에 바로 넣기 좋은 그림 복사본
- `05_Report/`: HWPX 보고서, 요약 PDF, 보고서 메모
- `03_Analysis_Results/RDF_CN/`: RDF와 coordination number 원본 xvg, CSV, README
- `02_Processed_Data/MD_Runs/`: 10 ps, 50 ps, 엄밀 MD 실행 결과

## 전체 구조

- `00_START_HERE/`: 이 안내문과 바로 실행용 command
- `01_Raw_Data/`: 강의자료, 원본 MD 자료, Packmol 초기 구조
- `02_Processed_Data/`: GROMACS 실행 결과, MDP 설정, 엄밀 MD 프로토콜
- `03_Analysis_Results/`: 분석 원자료, CSV, 상세 그래프
- `04_Figures_For_Report/`: 보고서/발표에 쓸 최종 그림 모음
- `05_Report/`: 보고서 파일과 요약 PDF
- `06_Presentation/`: 발표자료를 만들 때 둘 곳
- `90_Reproduce_Scripts/`: 결과를 다시 만들 때 쓰는 스크립트
- `99_Old_Backup/`: 예전 백업, 압축 파일, 정리 로그

## 자주 쓰는 파일

- VMD 50 ps 애니메이션 실행: `00_START_HERE/OPEN_VMD_50ps_animation.command`
  - 실제 애니메이션 PDB/TCL의 기준 위치: `03_Analysis_Results/VMD_View/`
  - VMD 앱의 기준 위치: `/Applications/VMD*.app` (연구 폴더 안에 앱 복사본을 두지 않음)
- L1P2 RDF/CN 그림: `04_Figures_For_Report/RDF_CN/per_system/L1P2_li_o_n_coordination_slide.png`
- RDF/CN 요약표: `03_Analysis_Results/RDF_CN/coordination_number_li_o_n_summary.csv`
- 엄밀 MD 실행: `02_Processed_Data/MD_Protocols/Rigorous_1ns/scripts/RUN_ONE_SYSTEM.command`

## 기준

원본 데이터는 `01_Raw_Data`에 두고, 계산으로 만들어진 결과는 `02_Processed_Data`와 `03_Analysis_Results`에 둡니다. 보고서에 바로 넣을 그림만 `04_Figures_For_Report`에 따로 모았습니다.
