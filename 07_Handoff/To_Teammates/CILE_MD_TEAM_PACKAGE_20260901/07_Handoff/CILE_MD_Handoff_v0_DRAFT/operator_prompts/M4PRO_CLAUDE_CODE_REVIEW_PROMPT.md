# M4 Pro Claude Code review prompt

이 폴더는 교수님 연구실 서버에 보낼 GROMACS 입력 패키지다. Codex 실행 담당자가 만든
검증 로그와 패키지를 독립적으로 감사하라. 새 MD를 실행하거나 원본 입력을 수정하지 말고,
읽기 전용 검토와 보고서 작성만 수행하라.

## 확인 대상

- `README_FIRST_KOR.md`, `SCOPE_AND_ASSUMPTIONS.md`,
  `SCIENTIFIC_REVIEW_REQUIRED.md`
- `systems/*/initial.gro`, `systems/*/topol.top`, `mdp/*.mdp`
- 모든 `run_*.sh`, `validate_inputs.sh`
- `validation/verification_matrix.csv`, `validation/local_m4pro/*`
- `SHA256SUMS`, manifest

## 핵심 질문

1. 패키지를 새 경로에 풀어도 절대경로 없이 실행 가능한가?
2. 공식 5개 조성이 모두 들어 있고 좌표/topology/조성 정보가 일치하는가?
3. 실행 로그가 실제 명령과 산출물을 증명하는가?
4. 기술적 smoke 성공을 물리적 타당성으로 과장한 문장이 있는가?
5. 초기 저밀도, L1P1 divergence, 미완료 조성이 빠짐없이 공개됐는가?
6. 교수님 서버 환경에서 재생성 가능한 원본 입력이 모두 있는가?
7. 개인정보, Mac 절대경로, 대용량 trajectory, stale 결과가 섞였는가?

## 출력

`validation/local_m4pro/CLAUDE_AUDIT.md`에 다음을 작성하라.

- 결론: SEND / SEND AS DRAFT / DO NOT SEND 중 하나
- P0/P1/P2 발견 사항
- 검증 수준별 상태
- 교수님께 보낼 때 반드시 포함할 경고 문구
- 수정이 필요한 정확한 파일과 줄

실행하지 않은 항목은 반드시 `Not verified / 미검증`으로 표시하라.
