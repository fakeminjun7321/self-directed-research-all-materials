from pathlib import Path
import shutil
import subprocess

ROOT = Path("/Users/minjun/gromacs_practice/CILE_MD_clean")
SOURCE = ROOT / "00_lecture_source"
INITIAL = ROOT / "01_initial_structures"
RUNS = ROOT / "02_md_50ps"
VIEWS = ROOT / "03_vmd_views"

LABELS = ["L1P1", "L1P2", "L2P1", "L3P1", "L1P3"]
SYSTEMS = {
    "L1P1": {"Li+": 25, "c3c1pyrr+": 25, "fsi-": 50},
    "L1P2": {"Li+": 25, "c3c1pyrr+": 50, "fsi-": 75},
    "L2P1": {"Li+": 50, "c3c1pyrr+": 25, "fsi-": 75},
    "L3P1": {"Li+": 75, "c3c1pyrr+": 25, "fsi-": 100},
    "L1P3": {"Li+": 25, "c3c1pyrr+": 75, "fsi-": 100},
}
PACK_FILES = {
    "Li+": "Li_pack.xyz",
    "c3c1pyrr+": "c3c1pyrr_pack.xyz",
    "fsi-": "fsi_pack.xyz",
}
PDB_RESNAMES = {
    "Li+": "LIT",
    "c3c1pyrr+": "PYR",
    "fsi-": "FSI",
}
POSITIONS = {
    "L1P1": (-78.0, 32.0, 0.0),
    "L1P2": (0.0, 32.0, 0.0),
    "L2P1": (78.0, 32.0, 0.0),
    "L3P1": (-39.0, -42.0, 0.0),
    "L1P3": (39.0, -42.0, 0.0),
}

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


def run(command, cwd, **kwargs):
    print(f"[{cwd.relative_to(ROOT)}] " + " ".join(str(c) for c in command), flush=True)
    subprocess.run(command, cwd=cwd, check=True, **kwargs)


def forcefield_section() -> str:
    lines = []
    for line in (SOURCE / "field.top").read_text().splitlines():
        if line.strip() == "[ system ]":
            break
        lines.append(line)
    return "\n".join(lines).rstrip() + "\n\n"


def molecule_atom_names() -> dict[str, list[str]]:
    names = {}
    current = None
    in_atoms = False
    pending_moleculetype = False
    for raw in (SOURCE / "field.top").read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if line == "[ moleculetype ]":
            pending_moleculetype = True
            in_atoms = False
            current = None
            continue
        if line.startswith("[") and line != "[ atoms ]":
            in_atoms = False
        elif line == "[ atoms ]":
            in_atoms = current is not None
            continue
        elif pending_moleculetype:
            current = line.split()[0]
            names[current] = []
            pending_moleculetype = False
            continue
        elif in_atoms and current:
            parts = line.split()
            if len(parts) >= 5:
                names[current].append(parts[4])
    return names


def read_xyz(path: Path):
    lines = path.read_text().splitlines()
    count = int(lines[0].strip())
    atoms = []
    for line in lines[2 : 2 + count]:
        atom, x, y, z = line.split()[:4]
        atoms.append((atom, float(x), float(y), float(z)))
    return atoms


def box_size(total_atoms: int) -> float:
    base_atoms = 4650
    base_box = 84.240
    return max(52.0, base_box * (total_atoms / base_atoms) ** (1 / 3))


def write_packmol_input(label: str, counts: dict[str, int], box: float, path: Path):
    inner = box - 1.5
    lines = [
        f"# {label}: LiFSI/Pyr13FSI initial configuration",
        "tolerance 2.5",
        "filetype xyz",
        f"output {label}.xyz",
        "",
    ]
    for molecule in ["Li+", "c3c1pyrr+", "fsi-"]:
        lines.extend(
            [
                f"structure {PACK_FILES[molecule]}",
                f"  number {counts[molecule]}",
                f"  inside box 1.5000 1.5000 1.5000 {inner:.4f} {inner:.4f} {inner:.4f}",
                "end structure",
                "",
            ]
        )
    path.write_text("\n".join(lines))


