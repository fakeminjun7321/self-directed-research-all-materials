#!/usr/bin/env bash
# Preprocess the EM input for all five systems. This does not run mdrun.

set -Eeuo pipefail
IFS=$'\n\t'

PACKAGE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SYSTEMS=(L1P1 L1P2 L1P3 L2P1 L3P1)
OUTPUT_ROOT="${GROMPP_VALIDATION_DIR:-$PACKAGE_DIR/validation/grompp}"
errors=0

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

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

[[ -s "$PACKAGE_DIR/mdp/01_em_strict.mdp" ]] || die "Missing EM MDP: $PACKAGE_DIR/mdp/01_em_strict.mdp"
mkdir -p "$OUTPUT_ROOT"
OUTPUT_ROOT="$(cd -- "$OUTPUT_ROOT" && pwd -P)"

printf 'GROMACS preprocessing validation only; no MD will be run.\n'
printf 'Command: %s\n' "$GMX_CMD"
"$GMX_CMD" --version > "$OUTPUT_ROOT/gromacs_version.txt" 2>&1 || true

for label in "${SYSTEMS[@]}"; do
  system_dir="$PACKAGE_DIR/systems/$label"
  output_dir="$OUTPUT_ROOT/$label"
  log="$output_dir/grompp_em.log"
  mkdir -p "$output_dir"

  if [[ ! -s "$system_dir/initial.gro" || ! -s "$system_dir/topol.top" ]]; then
    printf '[%s] FAIL: initial.gro or topol.top is missing.\n' "$label" >&2
    errors=$((errors + 1))
    continue
  fi

  printf '[%s] Running EM-stage grompp without -maxwarn.\n' "$label"
  if (
    cd -- "$system_dir"
    "$GMX_CMD" grompp \
      -f "$PACKAGE_DIR/mdp/01_em_strict.mdp" \
      -c initial.gro \
      -p topol.top \
      -o "$output_dir/em.tpr" \
      -po "$output_dir/em_mdout.mdp"
  ) 2>&1 | tee "$log"; then
    printf '[%s] PASS: TPR generated at %s\n' "$label" "$output_dir/em.tpr"
  else
    printf '[%s] FAIL: inspect %s\n' "$label" "$log" >&2
    errors=$((errors + 1))
  fi
done

if [[ "$errors" -ne 0 ]]; then
  printf 'grompp validation FAILED for %s system(s). No mdrun was performed.\n' "$errors" >&2
  exit 1
fi

printf '%s\n' \
  'grompp validation PASSED for all five systems.' \
  'Verification scope: preprocessing only. No integration trajectory, physical stability, density QC, or research-server execution was verified.'
