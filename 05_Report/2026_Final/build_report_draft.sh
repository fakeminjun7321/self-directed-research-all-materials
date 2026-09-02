#!/usr/bin/env bash
set -euo pipefail

report_dir="$(cd "$(dirname "$0")" && pwd)"
output="$report_dir/자율연구_보고서_초안.docx"

if [ -e "$output" ]; then
  echo "refusing to overwrite existing draft: $output" >&2
  exit 2
fi

cd "$report_dir"
pandoc \
  report_source.md METHODS.md LIMITATIONS.md \
  --metadata lang=ko \
  -o "$output"

echo "REPORT_DRAFT_BUILT $output"