def write_pdb(label: str, counts: dict[str, int], box: float, atom_names: dict[str, list[str]], xyz_path: Path, pdb_path: Path):
    xyz_atoms = read_xyz(xyz_path)
    lines = [
        f"TITLE     {label} LiFSI/Pyr13FSI Packmol initial structure",
        "REMARK    Generated for GROMACS and VMD practice",
        f"CRYST1{box:9.3f}{box:9.3f}{box:9.3f}  90.00  90.00  90.00 P 1           1",
    ]
    cursor = 0
    atom_id = 1
    resid = 1
    for molecule in ["Li+", "c3c1pyrr+", "fsi-"]:
        names = atom_names[molecule]
        resname = PDB_RESNAMES[molecule]
        for _ in range(counts[molecule]):
            for atom_name in names:
                element, x, y, z = xyz_atoms[cursor]
                lines.append(
                    f"HETATM{atom_id:5d} {atom_name:<4s} {resname:>3s} A{resid:4d}    "
                    f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {element:>2s}"
                )
                atom_id += 1
                cursor += 1
            resid += 1
    lines.append("END")
    pdb_path.write_text("\n".join(lines) + "\n")


def write_topology(path: Path, label: str, counts: dict[str, int]):
    text = forcefield_section()
    text += f"[ system ]\n{label} 50 ps practice\n\n[ molecules ]\n"
    for molecule in ["Li+", "c3c1pyrr+", "fsi-"]:
        text += f"{molecule:<18s} {counts[molecule]}\n"
    path.write_text(text)


def build_initial_structures():
    atom_names = molecule_atom_names()
    for required in ["Li+", "c3c1pyrr+", "fsi-"]:
        if required not in atom_names:
            raise RuntimeError(f"Missing moleculetype in field.top: {required}")

    for label, counts in SYSTEMS.items():
        work = INITIAL / label
        work.mkdir(parents=True, exist_ok=True)
        for molecule, filename in PACK_FILES.items():
            shutil.copy2(SOURCE / filename, work / filename)
        total_atoms = counts["Li+"] + counts["c3c1pyrr+"] * len(atom_names["c3c1pyrr+"]) + counts["fsi-"] * len(atom_names["fsi-"])
        box = box_size(total_atoms)
        pack_inp = work / f"{label}.pack.inp"
        write_packmol_input(label, counts, box, pack_inp)
        if not (work / f"{label}.xyz").exists():
            run(["packmol"], work, stdin=pack_inp.open())
        write_pdb(label, counts, box, atom_names, work / f"{label}.xyz", work / f"{label}.pdb")


def run_50ps_md():
    for label, counts in SYSTEMS.items():
        work = RUNS / label
        work.mkdir(parents=True, exist_ok=True)
        shutil.copy2(INITIAL / label / f"{label}.pdb", work / "start.pdb")
        write_topology(work / "topol.top", label, counts)
        (work / "em.mdp").write_text(EM_MDP)
        (work / "md_50ps.mdp").write_text(MD_50PS_MDP)
        if not (work / "em.gro").exists():
            run(["gmx", "grompp", "-f", "em.mdp", "-c", "start.pdb", "-p", "topol.top", "-o", "em.tpr", "-maxwarn", "20"], work)
            run(["gmx", "mdrun", "-deffnm", "em", "-nt", "8"], work)
        if not (work / "md_50ps.xtc").exists():
            run(["gmx", "grompp", "-f", "md_50ps.mdp", "-c", "em.gro", "-p", "topol.top", "-o", "md_50ps.tpr", "-maxwarn", "20"], work)
            run(["gmx", "mdrun", "-deffnm", "md_50ps", "-nt", "8"], work)


def trjconv_to_pdb(label: str) -> Path:
    work = RUNS / label
    out = work / "md_50ps_sampled.pdb"
    if not out.exists():
        run(
            ["gmx", "trjconv", "-s", "md_50ps.tpr", "-f", "md_50ps.xtc", "-dt", "0.5", "-o", out.name],
            work,
            input="0\n",
            text=True,
        )
    return out


def parse_models(path: Path):
    models = []
    current = []
    for line in path.read_text(errors="ignore").splitlines():
        if line.startswith("MODEL"):
            current = []
        elif line.startswith(("ATOM", "HETATM")):
            current.append((line, float(line[30:38]), float(line[38:46]), float(line[46:54])))
        elif line.startswith("ENDMDL"):
            if current:
                models.append(current)
    return models


