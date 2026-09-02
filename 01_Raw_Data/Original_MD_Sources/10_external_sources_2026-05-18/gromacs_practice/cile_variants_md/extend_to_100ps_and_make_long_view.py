from pathlib import Path
import subprocess

ROOT = Path("/Users/minjun/gromacs_practice/cile_variants_md")
LABELS = ["L1P1", "L1P2", "L2P1", "L3P1", "L1P3"]
POSITIONS = {
    "L1P1": (-78.0, 32.0, 0.0),
    "L1P2": (0.0, 32.0, 0.0),
    "L2P1": (78.0, 32.0, 0.0),
    "L3P1": (-39.0, -42.0, 0.0),
    "L1P3": (39.0, -42.0, 0.0),
}


def run(command, cwd, **kwargs):
    print(f"[{cwd.name}] " + " ".join(str(c) for c in command), flush=True)
    subprocess.run(command, cwd=cwd, check=True, **kwargs)


def extend_if_needed(label: str):
    work = ROOT / label
    long_tpr = work / "md_100ps.tpr"
    if not long_tpr.exists():
        run(["gmx", "convert-tpr", "-s", "md_short.tpr", "-until", "100", "-o", "md_100ps.tpr"], work)

    log = work / "md_short.log"
    already_100 = log.exists() and "100000 steps,    100.0 ps" in log.read_text(errors="ignore")
    if not already_100:
        run(["gmx", "mdrun", "-s", "md_100ps.tpr", "-cpi", "md_short.cpt", "-deffnm", "md_short", "-nt", "8"], work)


def write_sampled_pdb(label: str) -> Path:
    work = ROOT / label
    out = work / "md_100ps_sampled_0p5ps.pdb"
    if out.exists():
        return out
    run(
        ["gmx", "trjconv", "-s", "md_100ps.tpr", "-f", "md_short.xtc", "-dt", "0.5", "-o", out.name],
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
    if current:
        models.append(current)
    return models


def bounds(atoms):
    xs = [atom[1] for atom in atoms]
    ys = [atom[2] for atom in atoms]
    zs = [atom[3] for atom in atoms]
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def make_combined(paths: dict[str, Path]):
    trajectories = {label: parse_models(path) for label, path in paths.items()}
    frame_count = min(len(frames) for frames in trajectories.values())

    transforms = {}
    for label in LABELS:
        min_x, max_x, min_y, max_y, min_z, max_z = bounds(trajectories[label][0])
        cx = (min_x + max_x) / 2
        cy = (min_y + max_y) / 2
        cz = (min_z + max_z) / 2
        span = max(max_x - min_x, max_y - min_y, max_z - min_z)
        transforms[label] = (cx, cy, cz, 34.0 / span, POSITIONS[label])

    out_lines = [
        "TITLE     Long moving grid view of five CILE trajectories",
        "REMARK    Visualization-only combined trajectory.",
        "REMARK    Source simulations are 100 ps; frames sampled every 0.5 ps.",
        "CRYST1  220.000  140.000  100.000  90.00  90.00  90.00 P 1           1",
    ]

    for frame in range(frame_count):
        out_lines.append(f"MODEL{frame + 1:9d}")
        atom_id = 1
        residue_offset = 0
        for label in LABELS:
            cx, cy, cz, scale, (ox, oy, oz) = transforms[label]
            for original, x, y, z in trajectories[label][frame]:
                new_x = (x - cx) * scale + ox
                new_y = (y - cy) * scale + oy
                new_z = (z - cz) * scale + oz
                res_id = int(original[22:26]) + residue_offset
                chain = label[-1]
                out_lines.append(
                    f"HETATM{atom_id:5d} {original[12:16]} {original[17:20]} {chain}{res_id:4d}    "
                    f"{new_x:8.3f}{new_y:8.3f}{new_z:8.3f}"
                    f"{original[54:66]}          {original[76:78].strip():>2s}"
                )
                atom_id += 1
            residue_offset += 1000
        out_lines.append("ENDMDL")
    out_lines.append("END")

    combined = ROOT / "all_five_moving_grid_100ps.pdb"
    combined.write_text("\n".join(out_lines) + "\n")

    label_draws = "\n".join(
        f"draw text {{{x - 14:.1f} {y - 25:.1f} 0}} {{{label}}} size 1.8 thickness 2"
        for label, (x, y, _) in POSITIONS.items()
    )
    tcl = f"""
display projection Orthographic
display depthcue off
color Display Background white
axes location Off
mol new {{{combined}}} type pdb waitfor all
mol delrep 0 top
mol representation VDW 0.420000 16.000000
mol color Element
mol selection all
mol material Opaque
mol addrep top
draw color black
{label_draws}
display resetview
scale by 1.15
rotate x by -15
rotate y by 18
animate goto start
animate speed 0.28
animate forward
menu main on
vwait forever
"""
    (ROOT / "open_moving_grid_100ps_keepopen.tcl").write_text(tcl.strip() + "\n")


def main():
    for label in LABELS:
        extend_if_needed(label)
    paths = {label: write_sampled_pdb(label) for label in LABELS}
    make_combined(paths)


if __name__ == "__main__":
    main()
