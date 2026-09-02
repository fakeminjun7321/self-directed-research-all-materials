#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SYSTEMS=(L1P1 L1P2 L2P1 L3P1 L1P3)
MDPS=(01_em_strict.mdp 02_nvt_100ps.mdp 03_npt_500ps.mdp 04_prod_1ns.mdp)
errors=0

check_file() {
  if [[ -s "$1" ]]; then
    printf 'OK  %s\n' "${1#$ROOT/}"
  else
    printf 'MISSING  %s\n' "${1#$ROOT/}" >&2
    errors=$((errors + 1))
  fi
}

for mdp in "${MDPS[@]}"; do
  check_file "$ROOT/mdp/$mdp"
done

for system in "${SYSTEMS[@]}"; do
  gro="$ROOT/systems/$system/initial.gro"
  top="$ROOT/systems/$system/topol.top"
  check_file "$gro"
  check_file "$top"

  if [[ -s "$gro" ]]; then
    natoms="$(sed -n '2p' "$gro" | tr -d '[:space:]')"
    lines="$(awk 'END { print NR }' "$gro")"
    if [[ "$natoms" =~ ^[0-9]+$ ]] && (( lines >= natoms + 3 )); then
      printf 'OK  %s atoms in %s\n' "$natoms" "$system"
    else
      printf 'INVALID  systems/%s/initial.gro\n' "$system" >&2
      errors=$((errors + 1))
    fi
  fi
done

for script in run_one.sh run_local.sh run_slurm_template.sh run_smoke_all.sh validate_grompp.sh; do
  check_file "$ROOT/$script"
done

if (( errors > 0 )); then
  printf 'Input check failed: %s problem(s).\n' "$errors" >&2
  exit 1
fi

printf 'Input check passed for all five systems.\n'
