# CILE MD Google Drive 백업 안내

이 Drive는 보고서 제출과 재현에 필요한 **선별 파일**을 보관한다.

## Drive에 보관

- 교수 전달용 ZIP
- 최종 보고서 HWPX/PDF/Markdown 원본
- 보고서용 그림
- 프로토콜·스크립트·테스트·환경 명세
- QC JSON/CSV/Markdown 보고서
- 전체 workspace 파일의 크기·SHA-256 manifest

## 기본 Drive 백업에서 제외

- XTC/TRR trajectory
- EDR/CPT/TPR 실행·재시작 파일
- animation/sample PDB
- `99_Old_Backup` 중복 아카이브

제외 파일은 손실을 허용한다는 의미가 아니다. Mac 외에 외장 SSD 또는 연구실 서버에 별도 복사해야 하며 `workspace_manifest.csv`의 SHA-256으로 무결성을 확인한다.

## 현재 주의점

- 기존 2026-05-27 보고서와 그림은 50 ps 연습 결과 중심이다.
- 독립 replica 1 ns 결과는 탐색용이며 equilibrium/production 결과가 아니다.
- 0.75 전하 스케일, 목표 밀도, 총 3 ns replica, 물성 수렴과 서버 재현은 미검증이다.

## 복구 순서

1. `CILE_reproducibility_YYYYMMDD.zip`을 푼다.
2. `environment.yml`과 `Brewfile`을 확인한다.
3. `preflight_environment.py`를 실행한다.
4. `workspace_manifest.csv`로 외장 SSD/서버의 대용량 파일 hash를 확인한다.
5. 교수 전달본은 `01_Professor_Handoff`의 SHA-256과 비교한다.
