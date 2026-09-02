# 개인 Mac 기술 스모크 요약

- 실행 시각: 2026-08-06T13:53:59Z
- 환경: Apple M5, 24 GB, macOS, GROMACS 2026.3-Homebrew, mixed precision, CPU only
- 입력 변경: 패키지 원본 MDP는 변경하지 않음. 임시 복사본의 활성 `nsteps`만 20으로 제한
- 범위: EM → NVT → NPT → production 명령·파일 형식·단계 연결 확인
- 금지 옵션: `-maxwarn` 미사용

| 시스템 | 4단계 종료 | 최종 GRO/CPT/EDR/LOG | production XTC 읽기 | Fatal/LINCS/NaN | 판정 |
|---|---:|---:|---:|---:|---|
| L1P1 | 4/4 | 확인 | `gmx check` 확인 | 0 | 기술 smoke PASS |
| L1P2 | 4/4 | 확인 | `gmx check` 확인 | 0 | 기술 smoke PASS |
| L2P1 | 4/4 | 확인 | `gmx check` 확인 | 0 | 기술 smoke PASS |
| L3P1 | 4/4 | 확인 | `gmx check` 확인 | 0 | 기술 smoke PASS |
| L1P3 | 4/4 | 확인 | `gmx check` 확인 | 0 | 기술 smoke PASS |

## 제한과 정확한 미검증 항목

- 20-step으로 제한했기 때문에 EM은 5개 모두 `Fmax < 500 kJ mol^-1 nm^-1`에 수렴하지 않았습니다.
- 원래 100 ps/500 ps/1 ns 길이의 실행은 하지 않았습니다.
- 밀도, box 안정성, 온도·압력·에너지 plateau와 production 타당성은 **Not verified / 미검증**입니다.
- M4 Pro, Colab/Linux, 교수님 연구실 서버 실행은 **Not verified / 미검증**입니다.

원시 로그와 생성 파일은 전달 패키지의 용량을 줄이기 위해 포함하지 않았으며, 로컬 검증 증거 폴더에 별도 보존했습니다.
