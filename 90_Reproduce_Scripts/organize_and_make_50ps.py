from __future__ import annotations

from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SOURCE_POOL = ROOT / "01_Raw_Data" / "Original_MD_Sources"
ARCHIVE = ROOT / "99_Old_Backup" / "Previous_Archives" / "2026-05-13_정리전백업"


def source_dir(name: str) -> Path:
    for visible in (SOURCE_POOL / name, ROOT / name):
        if visible.exists():
            return visible
    return ARCHIVE / name


SOURCE_INPUTS = source_dir("MD_files")
SOURCE_STATIC = source_dir("cile_variants")
SOURCE_SHORT_MD = source_dir("cile_variants_md")

ORIGINAL = ROOT / "01_Raw_Data" / "Original_MD_Sources"
INITIAL = ROOT / "01_Raw_Data" / "Initial_Structures_Packmol"
SHORT_REF = ROOT / "02_Processed_Data" / "MD_Runs" / "10ps_Practice"
LONG_MD = ROOT / "02_Processed_Data" / "MD_Runs" / "50ps_Practice"
VIEWS = ROOT / "03_Analysis_Results" / "VMD_View"

LABELS = ["L1P1", "L1P2", "L2P1", "L3P1", "L1P3"]

GRID_OFFSETS = {
    "L1P1": (-80.0, 32.0, 0.0),
    "L1P2": (0.0, 32.0, 0.0),
    "L2P1": (80.0, 32.0, 0.0),
    "L3P1": (-40.0, -42.0, 0.0),
    "L1P3": (40.0, -42.0, 0.0),
}

MD_50PS_MDP = """integrator            = md
dt                    = 0.001
nsteps                = 50000

nstlog                = 1000
nstenergy             = 1000
nstxout-compressed    = 250

cutoff-scheme         = Verlet
rlist                 = 1.2
pbc                   = xyz

coulombtype           = PME
rcoulomb              = 1.2
ewald-rtol            = 1.0e-5
vdwtype               = Cut-off
rvdw                  = 1.2
DispCorr              = EnerPres

tcoupl                = V-rescale
tc-grps               = System
tau-t                 = 0.1
ref-t                 = 298.0

pcoupl                = no

gen-vel               = yes
gen-temp              = 298.0
gen-seed              = -1

constraints           = h-bonds
constraint-algorithm  = LINCS
continuation          = no
"""


def copy_tree(src: Path, dst: Path) -> None:
    if src.exists():
        shutil.copytree(src, dst, dirs_exist_ok=True)


def copy_file(src: Path, dst: Path) -> None:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def run(command: list[str], cwd: Path, log_name: str, stdin: str | None = None) -> None:
    log_path = cwd / log_name
    with log_path.open("a") as log:
        log.write("$ " + " ".join(command) + "\n")
        log.flush()
        subprocess.run(
            command,
            cwd=cwd,
            input=stdin,
            text=True,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
        )
        log.write("\n")


def organize_sources() -> None:
    ORIGINAL.mkdir(parents=True, exist_ok=True)
    copy_tree(SOURCE_INPUTS, ORIGINAL / "MD_files")
    for pdf in sorted(RESEARCH.glob("*.pdf")):
        copy_file(pdf, ORIGINAL / "lectures" / pdf.name)

    for label in LABELS:
        dst = INITIAL / label
        dst.mkdir(parents=True, exist_ok=True)
        for suffix in [".pdb", ".xyz", ".pack.inp"]:
            copy_file(SOURCE_STATIC / f"{label}{suffix}", dst / f"{label}{suffix}")
        copy_file(SOURCE_STATIC / "summary.csv", INITIAL / "summary.csv")

        ref = SHORT_REF / label
        ref.mkdir(parents=True, exist_ok=True)
        for name in [
            "start.pdb",
            "topol.top",
            "em.mdp",
            "em.gro",
            "em.log",
            "md_short.mdp",
            "md_short.gro",
            "md_short.log",
            "md_short.xtc",
            "md_short.tpr",
        ]:
            copy_file(SOURCE_SHORT_MD / label / name, ref / name)


def prepare_long_md() -> None:
    for label in LABELS:
        src = SOURCE_SHORT_MD / label
        work = LONG_MD / label
        work.mkdir(parents=True, exist_ok=True)
        copy_file(src / "em.gro", work / "em.gro")
        copy_file(src / "topol.top", work / "topol.top")
        copy_file(src / "start.pdb", work / "start.pdb")
        (work / "md_50ps.mdp").write_text(MD_50PS_MDP)

        if not (work / "md_50ps.tpr").exists():
            print(f"[{label}] preparing 50 ps input")
            run(
                [
                    "gmx",
                    "grompp",
                    "-f",
                    "md_50ps.mdp",
                    "-c",
                    "em.gro",
                    "-p",
                    "topol.top",
                    "-o",
                    "md_50ps.tpr",
                    "-maxwarn",
                    "100",
                ],
                work,
                "run_commands.log",
            )

        if not (work / "md_50ps.xtc").exists():
            print(f"[{label}] running 50 ps MD")
            run(["gmx", "mdrun", "-deffnm", "md_50ps", "-nt", "8"], work, "run_commands.log")

        if not (work / "md_50ps_sampled.pdb").exists():
            print(f"[{label}] converting trajectory for VMD")
            run(
                [
                    "gmx",
                    "trjconv",
                    "-s",
                    "md_50ps.tpr",
                    "-f",
                    "md_50ps.xtc",
                    "-o",
                    "md_50ps_sampled.pdb",
                    "-dt",
                    "0.5",
                    "-pbc",
                    "mol",
                ],
                work,
                "run_commands.log",
                stdin="0\n",
            )


