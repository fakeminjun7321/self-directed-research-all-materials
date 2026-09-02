#!/usr/bin/env bash
#SBATCH --job-name=cile-md
#SBATCH --array=0-4
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --time=08:00:00
#SBATCH --mem=8G
#SBATCH --output=slurm-%A_%a.out
#SBATCH --error=slurm-%A_%a.err

# Site-neutral Slurm template. Before submission, edit partition/account/time/
# memory directives to match the research server, and load its GROMACS module.
# Submit all systems with: sbatch run_slurm_template.sh

set -Eeuo pipefail
IFS=$'\n\t'

PACKAGE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SYSTEMS=(L1P1 L1P2 L1P3 L2P1 L3P1)

: "${SLURM_ARRAY_TASK_ID:?Submit this file with sbatch as an array job (expected index 0-4).}"
case "$SLURM_ARRAY_TASK_ID" in
  0|1|2|3|4) ;;
  *) printf 'ERROR: SLURM_ARRAY_TASK_ID must be 0-4, received %s.\n' "$SLURM_ARRAY_TASK_ID" >&2; exit 1 ;;
esac

# Adapt this section to the server. Examples (leave only the applicable one):
# module purge
# module load gromacs
# source /path/to/gromacs/bin/GMXRC

GMX_CMD="${GMX_CMD:-gmx_mpi}"
THREADS="${THREADS:-${SLURM_CPUS_PER_TASK:-8}}"
USE_SRUN=1
export GMX_CMD THREADS USE_SRUN

LABEL="${SYSTEMS[$SLURM_ARRAY_TASK_ID]}"
printf 'Slurm job %s array task %s -> %s\n' \
  "${SLURM_JOB_ID:-unknown}" "$SLURM_ARRAY_TASK_ID" "$LABEL"

"$PACKAGE_DIR/run_one.sh" "$LABEL"

