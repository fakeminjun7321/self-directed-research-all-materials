# GROMACS Water Starter

이 폴더는 노트북에서 바로 돌릴 수 있는 작은 GROMACS MD 예제입니다.

## 내용

1. SPCE 물 박스 생성
2. 에너지 최소화
3. 10 ps NVT 분자 동역학 실행

## 이미 실행된 결과 파일

- `waterbox.gro`: 초기 물 박스
- `em.gro`: 에너지 최소화 후 구조
- `nvt.gro`: 10 ps MD 후 구조
- `nvt.xtc`: 압축 trajectory
- `nvt.edr`: 에너지/온도 등 결과
- `nvt.log`: 실행 로그

## 다시 실행하고 싶을 때

```bash
gmx solvate -cs spc216.gro -box 2.5 2.5 2.5 -o waterbox.gro -p topol.top
gmx grompp -f minim.mdp -c waterbox.gro -p topol.top -o em.tpr -maxwarn 1
gmx mdrun -deffnm em -nt 8
gmx grompp -f nvt.mdp -c em.gro -p topol.top -o nvt.tpr -maxwarn 1
gmx mdrun -deffnm nvt -nt 8
```

다음 단계로는 단백질 PDB 파일을 넣고 `pdb2gmx -> box -> solvate -> ion -> minimization -> NVT -> NPT -> production MD` 흐름으로 확장하면 됩니다.