def read_pdb_models(path: Path) -> list[list[str]]:
    models: list[list[str]] = []
    current: list[str] = []
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

    if not saw_model:
        atoms = [
            line
            for line in path.read_text(errors="ignore").splitlines()
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


def write_static_grid() -> None:
    out = VIEWS / "02_all_five_initial_structure.pdb"
    VIEWS.mkdir(parents=True, exist_ok=True)
    atom_id = 1
    chain_names = "ABCDE"
    with out.open("w") as fh:
        for chain, label in zip(chain_names, LABELS):
            atoms = [line for line in (INITIAL / label / f"{label}.pdb").read_text().splitlines() if line[:6].strip() in {"ATOM", "HETATM"}]
            dx, dy, dz = GRID_OFFSETS[label]
            fh.write(f"REMARK {label}\n")
            for atom in atoms:
                fh.write(offset_atom_line(atom, dx, dy, dz, atom_id, chain) + "\n")
                atom_id += 1
        fh.write("END\n")


def write_moving_grid() -> int:
    trajectories = {
        label: read_pdb_models(LONG_MD / label / "md_50ps_sampled.pdb")
        for label in LABELS
    }
    frame_count = min(len(frames) for frames in trajectories.values())
    out = VIEWS / "01_all_five_50ps_animation.pdb"
    chain_names = "ABCDE"

    with out.open("w") as fh:
        for frame_index in range(frame_count):
            fh.write(f"MODEL     {frame_index + 1:4d}\n")
            atom_id = 1
            for chain, label in zip(chain_names, LABELS):
                dx, dy, dz = GRID_OFFSETS[label]
                for atom in trajectories[label][frame_index]:
                    fh.write(offset_atom_line(atom, dx, dy, dz, atom_id, chain) + "\n")
                    atom_id += 1
            fh.write("ENDMDL\n")
    return frame_count


def write_vmd_scripts(frame_count: int) -> None:
    labels = "\n".join(
        f'draw text {{{x - 12:.1f} {y + 24:.1f} {z:.1f}}} "{label}" size 2.8 thickness 3'
        for label, (x, y, z) in GRID_OFFSETS.items()
    )
    moving = VIEWS / "VMD_01_open_50ps_animation.tcl"
    moving.write_text(
        f"""mol delete all
set here [file dirname [info script]]
display projection Orthographic
display backgroundgradient off
color Display Background black
axes location Off
mol new [file join $here "01_all_five_50ps_animation.pdb"] type pdb waitfor all
mol delrep 0 top
mol representation VDW 0.45 16
mol color Element
mol selection all
mol addrep top
rotate x by -18
rotate y by 12
scale by 0.55
draw color white
{labels}
animate style Loop
animate speed 0.35
animate goto 0
animate forward
puts "Loaded five 50 ps trajectories with {frame_count} sampled frames."
vwait forever
"""
    )

    static = VIEWS / "VMD_02_open_initial_structure.tcl"
    static.write_text(
        f"""mol delete all
set here [file dirname [info script]]
display projection Orthographic
display backgroundgradient off
color Display Background black
axes location Off
mol new [file join $here "02_all_five_initial_structure.pdb"] type pdb waitfor all
mol delrep 0 top
mol representation VDW 0.45 16
mol color Element
mol selection all
mol addrep top
rotate x by -18
rotate y by 12
scale by 0.55
draw color white
{labels}
vwait forever
"""
    )


def write_readme(frame_count: int) -> None:
    start_here = ROOT / "00_START_HERE"
    start_here.mkdir(parents=True, exist_ok=True)
    (start_here / "README_generated_50ps.md").write_text(
        f"""# CILE MD 정리 폴더

L1P1, L1P2, L2P1, L3P1, L1P3 다섯 조성을 보기 쉽게 정리한 폴더입니다.

## 폴더 구조

- `01_Raw_Data/Original_MD_Sources/`: 원본 `MD_files`
- `01_Raw_Data/Initial_Structures_Packmol/`: Packmol로 만든 초기 구조
- `02_Processed_Data/MD_Runs/10ps_Practice/`: 예전에 만든 10 ps 연습 결과
- `02_Processed_Data/MD_Runs/50ps_Practice/`: 새로 돌린 50 ps GROMACS 결과
- `03_Analysis_Results/VMD_View/`: VMD에서 바로 여는 합쳐진 PDB와 실행 스크립트
- `90_Reproduce_Scripts/`: 이 폴더를 다시 만들 때 쓰는 스크립트

## VMD에서 열기

```bash
"/Applications/VMD 1.9.4a57-arm64-Rev12.app/Contents/MacOS/startup.command" -e "{VIEWS / 'VMD_01_open_50ps_animation.tcl'}"
```

`01_all_five_50ps_animation.pdb`는 50 ps 결과에서 0.5 ps 간격으로 뽑은 {frame_count} 프레임짜리 애니메이션 파일입니다.
"""
    )


def main() -> None:
    organize_sources()
    prepare_long_md()
    write_static_grid()
    frame_count = write_moving_grid()
    write_vmd_scripts(frame_count)
    write_readme(frame_count)
    print(f"Done. Clean workspace: {ROOT}")
    print(f"VMD script: {VIEWS / 'VMD_01_open_50ps_animation.tcl'}")


if __name__ == "__main__":
    main()
