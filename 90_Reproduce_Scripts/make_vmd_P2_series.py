"""
교수님 P=2 시리즈(L1P2, L2P2, L3P2) 전용 VMD 비교 애니메이션을 만든다.

세 시스템의 50 ps trajectory를 가로로 나란히 배치한 PDB와 VMD 스크립트.
"""

from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "02_Processed_Data" / "MD_Runs" / "50ps_Practice"
OUT_DIR = ROOT / "03_Analysis_Results" / "VMD_View"

LABELS = ["L1P2", "L2P2", "L3P2"]
GRID_OFFSETS = {
    "L1P2": (-100.0, 0.0, 0.0),
    "L2P2": (0.0, 0.0, 0.0),
    "L3P2": (100.0, 0.0, 0.0),
}


def read_pdb_models(path: Path) -> list[list[str]]:
    models, current = [], []
    saw_model = False
    for line in path.read_text(errors="ignore").splitlines():
        rec = line[:6].strip()
        if rec == "MODEL":
            saw_model = True
            current = []
        elif rec == "ENDMDL":
            if current:
                models.append(current)
            current = []
        elif rec in {"ATOM", "HETATM"}:
            current.append(line)
    if not saw_model and current:
        models.append(current)
    if not saw_model:
        atoms = [
            line for line in path.read_text(errors="ignore").splitlines()
            if line[:6].strip() in {"ATOM", "HETATM"}
        ]
        if atoms:
            models.append(atoms)
    return models


def offset_atom_line(line: str, dx: float, dy: float, dz: float, atom_id: int, chain: str) -> str:
    x = float(line[30:38]) + dx
    y = float(line[38:46]) + dy
    z = float(line[46:54]) + dz
    return f"{line[:6]}{atom_id:5d}{line[11:21]}{chain}{line[22:30]}{x:8.3f}{y:8.3f}{z:8.3f}{line[54:]}"


def main() -> None:
    trajs = {
        label: read_pdb_models(RUNS / label / "md_50ps_sampled.pdb")
        for label in LABELS
    }
    frame_count = min(len(v) for v in trajs.values())
    print(f"frames per system: {frame_count}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_pdb = OUT_DIR / "03_P2_series_50ps_animation.pdb"
    chains = "ABC"

    with out_pdb.open("w") as fh:
        for fi in range(frame_count):
            fh.write(f"MODEL     {fi + 1:4d}\n")
            atom_id = 1
            for ch, label in zip(chains, LABELS):
                dx, dy, dz = GRID_OFFSETS[label]
                for atom in trajs[label][fi]:
                    fh.write(offset_atom_line(atom, dx, dy, dz, atom_id, ch) + "\n")
                    atom_id += 1
            fh.write("ENDMDL\n")

    labels_tcl = "\n".join(
        f'draw text {{{x - 12:.1f} {y + 32:.1f} {z:.1f}}} "{label}" size 3.2 thickness 3'
        for label, (x, y, z) in GRID_OFFSETS.items()
    )

    tcl = OUT_DIR / "VMD_03_open_P2_series_animation.tcl"
    tcl.write_text(
        f"""mol delete all
set here [file dirname [info script]]
display projection Orthographic
display backgroundgradient off
color Display Background black
axes location Off
mol new [file join $here "03_P2_series_50ps_animation.pdb"] type pdb waitfor all
mol delrep 0 top
mol representation VDW 0.45 16
mol color Element
mol selection all
mol addrep top
rotate x by -18
rotate y by 12
scale by 0.45
draw color white
{labels_tcl}
animate style Loop
animate speed 0.35
animate goto 0
animate forward
puts "Loaded P2-series 50 ps trajectory ({frame_count} frames per system)."
vwait forever
"""
    )

    # command 파일도 제공
    cmd = ROOT / "00_START_HERE" / "OPEN_VMD_P2_series.command"
    cmd.write_text(
        f"""#!/bin/zsh
set -e
VMD="/Applications/VMD 1.9.4a57-arm64-Rev12.app/Contents/MacOS/startup.command"
SOURCE_DIR="{OUT_DIR}"
SOURCE_SCRIPT="$SOURCE_DIR/VMD_03_open_P2_series_animation.tcl"
if [[ ! -x "$VMD" ]]; then
  echo "VMD 앱을 찾을 수 없습니다."
  read; exit 1
fi
cd "$SOURCE_DIR"
"$VMD" -e "$SOURCE_SCRIPT"
"""
    )
    cmd.chmod(0o755)
    print(f"saved: {out_pdb.relative_to(ROOT)}")
    print(f"saved: {tcl.relative_to(ROOT)}")
    print(f"saved: {cmd.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
