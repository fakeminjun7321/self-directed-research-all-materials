#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
project_root="$(cd "$script_dir/../.." && pwd)"
manifest_dir="$project_root/09_Research_Environment/manifests"
mkdir -p "$manifest_dir"

software_tmp="$(mktemp "$manifest_dir/software_versions.XXXXXX")"
packages_tmp="$(mktemp "$manifest_dir/python_packages.XXXXXX")"
trap 'rm -f "$software_tmp" "$packages_tmp"' EXIT

{
  echo "captured_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo "architecture=$(uname -m)"
  echo "macos=$(sw_vers -productVersion)"
  echo "gromacs_path=$(command -v gmx || true)"
  gmx --version 2>/dev/null | sed -n '1,12p'
  echo
  echo "packmol_path=$(command -v packmol || true)"
  brew list --versions packmol 2>/dev/null || true
  echo "python_path=/opt/anaconda3/bin/python"
  /opt/anaconda3/bin/python --version
  echo "pandoc_path=$(command -v pandoc || true)"
  pandoc --version 2>/dev/null | sed -n '1,2p' || true
  echo "latexmk_path=$(command -v latexmk || true)"
  latexmk --version 2>/dev/null | sed -n '1,2p' || true
  echo "git_path=$(command -v git || true)"
  git --version 2>/dev/null || true
} > "$software_tmp"

/opt/anaconda3/bin/python -m pip freeze --all | LC_ALL=C sort > "$packages_tmp"

mv "$software_tmp" "$manifest_dir/software_versions.txt"
mv "$packages_tmp" "$manifest_dir/python_packages.txt"
trap - EXIT

shasum -a 256 \
  "$manifest_dir/software_versions.txt" \
  "$manifest_dir/python_packages.txt" \
  > "$manifest_dir/environment_SHA256SUMS"

echo "ENVIRONMENT_CAPTURED $manifest_dir"
