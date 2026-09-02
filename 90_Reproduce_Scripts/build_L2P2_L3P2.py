"""
교수님 슬라이드(L1P2, L2P2, L3P2 비교)를 만들기 위해 빠진 L2P2, L3P2 시스템을
- Packmol 초기구조 생성
- 위상(topol.top) 작성
- Energy minimization
- 50 ps production MD
- VMD용 trajectory 변환
까지 한번에 처리한다.
"""

from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "01_Raw_Data" / "Original_MD_Sources" / "MD_files"
INITIAL = ROOT / "01_Raw_Data" / "Initial_Structures_Packmol"
RUNS = ROOT / "02_Processed_Data" / "MD_Runs" / "50ps_Practice"
L1P2_REF = RUNS / "L1P2"

# 50 ps production MD 설정 (기존과 동일)
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

EM_MDP = """integrator            = steep
dt                    = 0.001
nsteps                = 5000
emtol                 = 1000

nstlog                = 500
nstxout-compressed    = 500

cutoff-scheme         = Verlet
rlist                 = 1.2
pbc                   = xyz

coulombtype           = PME
rcoulomb              = 1.2
ewald-rtol            = 1.0e-5
vdwtype               = Cut-off
rvdw                  = 1.2
DispCorr              = EnerPres

tcoupl                = no
pcoupl                = no

constraints           = h-bonds
constraint-algorithm  = LINCS
continuation          = no
"""

# 목표 시스템 정의: (Li 개수, Pyr13 개수, FSI 개수)
SYSTEMS = {
    "L2P2": {"li": 50, "pyr": 50, "fsi": 100},
    "L3P2": {"li": 75, "pyr": 50, "fsi": 125},
    "L2P3": {"li": 50, "pyr": 75, "fsi": 125},
    "L3P3": {"li": 75, "pyr": 75, "fsi": 150},
}

# atoms/Å³ - 기존 5개 시스템 모두 동일 (0.00778)
DENSITY = 0.00778

# Pyr13 27개 원자에 부여할 PDB atom name (PY1..PY27)
# FSI 9개 원자에 부여할 PDB atom name (FS1..FS9)


def system_atom_count(spec: dict[str, int]) -> int:
    return spec["li"] * 1 + spec["pyr"] * 27 + spec["fsi"] * 9


def box_length(spec: dict[str, int]) -> float:
    return (system_atom_count(spec) / DENSITY) ** (1 / 3)


def read_xyz_block(path: Path) -> tuple[list[str], list[tuple[float, float, float]]]:
    """packmol용 .xyz 한 분자 파일을 읽어 (원소, 좌표) 반환."""
    lines = path.read_text().splitlines()
    n_atoms = int(lines[0].strip())
    elements: list[str] = []
    coords: list[tuple[float, float, float]] = []
    for line in lines[2 : 2 + n_atoms]:
        parts = line.split()
        elements.append(parts[0])
        coords.append((float(parts[1]), float(parts[2]), float(parts[3])))
    return elements, coords


def write_packmol_input(label: str, spec: dict[str, int], work: Path) -> Path:
    box = box_length(spec)
    pack_lo = 1.5
    pack_hi = box - 1.5
    inp = work / f"{label}.pack.inp"
    inp.write_text(
        f"""# {label}: LiFSI/Pyr13FSI initial configuration
tolerance 2.5
filetype xyz
output {label}.xyz

structure Li_pack.xyz
  number {spec['li']}
  inside box {pack_lo:.4f} {pack_lo:.4f} {pack_lo:.4f} {pack_hi:.4f} {pack_hi:.4f} {pack_hi:.4f}
end structure

structure c3c1pyrr_pack.xyz
  number {spec['pyr']}
  inside box {pack_lo:.4f} {pack_lo:.4f} {pack_lo:.4f} {pack_hi:.4f} {pack_hi:.4f} {pack_hi:.4f}
end structure

structure fsi_pack.xyz
  number {spec['fsi']}
  inside box {pack_lo:.4f} {pack_lo:.4f} {pack_lo:.4f} {pack_hi:.4f} {pack_hi:.4f} {pack_hi:.4f}
end structure
"""
    )
    return inp


