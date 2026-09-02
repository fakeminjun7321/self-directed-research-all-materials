#!/usr/bin/env bash
# Run a 20-step technical smoke chain for all five systems.
#
# The original MDP files are never edited. Each invocation creates a temporary
# copy, changes only the active nsteps value to 20, and preserves the modified
# copies plus all logs/results under validation/smoke/<label>/<run-id>/.
# This is a technical execution check, not physical or scientific validation.

set -Eeuo pipefail
IFS=$'\n\t'

PACKAGE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SYSTEMS=(L1P1 L1P2 L1P3 L2P1 L3P1)
MDPS=(01_em_strict.mdp 02_nvt_100ps.mdp 03_npt_500ps.mdp 04_prod_1ns.mdp)
THREADS="${THREADS:-1}"
RUN_ID="$(date -u '+%Y%m%dT%H%M%SZ')_$$"
SMOKE_ROOT="${SMOKE_ROOT:-$PACKAGE_DIR/validation/smoke}"
SMOKE_TMP_DIR=""

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

cleanup() {
  if [[ -n "$SMOKE_TMP_DIR" && -d "$SMOKE_TMP_DIR" ]]; then
    rm -rf -- "$SMOKE_TMP_DIR"
  fi
}
trap cleanup EXIT INT TERM

case "$THREADS" in
  ''|*[!0-9]*|0) die "THREADS must be a positive integer (received '$THREADS')." ;;
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

mkdir -p "$SMOKE_ROOT"
SMOKE_ROOT="$(cd -- "$SMOKE_ROOT" && pwd -P)"

case "$(basename -- "$GMX_CMD")" in
  *mpi*) MDRUN_THREAD_ARGS=(-ntomp "$THREADS") ;;
  *) MDRUN_THREAD_ARGS=(-nt "$THREADS") ;;
esac
export OMP_NUM_THREADS="$THREADS"

SMOKE_TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/cile-md-smoke.XXXXXX")"
MDP_TMP_DIR="$SMOKE_TMP_DIR/mdp"
mkdir -p "$MDP_TMP_DIR"

for mdp in "${MDPS[@]}"; do
  source_mdp="$PACKAGE_DIR/mdp/$mdp"
  target_mdp="$MDP_TMP_DIR/$mdp"
  [[ -s "$source_mdp" ]] || die "Missing MDP: $source_mdp"
  cp -- "$source_mdp" "$target_mdp"
  awk '
    BEGIN { changed = 0 }
    {
      if (!changed && $0 ~ /^[[:space:]]*nsteps[[:space:]]*=/) {
        sub(/=.*/, "= 20")
        changed = 1
      }
      print
    }
    END { if (!changed) exit 42 }
  ' "$target_mdp" > "$target_mdp.updated" || die "No active nsteps setting found in $source_mdp"
  mv -- "$target_mdp.updated" "$target_mdp"
done

printf 'TECHNICAL SMOKE ONLY: 20 steps per stage; no claim of physical equilibration.\n'
printf 'Run ID: %s; GROMACS: %s; threads: %s\n' "$RUN_ID" "$GMX_CMD" "$THREADS"

run_stage() {
  local label="$1"
  local stage="$2"
  local mdp="$3"
  local coordinate="$4"
  local checkpoint="${5:-}"
  local system_dir="$PACKAGE_DIR/systems/$label"
  local output_dir="$SMOKE_ROOT/$label/$RUN_ID"
  local grompp_args

  grompp_args=(grompp -f "$MDP_TMP_DIR/$mdp" -c "$coordinate"
               -p "$system_dir/topol.top" -o "$output_dir/$stage.tpr"
               -po "$output_dir/${stage}_mdout.mdp")
  if [[ -n "$checkpoint" ]]; then
    [[ -s "$checkpoint" ]] || die "[$label/$stage] Missing checkpoint: $checkpoint"
    grompp_args+=(-t "$checkpoint")
  fi

  (
    cd -- "$system_dir"
    "$GMX_CMD" "${grompp_args[@]}"
  ) 2>&1 | tee "$output_dir/grompp_${stage}.log"

  "$GMX_CMD" mdrun -s "$output_dir/$stage.tpr" \
    -deffnm "$output_dir/$stage" "${MDRUN_THREAD_ARGS[@]}" \
    2>&1 | tee "$output_dir/mdrun_${stage}.stdout.log"
  [[ -s "$output_dir/$stage.gro" ]] || die "[$label/$stage] Final GRO was not generated."
}

for label in "${SYSTEMS[@]}"; do
  system_dir="$PACKAGE_DIR/systems/$label"
  output_dir="$SMOKE_ROOT/$label/$RUN_ID"
  [[ -s "$system_dir/initial.gro" ]] || die "Missing coordinate: $system_dir/initial.gro"
  [[ -s "$system_dir/topol.top" ]] || die "Missing topology: $system_dir/topol.top"
  mkdir -p "$output_dir/mdp_20steps"
  cp -- "$MDP_TMP_DIR"/*.mdp "$output_dir/mdp_20steps/"

  {
    printf '[%s] Technical smoke started (UTC): %s\n' "$label" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    run_stage "$label" em 01_em_strict.mdp "$system_dir/initial.gro"
    run_stage "$label" nvt 02_nvt_100ps.mdp "$output_dir/em.gro"
    run_stage "$label" npt 03_npt_500ps.mdp "$output_dir/nvt.gro" "$output_dir/nvt.cpt"
    run_stage "$label" prod_1ns 04_prod_1ns.mdp "$output_dir/npt.gro" "$output_dir/npt.cpt"
    printf '[%s] Technical smoke finished (UTC): %s\n' "$label" "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  } 2>&1 | tee "$output_dir/smoke_chain.log"
done

printf '%s\n' \
  'All 20-step chains finished.' \
  'Verification scope: technical command/format smoke only. Density, box stability, equilibration, production validity, and research-server behavior remain Not verified / 미검증.'
