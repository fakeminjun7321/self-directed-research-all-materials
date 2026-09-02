#!/usr/bin/env bash
# Static, non-MD validation of the portable handoff package.

set -Eeuo pipefail
IFS=$'\n\t'

PACKAGE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SYSTEMS=(L1P1 L1P2 L1P3 L2P1 L3P1)
MDPS=(01_em_strict.mdp 02_nvt_100ps.mdp 03_npt_500ps.mdp 04_prod_1ns.mdp)
errors=0
SCAN_FILES=(
  "$PACKAGE_DIR"/run_*.sh
  "$PACKAGE_DIR/validate_grompp.sh"
  "$PACKAGE_DIR"/mdp/*.mdp
  "$PACKAGE_DIR"/systems/*/*.top
)

pass() {
  printf 'PASS: %s\n' "$*"
}

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  errors=$((errors + 1))
}

check_nonempty() {
  if [[ -s "$1" ]]; then
    pass "Non-empty file: ${1#$PACKAGE_DIR/}"
  else
    fail "Missing or empty file: ${1#$PACKAGE_DIR/}"
  fi
}

check_gro() {
  local file="$1"
  local natoms
  local records
  local expected
  local box_line

  [[ -s "$file" ]] || return 0
  natoms="$(sed -n '2p' "$file" | tr -d '[:space:]')"
  case "$natoms" in
    ''|*[!0-9]*) fail "Invalid atom-count line in ${file#$PACKAGE_DIR/}"; return 0 ;;
  esac
  records="$(awk 'END { print NR }' "$file")"
  expected=$((natoms + 3))
  if [[ "$records" -lt "$expected" ]]; then
    fail "Truncated GRO file ${file#$PACKAGE_DIR/}: expected at least $expected records, found $records"
    return 0
  fi
  box_line="$(sed -n "${expected}p" "$file")"
  if awk '
    BEGIN { ok = 1 }
    {
      if (NF != 3 && NF != 9) ok = 0
      for (i = 1; i <= NF; i++) {
        if ($i !~ /^[-+]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][-+]?[0-9]+)?$/) ok = 0
      }
    }
    END { exit(ok ? 0 : 1) }
  ' <<< "$box_line"; then
    pass "GRO atom count and box line: ${file#$PACKAGE_DIR/} ($natoms atoms)"
  else
    fail "Invalid GRO box line in ${file#$PACKAGE_DIR/}"
  fi
}

check_topology() {
  local file="$1"
  [[ -s "$file" ]] || return 0
  if grep -Eq '^[[:space:]]*\[[[:space:]]*system[[:space:]]*\]' "$file"; then
    pass "Topology has [ system ]: ${file#$PACKAGE_DIR/}"
  else
    fail "Topology lacks [ system ]: ${file#$PACKAGE_DIR/}"
  fi
  if grep -Eq '^[[:space:]]*\[[[:space:]]*molecules[[:space:]]*\]' "$file"; then
    pass "Topology has [ molecules ]: ${file#$PACKAGE_DIR/}"
  else
    fail "Topology lacks [ molecules ]: ${file#$PACKAGE_DIR/}"
  fi
}

for script in run_local.sh run_one.sh run_slurm_template.sh validate_inputs.sh validate_grompp.sh run_smoke_all.sh; do
  check_nonempty "$PACKAGE_DIR/$script"
done
check_nonempty "$PACKAGE_DIR/validation/verification_matrix.csv"

for mdp in "${MDPS[@]}"; do
  check_nonempty "$PACKAGE_DIR/mdp/$mdp"
done

for system in "${SYSTEMS[@]}"; do
  gro="$PACKAGE_DIR/systems/$system/initial.gro"
  topology="$PACKAGE_DIR/systems/$system/topol.top"
  check_nonempty "$gro"
  check_nonempty "$topology"
  check_gro "$gro"
  check_topology "$topology"
done

if grep -En '(^|[[:space:]])-maxwarn([[:space:]]|$)' "${SCAN_FILES[@]}" >/dev/null 2>&1; then
  fail "Forbidden -maxwarn option found in package scripts/inputs."
else
  pass "No -maxwarn option in package scripts/inputs."
fi

if grep -En '(/Users/|/home/[^/]+/)' "${SCAN_FILES[@]}" >/dev/null 2>&1; then
  fail "Host-specific absolute path found in package scripts/inputs."
else
  pass "No obvious host-specific absolute paths in package scripts/inputs."
fi

if [[ "$errors" -ne 0 ]]; then
  printf 'Static validation FAILED with %s issue(s). No MD was run.\n' "$errors" >&2
  exit 1
fi

printf 'Static validation PASSED. This proves file-level checks only; no grompp or MD user path was run.\n'
