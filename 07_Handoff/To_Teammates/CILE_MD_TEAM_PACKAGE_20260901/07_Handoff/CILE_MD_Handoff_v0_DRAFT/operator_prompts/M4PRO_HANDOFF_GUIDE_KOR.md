# M4 Pro에서 하는 방법

## 1. 파일 옮기기

최종 생성된 `CILE_MD_Handoff_v0_DRAFT.zip`을 AirDrop 또는 외장 저장장치로 M4 Pro에
옮깁니다. 원래 연구 폴더 전체를 복사할 필요는 없습니다.

## 2. Codex에 맡기기

1. ZIP을 새 빈 폴더에 풉니다.
2. Codex에서 압축을 푼 `CILE_MD_Handoff_v0_DRAFT` 폴더를 workspace로 엽니다.
3. `operator_prompts/M4PRO_CODEX_EXECUTION_PROMPT.md` 전체를 첫 요청으로 붙여 넣습니다.
4. Codex가 원본 MDP/topology 변경이나 `-maxwarn` 사용을 제안하면 승인하지 않습니다.
5. 결과는 `validation/local_m4pro/`에만 저장하게 합니다.

M4 Pro가 12-core이면 `THREADS=5`, 14-core이면 `THREADS=6`으로 두 개 job까지 병렬
실행할 수 있습니다. full protocol은 과학 조건 승인이 끝난 뒤에만 실행합니다.

## 3. Claude Code에 재검토 맡기기

Codex의 기술 검증이 끝난 뒤 같은 폴더에서 Claude Code를 열고
`operator_prompts/M4PRO_CLAUDE_CODE_REVIEW_PROMPT.md` 전체를 붙여 넣습니다.
Claude Code는 새 MD를 실행하지 않고 Codex 로그와 패키지만 독립 검토합니다.

## 4. 결과 되가져오기

다음 파일을 현재 작업 Mac으로 다시 가져옵니다.

- `validation/verification_matrix.csv`
- `validation/local_m4pro/REPORT.md`
- `validation/local_m4pro/CLAUDE_AUDIT.md`
- `validation/local_m4pro/` 아래 GROMACS 로그

이 자료가 있어야 `Physical-device-verified` 범위를 정확히 기록할 수 있습니다.

## 주의

- 짧은 20-step smoke 성공은 물리적 평형화 증거가 아닙니다.
- Mac과 Linux/Colab trajectory가 bitwise 동일할 필요는 없습니다.
- 연구실 서버 실행은 교수님 확인 전까지 항상 `Not verified / 미검증`입니다.
