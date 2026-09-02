#!/usr/bin/env bash
# Run one CILE composition through EM -> NVT -> NPT -> production MD.
#
# Usage:
#   ./run_one.sh L1P1
#   GMX_CMD=gmx THREADS=8 ./run_one.sh L1P1
#
# This script is intentionally non-interactive. Completed stages (identified by
# their final .gro file) are skipped, and an interrupted stage with a checkpoint
# is resumed with -cpi/-append.

set -Eeuo pipefail
IFS=$'\n\t'

PACKAGE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
MDP_DIR="${MDP_DIR:-$PACKAGE_DIR/mdp}"
SYSTEMS_DIR="$PACKAGE_DIR/systems"
RUNS_DIR="${RUNS_DIR:-$PACKAGE_DIR/runs}"
THREADS="${THREADS:-1}"
USE_SRUN="${USE_SRUN:-0}"

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

is_positive_integer() {
  case "$1" in
    ''|*[!0-9]*|0) return 1 ;;
    *) return 0 ;;
  esac
}

[[ "$#" -eq 1 ]] || die "Usage: $0 SYSTEM (example: $0 L1P1)"
LABEL="$1"

case "$LABEL" in
  L1P1|L1P2|L1P3|L2P1|L3P1) ;;
  *) die "Unknown system '$LABEL'. Expected one of: L1P1 L1P2 L1P3 L2P1 L3P1" ;;
esac

is_positive_integer "$THREADS" || die "THREADS must be a positive integer (received '$THREADS')."
case "$USE_SRUN" in
  0|1) ;;
  *) die "USE_SRUN must be 0 or 1 (received '$USE_SRUN')." ;;
esac

if [[ -z "${GMX_CMD:-}" ]]; then
  if command -v gmx >/dev/null 2>&1; then
    GMX_CMD="gmx"
  elif command -v gmx_mpi >/dev/null 2>&1; then
    GMX_CMD="gmx_mpi"
  else
    die "GROMACS was not found. Load/install it or set GMX_CMD to gmx or gmx_mpi."
  fi
fi
command -v "$GMX_CMD" >/dev/null 2>&1 || die "GMX_CMD '$GMX_CMD' was not found in PATH."
if [[ "$USE_SRUN" == "1" ]]; then
  command -v srun >/dev/null 2>&1 || die "USE_SRUN=1 but srun was not found in PATH."
fi

SYSTEM_DIR="$SYSTEMS_DIR/$LABEL"
RUN_DIR="$RUNS_DIR/$LABEL"
INITIAL="$SYSTEM_DIR/initial.gro"
TOPOLOGY="$SYSTEM_DIR/topol.top"

[[ -s "$INITIAL" ]] || die "Missing or empty coordinate file: $INITIAL"
[[ -s "$TOPOLOGY" ]] || die "Missing or empty topology: $TOPOLOGY"
for mdp in 01_em_strict.mdp 02_nvt_100ps.mdp 03_npt_500ps.mdp 04_prod_1ns.mdp; do
  [[ -s "$MDP_DIR/$mdp" ]] || die "Missing or empty MDP file: $MDP_DIR/$mdp"
done

mkdir -p "$RUN_DIR"
RUN_LOG="$RUN_DIR/run_${LABEL}.log"
exec > >(tee -a "$RUN_LOG") 2>&1

printf '=== CILE MD run: %s ===\n' "$LABEL"
printf 'Started (UTC): %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
printf 'Package: %s\n' "$PACKAGE_DIR"
printf 'GROMACS command: %s\n' "$GMX_CMD"
printf 'Threads: %s\n' "$THREADS"
printf 'Output: %s\n' "$RUN_DIR"

# Use total-thread control for a thread-MPI binary and OpenMP-thread control for
# an external-MPI binary. The Slurm template launches exactly one MPI task.
case "$(basename -- "$GMX_CMD")" in
  *mpi*) MDRUN_THREAD_ARGS=(-ntomp "$THREADS") ;;
  *) MDRUN_THREAD_ARGS=(-nt "$THREADS") ;;
esac
export OMP_NUM_THREADS="$THREADS"

run_grompp() {
  local stage="$1"
  local mdp="$2"
  local coordinate="$3"
  local checkpoint="${4:-}"
  local tpr="$RUN_DIR/$stage.tpr"
  local log="$RUN_DIR/grompp_${stage}.log"
  local args

  [[ -s "$coordinate" ]] || die "Cannot prepare $stage; coordinate file is missing: $coordinate"
  if [[ -n "$checkpoint" ]]; then
    [[ -s "$checkpoint" ]] || die "Cannot prepare $stage; checkpoint is missing: $checkpoint"
  fi

  if [[ -s "$tpr" ]]; then
    printf '[%s] Existing TPR found; skipping grompp: %s\n' "$stage" "$tpr"
    return 0
  fi

  args=(grompp -f "$MDP_DIR/$mdp" -c "$coordinate" -p "$TOPOLOGY"
        -o "$tpr" -po "$RUN_DIR/${stage}_mdout.mdp")
  if [[ -n "$checkpoint" ]]; then
    args+=(-t "$checkpoint")
  fi

  printf '[%s] Preparing portable run input (no -maxwarn).\n' "$stage"
  # Run from the system directory so any relative #include directives in the
  # topology resolve next to topol.top.
  (
    cd -- "$SYSTEM_DIR"
    "$GMX_CMD" "${args[@]}"
  ) 2>&1 | tee "$log"
}

run_mdrun() {
  local stage="$1"
  local final_gro="$RUN_DIR/$stage.gro"
  local checkpoint="$RUN_DIR/$stage.cpt"
  local args

  if [[ -s "$final_gro" ]]; then
    printf '[%s] Final structure exists; stage is already complete: %s\n' "$stage" "$final_gro"
    return 0
  fi
  [[ -s "$RUN_DIR/$stage.tpr" ]] || die "Cannot run $stage; TPR is missing: $RUN_DIR/$stage.tpr"

  args=(mdrun -s "$RUN_DIR/$stage.tpr" -deffnm "$RUN_DIR/$stage"
        "${MDRUN_THREAD_ARGS[@]}")
  if [[ -s "$checkpoint" ]]; then
    args+=(-cpi "$checkpoint" -append)
    printf '[%s] Resuming from checkpoint: %s\n' "$stage" "$checkpoint"
  else
    printf '[%s] Starting stage.\n' "$stage"
  fi

  if [[ "$USE_SRUN" == "1" ]]; then
    srun --ntasks=1 --cpus-per-task="$THREADS" "$GMX_CMD" "${args[@]}"
  else
    "$GMX_CMD" "${args[@]}"
  fi
}

run_grompp em 01_em_strict.mdp "$INITIAL"
run_mdrun em

run_grompp nvt 02_nvt_100ps.mdp "$RUN_DIR/em.gro"
run_mdrun nvt

run_grompp npt 03_npt_500ps.mdp "$RUN_DIR/nvt.gro" "$RUN_DIR/nvt.cpt"
run_mdrun npt

run_grompp prod_1ns 04_prod_1ns.mdp "$RUN_DIR/npt.gro" "$RUN_DIR/npt.cpt"
run_mdrun prod_1ns

printf 'Finished (UTC): %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
printf 'Observable final structure: %s\n' "$RUN_DIR/prod_1ns.gro"
