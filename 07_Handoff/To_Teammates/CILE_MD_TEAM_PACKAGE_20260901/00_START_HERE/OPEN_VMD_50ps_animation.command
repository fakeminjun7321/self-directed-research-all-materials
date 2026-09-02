#!/bin/zsh
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RESEARCH_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE_DIR="$RESEARCH_ROOT/03_Analysis_Results/VMD_View"
SOURCE_PDB="$SOURCE_DIR/01_all_five_50ps_animation.pdb"
SOURCE_SCRIPT="$SOURCE_DIR/VMD_01_open_50ps_animation.tcl"

find_vmd_launcher() {
  local override="${VMD_APP:-}"
  local root app launcher

  if [[ -n "$override" ]]; then
    if [[ -x "$override" ]]; then
      print -r -- "$override"
      return 0
    fi
    for launcher in \
      "$override/Contents/Resources/VMD.app/Contents/MacOS/VMD" \
      "$override/Contents/MacOS/VMD" \
      "$override/Contents/MacOS/startup.command"; do
      if [[ -x "$launcher" ]]; then
        print -r -- "$launcher"
        return 0
      fi
    done
  fi

  for root in /Applications "$HOME/Applications"; do
    for app in "$root"/VMD*.app(N); do
      for launcher in \
        "$app/Contents/Resources/VMD.app/Contents/MacOS/VMD" \
        "$app/Contents/MacOS/VMD" \
        "$app/Contents/MacOS/startup.command"; do
        if [[ -x "$launcher" ]]; then
          print -r -- "$launcher"
          return 0
        fi
      done
    done
  done

  return 1
}

VMD="$(find_vmd_launcher || true)"

if [[ -z "$VMD" ]]; then
  echo "VMD 앱을 찾을 수 없습니다."
  echo "VMD 앱을 /Applications 또는 ~/Applications에 설치하세요."
  echo "공식 다운로드: https://www.ks.uiuc.edu/Research/vmd/"
  echo
  echo "닫으려면 Enter를 누르세요."
  read
  exit 1
fi

if [[ ! -f "$SOURCE_PDB" ]]; then
  echo "VMD용 PDB 파일을 찾을 수 없습니다."
  echo "$SOURCE_PDB"
  echo
  echo "닫으려면 Enter를 누르세요."
  read
  exit 1
fi

if [[ ! -f "$SOURCE_SCRIPT" ]]; then
  echo "VMD 실행 스크립트를 찾을 수 없습니다."
  echo "$SOURCE_SCRIPT"
  echo
  echo "닫으려면 Enter를 누르세요."
  read
  exit 1
fi

MODEL_COUNT="$(grep -c '^MODEL' "$SOURCE_PDB" || true)"
ENDMDL_COUNT="$(grep -c '^ENDMDL' "$SOURCE_PDB" || true)"
if [[ "$MODEL_COUNT" -eq 0 || "$MODEL_COUNT" -ne "$ENDMDL_COUNT" ]]; then
  echo "VMD용 PDB 프레임 구조가 올바르지 않습니다."
  echo "MODEL=$MODEL_COUNT, ENDMDL=$ENDMDL_COUNT"
  echo "$SOURCE_PDB"
  echo
  echo "닫으려면 Enter를 누르세요."
  read
  exit 1
fi

echo "VMD 실행 파일: $VMD"
echo "5개 조성 애니메이션: $SOURCE_PDB"
echo "프레임 수: $MODEL_COUNT"

cd "$SOURCE_DIR"
exec "$VMD" -e "$SOURCE_SCRIPT"
