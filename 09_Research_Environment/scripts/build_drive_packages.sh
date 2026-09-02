#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
project_root="$(cd "$script_dir/../.." && pwd)"
snapshot_date="${CILE_BACKUP_DATE:-$(date '+%Y%m%d')}"
backup_root="$project_root/09_Research_Environment/backups"
output_dir="$backup_root/$snapshot_date"

if [ -e "$output_dir" ]; then
  echo "refusing to overwrite existing backup directory: $output_dir" >&2
  exit 2
fi

mkdir -p "$backup_root"
temporary_dir="$(mktemp -d "$backup_root/.build.${snapshot_date}.XXXXXX")"
cleanup_temporary_dir() {
  case "$temporary_dir" in
    "$backup_root"/.build."$snapshot_date".*)
      rm -r -- "$temporary_dir"
      ;;
    *)
      echo "refusing unsafe temporary cleanup target: $temporary_dir" >&2
      ;;
  esac
}
trap cleanup_temporary_dir EXIT

bash "$script_dir/capture_environment.sh"
/opt/anaconda3/bin/python "$script_dir/generate_workspace_manifest.py"

cd "$project_root"

zip -qry "$temporary_dir/CILE_reproducibility_${snapshot_date}.zip" \
  .gitignore environment.yml Brewfile README.md \
  08_Next_Research/README_FIRST_KOR.md \
  08_Next_Research/OVERNIGHT_RESEARCH_SUMMARY_20260807.md \
  08_Next_Research/02_Protocol \
  08_Next_Research/03_Environments \
  08_Next_Research/05_QC \
  08_Next_Research/06_Reproducibility \
  08_Next_Research/scripts \
  08_Next_Research/tests \
  09_Research_Environment/README_FIRST_KOR.md \
  09_Research_Environment/DRIVE_README.md \
  09_Research_Environment/backup_policy.json \
  09_Research_Environment/drive_folder_map.json \
  09_Research_Environment/scripts \
  09_Research_Environment/tests \
  09_Research_Environment/manifests \
  -x '*/__pycache__/*' '*.pyc' '*.DS_Store'

zip -qry "$temporary_dir/CILE_report_working_${snapshot_date}.zip" \
  05_Report 04_Figures_For_Report \
  -x '*.DS_Store'

zip -qry "$temporary_dir/CILE_selected_results_${snapshot_date}.zip" \
  08_Next_Research/05_QC \
  08_Next_Research/04_Runs/chain_registry.csv \
  08_Next_Research/03_Environments/environment_registry.csv \
  05_Report/2026_Final/RESULTS_TABLE.csv \
  05_Report/2026_Final/FIGURE_MANIFEST.csv \
  09_Research_Environment/manifests/workspace_manifest.csv \
  09_Research_Environment/manifests/workspace_manifest_summary.json \
  -x '*.DS_Store'

for archive in "$temporary_dir"/*.zip; do
  if unzip -Z1 "$archive" | grep -Eiq '(^|/)(\.env($|\.)|[^/]*\.pem$|[^/]*\.key$|[^/]*credentials[^/]*\.json$|[^/]*service-account[^/]*\.json$)'; then
    echo "secret-like archive member detected: $archive" >&2
    exit 3
  fi
done

cp "$project_root/09_Research_Environment/manifests/workspace_manifest.csv" "$temporary_dir/"
cp "$project_root/09_Research_Environment/manifests/workspace_manifest_summary.json" "$temporary_dir/"
cp "$project_root/09_Research_Environment/DRIVE_README.md" "$temporary_dir/"

(
  cd "$temporary_dir"
  shasum -a 256 *.zip workspace_manifest.csv workspace_manifest_summary.json DRIVE_README.md \
    > SHA256SUMS
)

mv "$temporary_dir" "$output_dir"
trap - EXIT

echo "DRIVE_PACKAGES_BUILT $output_dir"
ls -lh "$output_dir"
