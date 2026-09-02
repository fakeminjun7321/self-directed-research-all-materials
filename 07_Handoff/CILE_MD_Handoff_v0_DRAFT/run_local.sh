#!/usr/bin/env bash
# Run all five systems, or only the labels passed as arguments.
#
# Examples:
#   ./run_local.sh
#   THREADS=6 MAX_PARALLEL=2 ./run_local.sh L1P1 L1P2

set -Eeuo pipefail
IFS=$'\n\t'

PACKAGE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
THREADS="${THREADS:-1}"
MAX_PARALLEL="${MAX_PARALLEL:-1}"

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

is_positive_integer "$THREADS" || die "THREADS must be a positive integer (received '$THREADS')."
is_positive_integer "$MAX_PARALLEL" || die "MAX_PARALLEL must be a positive integer (received '$MAX_PARALLEL')."

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
export GMX_CMD THREADS

if [[ "$#" -gt 0 ]]; then
  LABELS=("$@")
else
  LABELS=(L1P1 L1P2 L1P3 L2P1 L3P1)
fi

for label in "${LABELS[@]}"; do
  case "$label" in
    L1P1|L1P2|L1P3|L2P1|L3P1) ;;
    *) die "Unknown system '$label'. Expected one of: L1P1 L1P2 L1P3 L2P1 L3P1" ;;
  esac
done

"$PACKAGE_DIR/validate_inputs.sh"

printf 'Running %s system(s) with THREADS=%s and MAX_PARALLEL=%s.\n' \
  "${#LABELS[@]}" "$THREADS" "$MAX_PARALLEL"
if (( THREADS * MAX_PARALLEL > 1 )); then
  printf 'Planned maximum CPU threads: %s\n' "$((THREADS * MAX_PARALLEL))"
fi

pids=()
pid_labels=()
failed=0

wait_for_batch() {
  local index
  for ((index = 0; index < ${#pids[@]}; index++)); do
    if wait "${pids[$index]}"; then
      printf '[%s] Finished successfully.\n' "${pid_labels[$index]}"
    else
      printf '[%s] FAILED. See runs/%s/run_%s.log.\n' \
        "${pid_labels[$index]}" "${pid_labels[$index]}" "${pid_labels[$index]}" >&2
      failed=1
    fi
  done
  pids=()
  pid_labels=()
}

for label in "${LABELS[@]}"; do
  "$PACKAGE_DIR/run_one.sh" "$label" &
  pids+=("$!")
  pid_labels+=("$label")
  if (( ${#pids[@]} >= MAX_PARALLEL )); then
    wait_for_batch
  fi
done

if (( ${#pids[@]} > 0 )); then
  wait_for_batch
fi

if [[ "$failed" -ne 0 ]]; then
  die "One or more systems failed. Successful systems were not deleted and can be resumed."
fi

printf 'All requested systems finished. Inspect the observable outputs and QC evidence under: %s/runs\n' "$PACKAGE_DIR"

