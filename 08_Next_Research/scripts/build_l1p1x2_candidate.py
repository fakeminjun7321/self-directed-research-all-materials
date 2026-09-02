#!/usr/bin/env python3
"""Build an isolated L1P1x2 Packmol candidate and optionally run strict EM."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

DALTON_KG = 1.66053906660e-27
MASS_U = 2.0 * (25 * 6.941 + 25 * 128.239 + 50 * 180.124)
COUNTS = {"Li+": 50, "c3c1pyrr+": 50, "fsi-": 100}
ATOM_COUNT = 2300
PACKMOL_DEFAULT_SEED = 1234567
PACKMOL_MAX_SEED = 2_147_483_647

PROJECT = Path(__file__).resolve().parents[2]
NEXT = PROJECT / "08_Next_Research"
SOURCE = PROJECT / "01_Raw_Data" / "Original_MD_Sources" / "MD_files"
FFTOOL = PROJECT / "90_Reproduce_Scripts" / "tools" / "fftool" / "fftool"
CANONICAL_TOP = PROJECT / "07_Handoff" / "CILE_MD_Handoff_v0_DRAFT" / "systems" / "L1P1" / "topol.top"
EM_MDP = PROJECT / "07_Handoff" / "CILE_MD_Handoff_v0_DRAFT" / "mdp" / "01_em_strict.mdp"


def box_nm_for_density(density_kg_m3: float) -> float:
    return (MASS_U * DALTON_KG / density_kg_m3) ** (1.0 / 3.0) * 1e9


def validate_packmol_seed(seed: int) -> int:
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("Packmol seed must be an integer")
    if not 1 <= seed <= PACKMOL_MAX_SEED:
        raise ValueError(
            f"Packmol seed must be between 1 and {PACKMOL_MAX_SEED}"
        )
    return seed


def set_packmol_seed(text: str, seed: int) -> str:
    """Insert one explicit, reproducible global Packmol seed."""
    seed = validate_packmol_seed(seed)
    lines = text.splitlines()
    matches = [
        index
        for index, line in enumerate(lines)
        if re.match(r"^\s*seed(?:\s+|$)", line, re.IGNORECASE)
        and not line.lstrip().startswith("#")
    ]
    if len(matches) > 1:
        raise ValueError("Packmol input contains more than one global seed")
    if matches:
        parts = lines[matches[0]].split()
        if len(parts) != 2 or not re.fullmatch(r"[+-]?\d+", parts[1]):
            raise ValueError("Packmol input contains a malformed global seed")
        existing = int(parts[1])
        if existing != seed:
            raise ValueError(
                f"Packmol input seed mismatch: existing {existing}, requested {seed}"
            )
        lines[matches[0]] = f"seed {seed}"
    else:
        insert_at = 1 if lines and lines[0].lstrip().startswith("#") else 0
        lines.insert(insert_at, f"seed {seed}")
    return "\n".join(lines) + "\n"


def parse_packmol_observed_seed(text: str) -> int:
    matches = re.findall(
        r"Seed for random number generator:\s*([+-]?\d+)", text
    )
    if len(matches) != 1:
        raise ValueError(
            f"expected one observed Packmol seed in the execution log, found {len(matches)}"
        )
    return validate_packmol_seed(int(matches[0]))


def parse_packmol_completion(text: str) -> dict[str, object]:
    versions = re.findall(r"\bVersion\s+([0-9]+(?:\.[0-9]+)+)", text)
    successes = re.findall(r"^\s*Success!\s*$", text, re.MULTILINE)
    target = re.findall(
        r"Maximum violation of target distance:\s*([-+0-9.eE]+)", text
    )
    constraints = re.findall(
        r"Maximum violation of the constraints:\s*([-+0-9.eE]+)", text
    )
    if len(versions) != 1 or len(successes) != 1 or not target or not constraints:
        raise ValueError("Packmol completion evidence is missing or ambiguous")
    final_target = float(target[-1])
    final_constraint = float(constraints[-1])
    if not math.isfinite(final_target) or not math.isfinite(final_constraint):
        raise ValueError("Packmol completion metrics are non-finite")
    if not 0.0 <= final_target <= 0.01 or not 0.0 <= final_constraint <= 0.01:
        raise ValueError("Packmol final violations exceed 0.01")
    return {
        "version": versions[0],
        "success_markers": 1,
        "final_target_distance_violation": final_target,
        "final_constraint_violation": final_constraint,
    }


def require_em_threads(threads: int) -> int:
    if threads != 6:
        raise ValueError("Mac safety policy requires exactly --threads 6 for EM")
    return threads


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_command(
    command: list[str], cwd: Path, log: Path, stdin_path: Path | None = None
) -> None:
    with log.open("a") as output:
        output.write("$ " + shlex.join(command) + "\n")
        output.flush()
        env = os.environ.copy()
        env["GMX_MAXBACKUP"] = "-1"
        if stdin_path:
            with stdin_path.open() as input_handle:
                subprocess.run(
                    command,
                    cwd=cwd,
                    stdin=input_handle,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    text=True,
                    check=True,
                    env=env,
                )
        else:
            subprocess.run(
                command,
                cwd=cwd,
                stdout=output,
                stderr=subprocess.STDOUT,
                text=True,
                check=True,
                env=env,
            )
        output.write("\n")


def capture_command(command: list[str], cwd: Path, log: Path, artifact: Path) -> str:
    env = os.environ.copy()
    env["GMX_MAXBACKUP"] = "-1"
    result = subprocess.run(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=True,
        env=env,
    )
    artifact.write_text(result.stdout)
    with log.open("a") as output:
        output.write("$ " + shlex.join(command) + "\n")
        output.write(result.stdout + "\n")
    return result.stdout


def scale_topology_charges(source: Path, factor: float = 0.75) -> str:
    """Scale atom-type and molecule-atom charges while retaining fftool names."""
    output: list[str] = []
    section = ""
    for raw in source.read_text().splitlines():
        stripped = raw.strip()
        if stripped.startswith("!"):
            raw = ";" + raw[1:]
            stripped = raw.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped.strip("[] ").lower()
            output.append(raw)
            continue
        if not stripped or stripped.startswith(";"):
            output.append(raw)
            continue
        parts = raw.split()
        if section == "atomtypes" and len(parts) >= 7:
            parts[3] = f"{float(parts[3]) * factor:.6f}"
            raw = "  ".join(parts)
        elif section == "atoms" and len(parts) >= 7:
            parts[6] = f"{float(parts[6]) * factor:.6f}"
            raw = "  ".join(parts)
        output.append(raw)
    return "\n".join(output) + "\n"


def molecule_charge_sums(topology: str) -> dict[str, float]:
    sums: dict[str, float] = {}
    section = ""
    current_molecule: str | None = None
    need_molecule_name = False
    for raw in topology.splitlines():
        stripped = raw.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped.strip("[] ").lower()
            need_molecule_name = section == "moleculetype"
            continue
        if not stripped or stripped.startswith(";"):
            continue
        parts = stripped.split()
        if section == "moleculetype" and need_molecule_name:
            current_molecule = parts[0]
            sums[current_molecule] = 0.0
            need_molecule_name = False
        elif section == "atoms" and current_molecule is not None:
            sums[current_molecule] += float(parts[6])
    return sums


def parse_gro_box(path: Path) -> tuple[float, float, float]:
    parts = path.read_text().splitlines()[-1].split()
    if len(parts) < 3:
        raise ValueError(f"invalid GRO box line in {path}")
    return float(parts[0]), float(parts[1]), float(parts[2])


def density_from_box(box: tuple[float, float, float]) -> float:
    volume_m3 = box[0] * box[1] * box[2] * 1e-27
    return MASS_U * DALTON_KG / volume_m3


def bad_marker_counts(paths: list[Path]) -> dict[str, int]:
    combined = "\n".join(p.read_text(errors="replace") for p in paths if p.exists())
    return {
        "fatal": len(re.findall(r"fatal error", combined, re.IGNORECASE)),
        "nan": len(re.findall(r"\bnan\b", combined, re.IGNORECASE)),
        "lincs": len(re.findall(r"lincs warning", combined, re.IGNORECASE)),
    }


def parse_em_summary(path: Path) -> dict[str, float | int | bool]:
    text = path.read_text(errors="replace")
    converged = re.search(r"converged to Fmax <[^\n]* in\s+(\d+) steps", text)
    potential = re.search(r"Potential Energy\s*=\s*([-+0-9.eE]+)", text)
    maximum_force = re.search(r"Maximum force\s*=\s*([-+0-9.eE]+)", text)
    return {
        "converged": converged is not None,
        "steps": int(converged.group(1)) if converged else -1,
        "potential_energy_kj_mol": float(potential.group(1)) if potential else float("nan"),
        "maximum_force_kj_mol_nm": float(maximum_force.group(1)) if maximum_force else float("nan"),
    }


def grompp_warning_count(path: Path) -> int:
    text = path.read_text(errors="replace")
    match = re.search(r"\$ gmx grompp\b(.*?)\n\$ gmx (?:dump|mdrun)\b", text, re.DOTALL)
    return 999 if match is None else len(re.findall(r"\bWARNING\b", match.group(1)))


def write_run_record(
    path: Path,
    run_id: str,
    density: float,
    box_nm: float,
    packmol_seed: int,
    start: str,
    end: str,
    status: str,
    detail: str,
) -> None:
    path.write_text(
        f"""# Run record: {run_id}