def bounds(atoms):
    xs = [atom[1] for atom in atoms]
    ys = [atom[2] for atom in atoms]
    zs = [atom[3] for atom in atoms]
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def write_static_grid():
    out = VIEWS / "static_grid_initial.pdb"
    lines = [
        "TITLE     Static grid of five CILE initial structures",
        "REMARK    Visualization-only normalized view.",
        "CRYST1  220.000  140.000  100.000  90.00  90.00  90.00 P 1           1",
    ]
    atom_id = 1
    residue_offset = 0
    for label in LABELS:
        atoms = []
        for line in (INITIAL / label / f"{label}.pdb").read_text().splitlines():
            if line.startswith(("ATOM", "HETATM")):
                atoms.append((line, float(line[30:38]), float(line[38:46]), float(line[46:54])))
        min_x, max_x, min_y, max_y, min_z, max_z = bounds(atoms)
        cx, cy, cz = (min_x + max_x) / 2, (min_y + max_y) / 2, (min_z + max_z) / 2
        scale = 34.0 / max(max_x - min_x, max_y - min_y, max_z - min_z)
        ox, oy, oz = POSITIONS[label]
        for original, x, y, z in atoms:
            res_id = int(original[22:26]) + residue_offset
            chain = label[-1]
            lines.append(
                f"HETATM{atom_id:5d} {original[12:16]} {original[17:20]} {chain}{res_id:4d}    "
                f"{(x - cx) * scale + ox:8.3f}{(y - cy) * scale + oy:8.3f}{(z - cz) * scale + oz:8.3f}"
                f"{original[54:66]}          {original[76:78].strip():>2s}"
            )
            atom_id += 1
        residue_offset += 1000
    lines.append("END")
    out.write_text("\n".join(lines) + "\n")


def write_moving_grid():
    sampled = {label: parse_models(trjconv_to_pdb(label)) for label in LABELS}
    frame_count = min(len(frames) for frames in sampled.values())
    transforms = {}
    for label in LABELS:
        min_x, max_x, min_y, max_y, min_z, max_z = bounds(sampled[label][0])
        cx, cy, cz = (min_x + max_x) / 2, (min_y + max_y) / 2, (min_z + max_z) / 2
        scale = 34.0 / max(max_x - min_x, max_y - min_y, max_z - min_z)
        transforms[label] = (cx, cy, cz, scale, POSITIONS[label])

    out = VIEWS / "moving_grid_50ps.pdb"
    lines = [
        "TITLE     Moving grid of five CILE trajectories",
        "REMARK    Visualization-only combined trajectory.",
        "REMARK    Source simulations are 50 ps; frames sampled every 0.5 ps.",
        "CRYST1  220.000  140.000  100.000  90.00  90.00  90.00 P 1           1",
    ]
    for frame in range(frame_count):
        lines.append(f"MODEL{frame + 1:9d}")
        atom_id = 1
        residue_offset = 0
        for label in LABELS:
            cx, cy, cz, scale, (ox, oy, oz) = transforms[label]
            for original, x, y, z in sampled[label][frame]:
                res_id = int(original[22:26]) + residue_offset
                chain = label[-1]
                lines.append(
                    f"HETATM{atom_id:5d} {original[12:16]} {original[17:20]} {chain}{res_id:4d}    "
                    f"{(x - cx) * scale + ox:8.3f}{(y - cy) * scale + oy:8.3f}{(z - cz) * scale + oz:8.3f}"
                    f"{original[54:66]}          {original[76:78].strip():>2s}"
                )
                atom_id += 1
            residue_offset += 1000
        lines.append("ENDMDL")
    lines.append("END")
    out.write_text("\n".join(lines) + "\n")


def write_vmd_scripts():
    label_draws = "\n".join(
        f"draw text {{{x - 14:.1f} {y - 25:.1f} 0}} {{{label}}} size 1.8 thickness 2"
        for label, (x, y, _) in POSITIONS.items()
    )
    for filename, pdb, speed in [
        ("open_static_grid.tcl", "static_grid_initial.pdb", None),
        ("open_moving_grid_50ps.tcl", "moving_grid_50ps.pdb", "0.25"),
    ]:
        lines = [
            "display projection Orthographic",
            "display depthcue off",
            "color Display Background white",
            "axes location Off",
            f"mol new {{{VIEWS / pdb}}} type pdb waitfor all",
            "mol delrep 0 top",
            "mol representation VDW 0.420000 16.000000",
            "mol color Element",
            "mol selection all",
            "mol material Opaque",
            "mol addrep top",
            "draw color black",
            label_draws,
            "display resetview",
            "scale by 1.15",
            "rotate x by -15",
            "rotate y by 18",
            "menu main on",
        ]
        if speed:
            lines.extend(["animate goto start", f"animate speed {speed}", "animate forward"])
        lines.append("vwait forever")
        (VIEWS / filename).write_text("\n".join(lines) + "\n")


def main():
    build_initial_structures()
    run_50ps_md()
    write_static_grid()
    write_moving_grid()
    write_vmd_scripts()


if __name__ == "__main__":
    main()
