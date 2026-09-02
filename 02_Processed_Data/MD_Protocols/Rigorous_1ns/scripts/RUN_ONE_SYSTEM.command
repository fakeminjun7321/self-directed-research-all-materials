#!/bin/zsh
set -euo pipefail

THREADS="${THREADS:-8}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROTOCOL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROCESSED_ROOT="$(cd "$PROTOCOL_DIR/../.." && pwd)"
SOURCE_ROOT="$PROCESSED_ROOT/MD_Runs/50ps_Practice"
OUT_ROOT="$PROCESSED_ROOT/MD_Runs/Rigorous_1ns"

echo "Available systems: L1P1 L1P2 L2P1 L3P1 L1P3"
printf "System label to run: "
read LABEL

case "$LABEL" in
  L1P1|L1P2|L2P1|L3P1|L1P3) ;;
  *)
    echo "ERROR: unknown label: $LABEL"
    exit 1
    ;;
esac

if ! command -v gmx >/dev/null 2>&1; then
  echo "ERROR: gmx command was not found. Install or load GROMACS first."
  exit 1
fi

SRC="$SOURCE_ROOT/$LABEL"
RUN="$OUT_ROOT/$LABEL"
mkdir -p "$RUN"

cp "$SRC/start.pdb" "$RUN/start.pdb"
cp "$SRC/em.gro" "$RUN/previous_em.gro"
cp "$SRC/topol.top" "$RUN/topol.top"
cp "$PROTOCOL_DIR"/mdp/*.mdp "$RUN/"

cd "$RUN"

{
  echo "Rigorous MD run for $LABEL"
  echo "Start: $(date)"
  echo "Threads: $THREADS"
  echo

  echo "$ gmx grompp -f 01_em_strict.mdp -c previous_em.gro -p topol.top -o em.tpr -maxwarn 1"
  gmx grompp -f 01_em_strict.mdp -c previous_em.gro -p topol.top -o em.tpr -maxwarn 1
  echo "$ gmx mdrun -deffnm em -nt $THREADS"
  gmx mdrun -deffnm em -nt "$THREADS"

  echo "$ gmx grompp -f 02_nvt_100ps.mdp -c em.gro -p topol.top -o nvt.tpr -maxwarn 1"
  gmx grompp -f 02_nvt_100ps.mdp -c em.gro -p topol.top -o nvt.tpr -maxwarn 1
  echo "$ gmx mdrun -deffnm nvt -nt $THREADS"
  gmx mdrun -deffnm nvt -nt "$THREADS"

  echo "$ gmx grompp -f 03_npt_500ps.mdp -c nvt.gro -t nvt.cpt -p topol.top -o npt.tpr -maxwarn 1"
  gmx grompp -f 03_npt_500ps.mdp -c nvt.gro -t nvt.cpt -p topol.top -o npt.tpr -maxwarn 1
  echo "$ gmx mdrun -deffnm npt -nt $THREADS"
  gmx mdrun -deffnm npt -nt "$THREADS"

  echo "$ gmx grompp -f 04_prod_1ns.mdp -c npt.gro -t npt.cpt -p topol.top -o prod_1ns.tpr -maxwarn 1"
  gmx grompp -f 04_prod_1ns.mdp -c npt.gro -t npt.cpt -p topol.top -o prod_1ns.tpr -maxwarn 1
  echo "$ gmx mdrun -deffnm prod_1ns -nt $THREADS"
  gmx mdrun -deffnm prod_1ns -nt "$THREADS"

  echo "$ gmx trjconv -s prod_1ns.tpr -f prod_1ns.xtc -o prod_1ns_sampled.pdb -dt 2 -pbc mol"
  printf "0\n" | gmx trjconv -s prod_1ns.tpr -f prod_1ns.xtc -o prod_1ns_sampled.pdb -dt 2 -pbc mol

  echo
  echo "Finish: $(date)"
} 2>&1 | tee run_rigorous.log

echo
echo "Done. Output folder:"
echo "$RUN"
echo "Press Enter to close."
read
