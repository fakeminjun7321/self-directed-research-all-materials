#!/bin/zsh
# 5개 시스템 전부 엄밀(1ns) MD를 백그라운드로 실행.
# 진행 상황은 02_Processed_Data/MD_Runs/Rigorous_1ns/_background_status.log 확인.
set -euo pipefail

THREADS="${THREADS:-8}"
ROOT="/Users/minjun/D/연구/2026 연구/2026_자율연구"
PROTOCOL_DIR="$ROOT/02_Processed_Data/MD_Protocols/Rigorous_1ns"
SRC_ROOT="$ROOT/02_Processed_Data/MD_Runs/50ps_Practice"
OUT_ROOT="$ROOT/02_Processed_Data/MD_Runs/Rigorous_1ns"
STATUS="$OUT_ROOT/_background_status.log"

mkdir -p "$OUT_ROOT"
echo "Started: $(date)" > "$STATUS"

LABELS=(L1P1 L1P2 L2P1 L3P1 L1P3)

for LABEL in "${LABELS[@]}"; do
  SRC="$SRC_ROOT/$LABEL"
  RUN="$OUT_ROOT/$LABEL"
  mkdir -p "$RUN"

  cp -f "$SRC/start.pdb" "$RUN/start.pdb"
  cp -f "$SRC/em.gro" "$RUN/previous_em.gro"
  cp -f "$SRC/topol.top" "$RUN/topol.top"
  cp -f "$PROTOCOL_DIR"/mdp/*.mdp "$RUN/"

  cd "$RUN"

  echo "[$LABEL] start: $(date)" >> "$STATUS"

  {
    # 이미 prod_1ns.gro 있으면 건너뜀
    if [[ -f "prod_1ns.gro" ]]; then
      echo "$LABEL already complete, skipping"
      echo "[$LABEL] already complete, skipping" >> "$STATUS"
      continue
    fi

    if [[ ! -f "em.gro" ]]; then
      gmx grompp -f 01_em_strict.mdp -c previous_em.gro -p topol.top -o em.tpr -maxwarn 1
      gmx mdrun -deffnm em -nt "$THREADS"
    fi
    echo "[$LABEL] EM ok: $(date)" >> "$STATUS"

    if [[ ! -f "nvt.gro" ]]; then
      gmx grompp -f 02_nvt_100ps.mdp -c em.gro -p topol.top -o nvt.tpr -maxwarn 1
      gmx mdrun -deffnm nvt -nt "$THREADS"
    fi
    echo "[$LABEL] NVT ok: $(date)" >> "$STATUS"

    if [[ ! -f "npt.gro" ]]; then
      gmx grompp -f 03_npt_500ps.mdp -c nvt.gro -t nvt.cpt -p topol.top -o npt.tpr -maxwarn 1
      gmx mdrun -deffnm npt -nt "$THREADS"
    fi
    echo "[$LABEL] NPT ok: $(date)" >> "$STATUS"

    if [[ ! -f "prod_1ns.gro" ]]; then
      gmx grompp -f 04_prod_1ns.mdp -c npt.gro -t npt.cpt -p topol.top -o prod_1ns.tpr -maxwarn 1
      gmx mdrun -deffnm prod_1ns -nt "$THREADS"
    fi
    echo "[$LABEL] PROD ok: $(date)" >> "$STATUS"

    printf "0\n" | gmx trjconv -s prod_1ns.tpr -f prod_1ns.xtc \
        -o prod_1ns_sampled.pdb -dt 2 -pbc mol
    echo "[$LABEL] trjconv ok: $(date)" >> "$STATUS"

  } 2>&1 | tee -a run_rigorous.log
done

echo "All done: $(date)" >> "$STATUS"