def run(cmd: list[str], cwd: Path, log_name: str, stdin: str | None = None) -> None:
    log_path = cwd / log_name
    with log_path.open("a") as log:
        log.write("$ " + " ".join(cmd) + "\n")
        log.flush()
        env = os.environ.copy()
        env["GMX_MAXBACKUP"] = "-1"
        subprocess.run(
            cmd,
            cwd=cwd,
            input=stdin,
            text=True,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
            env=env,
        )
        log.write("\n")


def run_packmol(work: Path, label: str) -> Path:
    xyz_out = work / f"{label}.xyz"
    if xyz_out.exists():
        return xyz_out
    log = work / "run_commands.log"
    with log.open("a") as fh:
        fh.write(f"$ packmol < {label}.pack.inp\n")
        fh.flush()
        with (work / f"{label}.pack.inp").open() as inp_fh:
            subprocess.run(
                ["packmol"], cwd=work, stdin=inp_fh, stdout=fh, stderr=subprocess.STDOUT, check=True
            )
    return xyz_out


def xyz_to_pdb(xyz: Path, pdb: Path, label: str, spec: dict[str, int], box: float) -> None:
    """packmol XYZ -> 기존 L1P2.pdb와 동일한 컨벤션의 PDB로 변환."""
    li_elements, _ = read_xyz_block(SOURCE / "Li_pack.xyz")
    pyr_elements, _ = read_xyz_block(SOURCE / "c3c1pyrr_pack.xyz")
    fsi_elements, _ = read_xyz_block(SOURCE / "fsi_pack.xyz")

    pyr_atom_names = [f"PY{i + 1}" for i in range(len(pyr_elements))]
    fsi_atom_names = [f"FS{i + 1}" for i in range(len(fsi_elements))]

    coords: list[tuple[str, tuple[float, float, float]]] = []
    raw_lines = xyz.read_text().splitlines()
    n_atoms = int(raw_lines[0].strip())
    for line in raw_lines[2 : 2 + n_atoms]:
        parts = line.split()
        coords.append((parts[0], (float(parts[1]), float(parts[2]), float(parts[3]))))

    with pdb.open("w") as f:
        f.write(f"TITLE     {label} LiFSI/Pyr13FSI Packmol configuration\n")
        f.write("REMARK    Built by build_L2P2_L3P2.py\n")
        f.write(f"CRYST1{box:9.3f}{box:9.3f}{box:9.3f}  90.00  90.00  90.00 P 1           1\n")

        atom_id = 0
        residue_id = 0
        idx = 0

        # Li atoms
        for _ in range(spec["li"]):
            residue_id += 1
            for li_idx in range(len(li_elements)):
                atom_id += 1
                element, (x, y, z) = coords[idx]
                idx += 1
                f.write(
                    f"HETATM{atom_id:5d} {'Li':<4s} LIT A{residue_id:4d}    "
                    f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {element:>2s}\n"
                )

        # Pyr13 atoms
        for _ in range(spec["pyr"]):
            residue_id += 1
            for pyr_idx in range(len(pyr_elements)):
                atom_id += 1
                element, (x, y, z) = coords[idx]
                idx += 1
                name = pyr_atom_names[pyr_idx]
                f.write(
                    f"HETATM{atom_id:5d} {name:<4s} PYR A{residue_id:4d}    "
                    f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {element:>2s}\n"
                )

        # FSI atoms
        for _ in range(spec["fsi"]):
            residue_id += 1
            for fsi_idx in range(len(fsi_elements)):
                atom_id += 1
                element, (x, y, z) = coords[idx]
                idx += 1
                name = fsi_atom_names[fsi_idx]
                f.write(
                    f"HETATM{atom_id:5d} {name:<4s} FSI A{residue_id:4d}    "
                    f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {element:>2s}\n"
                )

        f.write("END\n")

    assert idx == n_atoms, f"Atom count mismatch: parsed {idx}, expected {n_atoms}"


