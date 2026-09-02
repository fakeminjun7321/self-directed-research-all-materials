# M4 Pro Codex execution prompt

당신은 교수님께 전달할 GROMACS 입력 패키지를 실제 개인 PC에서 검증하는 실행 담당자다.
압축을 푼 패키지 밖의 원본 연구 폴더는 수정하지 말고, 모든 출력은 새 임시 작업 폴더와
패키지의 `validation/local_m4pro/` 아래에만 저장하라.

## 시작 전에 기록할 것

- 작업 시작 시각과 패키지 SHA-256
- macOS 버전, Apple chip 이름, 물리/논리 코어 수, 메모리 용량
- `gmx --version` 전체 내용 중 버전, precision, MPI, OpenMP, GPU support
- 실제 사용한 `GMX_CMD`, thread 수, 동시 job 수
- serial number, hardware UUID, 사용자 계정명 등 개인정보는 기록하지 말 것

## 절대 제한

1. `systems/*/initial.gro`, `topol.top`, `mdp/*.mdp`를 수정하지 말 것.
2. `-maxwarn`을 사용하지 말 것.
3. 실패를 우회하거나 경고를 숨기지 말 것.
4. production용 과학 조건을 임의로 바꾸지 말 것.
5. 짧은 smoke용 MDP가 필요하면 원본을 복사해 임시 폴더에서만 `nsteps`를 줄일 것.
6. 다른 앱과 계산이 충돌하지 않도록 절전 방지 후 최대 2개 job만 병렬 실행할 것.

## 검증 순서

1. ZIP을 새로운 빈 폴더에 풀고 `SHA256SUMS`를 검증한다.
2. `bash validate_inputs.sh`를 실행한다.
3. 공식 5개 조성 모두 EM 단계 `grompp`를 `-maxwarn` 없이 수행한다.
4. 공식 5개 조성 모두 임시 20-step EM/NVT/NPT/production 연쇄 smoke를 수행한다.
5. 각 단계에서 exit code, `Finished mdrun`, fatal error, LINCS warning, NaN/Inf,
   생성된 GRO/CPT/EDR/LOG를 확인한다.
6. `gmx check`로 trajectory가 실제 생성되고 읽히는지 확인한다.
7. full protocol은 `DRAFT / NOT FOR PRODUCTION` 경고와 과학 조건 승인 여부를 확인한 뒤에만
   실행한다. 승인되지 않았다면 실행하지 말고 `Blocked / 과학 조건 미승인`으로 기록한다.
8. 검증 결과를 `validation/verification_matrix.csv`와
   `validation/local_m4pro/REPORT.md`에 기록한다.

## 합격 판정

- Technical smoke PASS: 모든 조성에서 연쇄 실행과 파일 읽기가 성공하고 fatal/LINCS/NaN 없음.
- Physical validity PASS: full-length 결과의 온도·밀도·박스·에너지 plateau가 사전 기준을
  만족할 때만 가능하다. 짧은 smoke로는 절대 PASS 처리하지 말 것.
- 연구실 서버 검증은 항상 `Not verified / 미검증`으로 남긴다.

끝나면 변경 파일, 실행 명령, 조성별 상태, 정확한 미검증 항목을 요약하라.