- System: L1P1x2 = Li 50 / Pyr13 50 / FSI 100 ({ATOM_COUNT} atoms)
- Protocol: v0.2-candidate
- Requested initial density: {density:.3f} kg/m³
- Calculated cubic box: {box_nm:.6f} nm
- Packmol random seed: {packmol_seed}
- Start: {start}
- End: {end}
- Technical status: {status}
- Physics status: NOT_VERIFIED
- Detail: {detail}

The requested density is an engineering pilot input, not an approved physical target. Energy minimization does not establish equilibrium or validate transport properties.
"""
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--density", type=float, default=1400.0)
    parser.add_argument("--tolerance", type=float, default=2.0)
    parser.add_argument("--threads", type=int, default=6)
    parser.add_argument("--packmol-seed", type=int, default=PACKMOL_DEFAULT_SEED)
    parser.add_argument("--run-id")
    parser.add_argument("--execute-em", action="store_true")
    args = parser.parse_args()

    if args.density <= 0 or args.tolerance <= 0 or args.threads <= 0:
        raise SystemExit("density, tolerance, and threads must be positive")
    try:
        validate_packmol_seed(args.packmol_seed)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if args.execute_em:
        try:
            require_em_threads(args.threads)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    if not FFTOOL.exists() or not CANONICAL_TOP.exists() or not EM_MDP.exists():
        raise SystemExit("required fftool/canonical topology/EM MDP is missing")
    for tool in ("packmol", "gmx"):
        if shutil.which(tool) is None:
            raise SystemExit(f"required executable not found: {tool}")

    run_id = args.run_id or f"pilot_L1P1x2_rho{args.density:g}"
    run_dir = NEXT / "04_Runs" / run_id
    if run_dir.exists():
        raise SystemExit(f"refusing to overwrite existing run: {run_dir}")
    input_dir = run_dir / "input"
    input_dir.mkdir(parents=True)
    log = run_dir / "commands.log"
    start = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    box_nm = box_nm_for_density(args.density)
    box_a = box_nm * 10.0
    status = "FAILED"
    detail = "candidate generation did not finish"

    try:
        for name in ("Li.zmat", "c3c1pyrr.zmat", "fsi.zmat", "il.ff"):
            shutil.copy2(SOURCE / name, input_dir / name)

        base_command = [
            sys.executable,
            str(FFTOOL),
            "50",
            "Li.zmat",
            "50",
            "c3c1pyrr.zmat",
            "100",
            "fsi.zmat",
            "--box",
            f"{box_a:.6f}",
            "--tol",
            f"{args.tolerance:g}",
        ]
        run_command(base_command, input_dir, log)
        packmol_input = input_dir / "pack.inp"
        packmol_input.write_text(
            set_packmol_seed(packmol_input.read_text(), args.packmol_seed)
        )
        run_command(["packmol"], input_dir, log, input_dir / "pack.inp")
        observed_packmol_seed = parse_packmol_observed_seed(log.read_text())
        packmol_completion = parse_packmol_completion(log.read_text())
        if observed_packmol_seed != args.packmol_seed:
            raise RuntimeError(
                f"Packmol used seed {observed_packmol_seed}, expected {args.packmol_seed}"
            )
        run_command(base_command + ["--gmx"], input_dir, log)
        # fftool may regenerate pack.inp while creating GROMACS inputs. Restore
        # the exact seed that the Packmol execution log proves was used.
        packmol_input.write_text(
            set_packmol_seed(packmol_input.read_text(), args.packmol_seed)
        )

        generated_gro = input_dir / "config.gro"
        generated_pdb = input_dir / "config.pdb"
        if generated_gro.exists():
            generated_gro.replace(input_dir / "initial.gro")
        elif generated_pdb.exists():
            # This bundled fftool version documents GRO output but emits PDB.
            # Convert coordinates and the CRYST1 box without changing topology.
            run_command(
                [
                    "gmx",
                    "editconf",
                    "-f",
                    "config.pdb",
                    "-o",
                    "initial.gro",
                ],
                input_dir,
                log,
            )
        else:
            raise RuntimeError("fftool did not create config.gro or config.pdb")
        generated_full_charge = input_dir / "field.top"
        scaled_topology = scale_topology_charges(generated_full_charge, 0.75)
        charge_sums = molecule_charge_sums(scaled_topology)
        expected_charges = {"Li+": 0.75, "c3c1pyrr+": 0.75, "fsi-": -0.75}
        for molecule, expected in expected_charges.items():
            if abs(charge_sums.get(molecule, 999.0) - expected) > 1e-8:
                raise RuntimeError(
                    f"scaled charge mismatch for {molecule}: {charge_sums.get(molecule)}"
                )
        (input_dir / "topol.top").write_text(scaled_topology)
        full_charge_reference = input_dir / "field_full_charge_REFERENCE_ONLY.top"
        generated_full_charge.replace(full_charge_reference)
        shutil.copy2(EM_MDP, input_dir / "em.mdp")
        (input_dir / "README_INPUTS.md").write_text(
            "# Candidate input files\n\n"
            "- `topol.top`: actual candidate topology; charges scaled uniformly by 0.75.\n"
            "- `field_full_charge_REFERENCE_ONLY.top`: raw fftool output with full charges; do not use for this candidate.\n"
            "- `initial.gro`: Packmol coordinates converted from fftool `config.pdb`.\n"
            f"- `pack.inp`: Packmol input with explicit global seed `{args.packmol_seed}`.\n"
            "- `em.mdp`: strict energy-minimization input copied from the handoff baseline.\n"
        )

        initial_lines = (input_dir / "initial.gro").read_text().splitlines()
        if int(initial_lines[1].strip()) != ATOM_COUNT:
            raise RuntimeError("initial.gro atom count is not 2300")

        input_files = [
            input_dir / "initial.gro",
            input_dir / "simbox.xyz",
            input_dir / "topol.top",
            input_dir / "em.mdp",
            full_charge_reference,
            input_dir / "pack.inp",
            input_dir / "README_INPUTS.md",
            input_dir / "Li.zmat",
            input_dir / "c3c1pyrr.zmat",
            input_dir / "fsi.zmat",
            input_dir / "il.ff",
        ]
        (run_dir / "INPUT_SHA256SUMS").write_text(
            "".join(f"{sha256(path)}  input/{path.name}\n" for path in input_files)
        )

        initial_box = parse_gro_box(input_dir / "initial.gro")
        metrics: dict[str, object] = {
            "run_id": run_id,
            "atom_count": ATOM_COUNT,
            "requested_density_kg_m3": args.density,
            "calculated_box_nm": box_nm,
            "initial_box_nm": initial_box,
            "initial_density_kg_m3": density_from_box(initial_box),
            "packmol_seed_requested": args.packmol_seed,
            "packmol_seed_observed": observed_packmol_seed,
            "packmol_completion": packmol_completion,
            "topology_source": "fftool field.top generated from copied il.ff; charges scaled by script",
            "canonical_topology_sha256": sha256(CANONICAL_TOP),
            "charge_scaling_retained": 0.75,
            "molecule_charge_sums": charge_sums,
            "physics_status": "NOT_VERIFIED",
        }

        if args.execute_em:
            run_command(
                [
                    "gmx",
                    "grompp",
                    "-f",
                    "input/em.mdp",
                    "-c",
                    "input/initial.gro",
                    "-p",
                    "input/topol.top",
                    "-o",
                    "em.tpr",
                    "-po",
                    "em_out.mdp",
                ],
                run_dir,
                log,
            )
            tpr_dump = capture_command(
                ["gmx", "dump", "-s", "em.tpr"],
                run_dir,
                log,
                run_dir / "em_tpr_dump.txt",
            )
            rlist_match = re.search(r"\brlist\s*=\s*([-+0-9.eE]+)", tpr_dump)
            if rlist_match is None:
                raise RuntimeError("could not read actual rlist from em.tpr")
            actual_rlist_nm = float(rlist_match.group(1))
            run_command(
                ["gmx", "mdrun", "-deffnm", "em", "-nt", str(args.threads)],
                run_dir,
                log,
            )
            if (run_dir / "em.trr").exists():
                run_command(["gmx", "check", "-f", "em.trr"], run_dir, log)
            final_box = parse_gro_box(run_dir / "em.gro")
            markers = bad_marker_counts([log, run_dir / "em.log"])
            em_summary = parse_em_summary(run_dir / "em.log")
            warning_count = grompp_warning_count(log)
            metrics.update(
                {
                    "final_box_nm": final_box,
                    "final_density_kg_m3": density_from_box(final_box),
                    "bad_markers": markers,
                    "grompp_warning_count": warning_count,
                    "em_summary": em_summary,
                    "actual_rlist_nm": actual_rlist_nm,
                    "min_box_over_2rlist": min(final_box) / (2.0 * actual_rlist_nm),
                }
            )
            if any(markers.values()):
                raise RuntimeError(f"bad log markers detected: {markers}")
            if warning_count != 0:
                raise RuntimeError(f"grompp warning count is {warning_count}, expected 0")
            if not em_summary["converged"]:
                raise RuntimeError("energy minimization did not report convergence")
            status = "PASS_EM_TECHNICAL"
            detail = "Packmol, strict grompp, energy minimization, and gmx check finished"
        else:
            status = "BUILT_NOT_EXECUTED"
            detail = "candidate inputs built; GROMACS EM not executed"

        metrics["technical_status"] = status
        (run_dir / "metrics.json").write_text(
            json.dumps(metrics, indent=2, ensure_ascii=False) + "\n"
        )
    except Exception as exc:
        detail = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        end = dt.datetime.now().astimezone().isoformat(timespec="seconds")
        write_run_record(
            run_dir / "RUN_RECORD.md",
            run_id,
            args.density,
            box_nm,
            args.packmol_seed,
            start,
            end,
            status,
            detail,
        )


if __name__ == "__main__":
    main()