def build_topol(spec: dict[str, int], work: Path) -> None:
    """L1P2의 topol.top을 복사한 뒤 [ molecules ] 섹션의 분자 수만 변경."""
    src = L1P2_REF / "topol.top"
    dst = work / "topol.top"
    text = src.read_text()
    block = "[ molecules ]"
    head, _, tail = text.partition(block)
    # tail에는 ; name ... 이어 Li+ ... 줄들이 포함됨
    new_tail_lines = []
    in_molecules = True
    seen_atoms = False
    for line in tail.splitlines():
        if in_molecules:
            stripped = line.strip()
            if not stripped or stripped.startswith(";"):
                new_tail_lines.append(line)
                continue
            # 첫 데이터 줄부터 우리가 재작성
            new_tail_lines.append(f"Li+                {spec['li']}")
            new_tail_lines.append(f"c3c1pyrr+          {spec['pyr']}")
            new_tail_lines.append(f"fsi-               {spec['fsi']}")
            in_molecules = False
            seen_atoms = True
            continue
        else:
            # 추가 분자 종류는 모두 제거 (L1P2 원본은 [ molecules ] 끝에 있어서 그 뒤 줄은 없음)
            if line.strip():
                continue
            new_tail_lines.append(line)
    dst.write_text(head + block + "\n" + "\n".join(new_tail_lines) + "\n")


def prepare_initial(label: str, spec: dict[str, int]) -> Path:
    """01_Raw_Data/Initial_Structures_Packmol/{label}/ 안에 .pack.inp, .xyz, .pdb 만들기."""
    init_dir = INITIAL / label
    init_dir.mkdir(parents=True, exist_ok=True)

    for fname in ["Li_pack.xyz", "c3c1pyrr_pack.xyz", "fsi_pack.xyz"]:
        shutil.copy2(SOURCE / fname, init_dir / fname)

    write_packmol_input(label, spec, init_dir)
    xyz = run_packmol(init_dir, label)
    pdb = init_dir / f"{label}.pdb"
    xyz_to_pdb(xyz, pdb, label, spec, box_length(spec))
    return pdb


def run_md_pipeline(label: str, spec: dict[str, int], init_pdb: Path) -> None:
    work = RUNS / label
    work.mkdir(parents=True, exist_ok=True)
    shutil.copy2(init_pdb, work / "start.pdb")
    build_topol(spec, work)
    (work / "em.mdp").write_text(EM_MDP)
    (work / "md_50ps.mdp").write_text(MD_50PS_MDP)

    if not (work / "em.gro").exists():
        run(
            ["gmx", "grompp", "-f", "em.mdp", "-c", "start.pdb", "-p", "topol.top",
             "-o", "em.tpr", "-maxwarn", "100"],
            work,
            "run_commands.log",
        )
        run(["gmx", "mdrun", "-deffnm", "em", "-nt", "8"], work, "run_commands.log")

    if not (work / "md_50ps.tpr").exists():
        run(
            ["gmx", "grompp", "-f", "md_50ps.mdp", "-c", "em.gro", "-p", "topol.top",
             "-o", "md_50ps.tpr", "-maxwarn", "100"],
            work,
            "run_commands.log",
        )

    if not (work / "md_50ps.xtc").exists():
        run(["gmx", "mdrun", "-deffnm", "md_50ps", "-nt", "8"], work, "run_commands.log")

    if not (work / "md_50ps_sampled.pdb").exists():
        run(
            ["gmx", "trjconv", "-s", "md_50ps.tpr", "-f", "md_50ps.xtc",
             "-o", "md_50ps_sampled.pdb", "-dt", "0.5", "-pbc", "mol"],
            work,
            "run_commands.log",
            stdin="0\n",
        )


def update_initial_summary() -> None:
    """summary.csv에 L2P2, L3P2 추가."""
    csv_path = INITIAL / "summary.csv"
    lines = csv_path.read_text().splitlines()
    existing = {line.split(",")[0] for line in lines[1:]}
    for label, spec in SYSTEMS.items():
        if label in existing:
            continue
        total = system_atom_count(spec)
        box = box_length(spec)
        lines.append(f"{label},{spec['li']},{spec['pyr']},{spec['fsi']},{total},{box:.3f}")
    csv_path.write_text("\n".join(lines) + "\n")


def main() -> None:
    print(f"== build L2P2 / L3P2 ==")
    for label, spec in SYSTEMS.items():
        print(f"\n[{label}] atoms={system_atom_count(spec)} box={box_length(spec):.3f} Å")
        init_pdb = prepare_initial(label, spec)
        print(f"  initial PDB ready: {init_pdb.relative_to(ROOT)}")
        run_md_pipeline(label, spec, init_pdb)
        print(f"  50 ps MD done: {RUNS / label / 'md_50ps.xtc'}")
    update_initial_summary()
    print("\n== done ==")


if __name__ == "__main__":
    main()
