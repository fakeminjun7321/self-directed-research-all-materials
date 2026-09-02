# 최종 ZIP 후보 clean-extract 기술 검증

## 검증한 범위

패키지를 ZIP 후보로 생성한 뒤 새 임시 폴더에 풀어, 원본 작업 폴더에 의존하지 않는 기술 실행 경로를 확인했습니다. 검증에 사용한 후보 ZIP은 이 문서와 갱신된 `MANIFEST.tsv`, `SHA256SUMS`를 추가하기 전 상태입니다.

## 관찰 결과

| 항목 | 관찰 결과 | 판정 |
|---|---:|---|
| SHA-256 무결성 | 52/52 `OK` | PASS |
| `validate_inputs.sh` 정적 검사 | PASS | PASS |
| 공식 5개 시스템 EM-stage `grompp` | 5/5, TPR 5개 생성 | PASS |
| 20-step EM→NVT→NPT→production 연쇄 | 5/5 | PASS |
| production 최종 GRO | 5개 | PASS |
| 단계별 `Finished mdrun` | 20개 | PASS |
| Fatal/LINCS/NaN 탐지 | 0건 | PASS |
| production XTC `gmx check` | 5/5, return code 0 | PASS |

생성된 TPR, trajectory, checkpoint, energy, raw run log는 인계 패키지에 포함하지 않고 외부 임시 검증 경로에서만 확인했습니다.

## 이 결과가 증명하지 않는 것

- 20-step smoke는 스크립트, 상대경로, GROMACS 단계 연결, 출력 파일 생성만 확인합니다.
- 원래 100 ps/500 ps/1 ns 길이의 full protocol은 **Not verified / 미검증**입니다.
- 목표 밀도, box 안정성, EM 수렴, 온도·압력·에너지 plateau와 production 타당성은 **Not verified / 미검증**입니다.
- Colab/Linux, 별도 M4 Pro, 교수님 연구실 서버 경로는 **Not verified / 미검증**입니다.
- 초기 저밀도와 L1P1 발산 이력은 이 기술 smoke로 해결되지 않았습니다.

## 현재 패키지에 대한 후속 확인

이 문서와 갱신된 manifest/checksum을 포함해 새로 생성한 최종 ZIP에서 같은 clean-extract 검증을 한 번 더 반복해야 합니다. 그 재검증은 이 문서를 추가하기 전 ZIP 후보에서 관찰한 결과와 현재 정확한 파일 집합을 구분하기 위해 필요합니다.
