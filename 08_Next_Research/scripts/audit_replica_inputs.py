#!/usr/bin/env python3
"""Fail-closed audit for three Packmol-built, not-yet-executed replicas."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any


PROJECT = Path(__file__).resolve().parents[2]
NEXT = PROJECT / "08_Next_Research"
RUNS = NEXT / "04_Runs"
HANDOFF = PROJECT / "07_Handoff"
SCHEMA = "replica-input-audit-v3"

VALIDATOR_PATH = NEXT / "scripts" / "validate_candidate.py"
VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "replica_candidate_validator", VALIDATOR_PATH
)
if VALIDATOR_SPEC is None or VALIDATOR_SPEC.loader is None:
    raise RuntimeError("cannot load validate_candidate.py")
candidate_validator = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(candidate_validator)


class AuditError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evidence(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AuditError(f"required file is missing: {path}")
    return {"sha256": sha256(path), "size_bytes": path.stat().st_size}


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(
            path.read_text(),
            parse_constant=lambda value: (_ for _ in ()).throw(
                AuditError(f"non-finite JSON constant in {path}: {value}")
            ),
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AuditError(f"expected JSON object: {path}")
    return payload


def finite(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise AuditError(f"{label} is not numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise AuditError(f"{label} is not numeric") from exc
    if not math.isfinite(number):
        raise AuditError(f"{label} is not finite")
    return number


def parse_single_seed_line(text: str, label: str) -> int:
    matches = re.findall(r"^\s*seed\s+([+-]?\d+)\s*$", text, re.MULTILINE | re.IGNORECASE)
    if len(matches) != 1:
        raise AuditError(f"{label}: expected exactly one Packmol seed line")
    seed = int(matches[0])
    if not 1 <= seed <= 2_147_483_647:
        raise AuditError(f"{label}: Packmol seed is outside the reproducible range")
    return seed


def parse_single_observed_seed(text: str, label: str) -> int:
    matches = re.findall(r"Seed for random number generator:\s*([+-]?\d+)", text)
    if len(matches) != 1:
        raise AuditError(f"{label}: expected exactly one observed Packmol seed")
    seed = int(matches[0])
    if not 1 <= seed <= 2_147_483_647:
        raise AuditError(f"{label}: observed Packmol seed is outside the reproducible range")
    return seed


def validate_checksum_file(run_dir: Path) -> dict[str, dict[str, Any]]:
    checksum_path = run_dir / "INPUT_SHA256SUMS"
    seen: dict[str, dict[str, Any]] = {}
    for line_number, raw in enumerate(checksum_path.read_text().splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64})  (input/[^\s]+)", raw)
        if match is None:
            raise AuditError(f"{run_dir.name}: malformed checksum line {line_number}")
        recorded, relative = match.groups()
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise AuditError(f"{run_dir.name}: unsafe checksum path {relative}")
        path = run_dir / candidate
        actual = evidence(path)
        if actual["sha256"] != recorded:
            raise AuditError(f"{run_dir.name}: checksum mismatch for {relative}")
        if relative in seen:
            raise AuditError(f"{run_dir.name}: duplicate checksum entry {relative}")
        seen[relative] = actual
    required = {"input/initial.gro", "input/topol.top", "input/em.mdp", "input/pack.inp"}
    if not required.issubset(seen):
        raise AuditError(f"{run_dir.name}: required input checksum entries are missing")
    return seen


def read_status(record: str, chain_id: str) -> str:
    match = re.search(r"^- Technical status:\s*(\S+)\s*$", record, re.MULTILINE)
    if match is None:
        raise AuditError(f"{chain_id}: technical status is missing")
    return match.group(1)


def validate_gro(path: Path, chain_id: str) -> None:
    lines = path.read_text().splitlines()
    if len(lines) != 2303 or int(lines[1].strip()) != 2300:
        raise AuditError(f"{chain_id}: GRO does not contain exactly 2300 atom rows")
    for index, line in enumerate(lines[2:2302], 1):
        if len(line) < 44:
            raise AuditError(f"{chain_id}: short GRO atom row {index}")
        try:
            coordinates = tuple(float(line[start : start + 8]) for start in (20, 28, 36))
        except ValueError as exc:
            raise AuditError(f"{chain_id}: invalid GRO coordinates at atom {index}") from exc
        if not all(math.isfinite(value) for value in coordinates):
            raise AuditError(f"{chain_id}: non-finite GRO coordinates at atom {index}")
    try:
        box = [float(value) for value in lines[-1].split()]
    except ValueError as exc:
        raise AuditError(f"{chain_id}: invalid GRO box") from exc
    if len(box) != 3 or not all(math.isfinite(value) and value > 0 for value in box):
        raise AuditError(f"{chain_id}: GRO box must be three positive finite values")


def validate_simbox_to_gro(input_dir: Path, chain_id: str) -> float:
    xyz_lines = (input_dir / "simbox.xyz").read_text().splitlines()
    gro_lines = (input_dir / "initial.gro").read_text().splitlines()
    try:
        xyz_count = int(xyz_lines[0].strip())
        gro_count = int(gro_lines[1].strip())
    except (IndexError, ValueError) as exc:
        raise AuditError(f"{chain_id}: malformed XYZ/GRO count") from exc
    if xyz_count != 2300 or gro_count != 2300:
        raise AuditError(f"{chain_id}: XYZ/GRO count mismatch")
    if len(xyz_lines) < 2302 or len(gro_lines) != 2303:
        raise AuditError(f"{chain_id}: incomplete XYZ/GRO coordinate rows")
    max_error = 0.0
    for index, (xyz_line, gro_line) in enumerate(
        zip(xyz_lines[2:2302], gro_lines[2:2302]), 1
    ):
        parts = xyz_line.split()
        if len(parts) < 4:
            raise AuditError(f"{chain_id}: malformed XYZ row {index}")
        try:
            xyz_angstrom = tuple(float(value) for value in parts[1:4])
            gro_angstrom = tuple(
                float(gro_line[start : start + 8]) * 10.0 for start in (20, 28, 36)
            )
        except ValueError as exc:
            raise AuditError(f"{chain_id}: invalid XYZ/GRO coordinates at atom {index}") from exc
        if not all(math.isfinite(value) for value in xyz_angstrom + gro_angstrom):
            raise AuditError(f"{chain_id}: non-finite XYZ/GRO coordinates at atom {index}")
        max_error = max(
            max_error,
            *(abs(a - b) for a, b in zip(xyz_angstrom, gro_angstrom)),
        )
    if max_error > 0.006:
        raise AuditError(
            f"{chain_id}: simbox.xyz and initial.gro differ by {max_error:.6f} A"
        )
    return max_error


def validate_packmol_completion(text: str, chain_id: str) -> dict[str, Any]:
    versions = re.findall(r"\bVersion\s+([0-9]+(?:\.[0-9]+)+)", text)
    successes = re.findall(r"^\s*Success!\s*$", text, re.MULTILINE)
    targets = re.findall(
        r"Maximum violation of target distance:\s*([-+0-9.eE]+)", text
    )
    constraints = re.findall(
        r"Maximum violation of the constraints:\s*([-+0-9.eE]+)", text
    )
    if len(versions) != 1 or len(successes) != 1 or not targets or not constraints:
        raise AuditError(f"{chain_id}: Packmol completion evidence is missing or ambiguous")
    target = finite(targets[-1], f"{chain_id} final target violation")
    constraint = finite(constraints[-1], f"{chain_id} final constraint violation")
    if not 0.0 <= target <= 0.01 or not 0.0 <= constraint <= 0.01:
        raise AuditError(f"{chain_id}: Packmol final violation is outside 0..0.01")
    return {
        "version": versions[0],
        "success_markers": 1,
        "final_target_distance_violation": target,
        "final_constraint_violation": constraint,
    }


def validate_scientific_inputs(run_dir: Path) -> dict[str, bool]:
    input_dir = run_dir / "input"
    scaled_text = (input_dir / "topol.top").read_text()
    full_text = (input_dir / "field_full_charge_REFERENCE_ONLY.top").read_text()
    legacy_text = candidate_validator.LEGACY_L2P2.read_text()
    scaled_defs, scaled_counts = candidate_validator.parse_molecules(scaled_text)
    legacy_defs, legacy_counts = candidate_validator.parse_molecules(legacy_text)
    scaled_types = candidate_validator.parse_atomtypes(scaled_text)
    legacy_types = candidate_validator.parse_atomtypes(legacy_text)
    expected_xyz = (
        candidate_validator.parse_xyz_elements(input_dir / "Li_pack.xyz") * 50
        + candidate_validator.parse_xyz_elements(input_dir / "c3c1pyrr_pack.xyz") * 50
        + candidate_validator.parse_xyz_elements(input_dir / "fsi_pack.xyz") * 100
    )
    actual_xyz = candidate_validator.parse_xyz_elements(input_dir / "simbox.xyz")
    residues = candidate_validator.gro_residue_sequence(input_dir / "initial.gro")
    expected_residues = ["Li"] * 50 + ["c3c"] * 50 + ["fsi"] * 100
    scaled_charges = candidate_validator.molecule_charge_sums(scaled_text)
    full_charges = candidate_validator.molecule_charge_sums(full_text)
    checks = {
        "defaults_equal_legacy": candidate_validator.parse_defaults(scaled_text)
        == candidate_validator.parse_defaults(legacy_text),
        "active_atomtypes_equal_legacy": all(
            scaled_types.get(name) == legacy_types.get(name)
            for name in candidate_validator.USED_TYPES
        ),
        "active_molecule_parameters_equal_legacy": all(
            scaled_defs.get(name) == legacy_defs.get(name)
            for name in candidate_validator.USED_MOLECULES
        ),
        "molecule_counts_equal_legacy": all(
            scaled_counts.get(name) == legacy_counts.get(name)
            for name in candidate_validator.USED_MOLECULES
        ),
        "molecule_counts_expected": scaled_counts
        == {"Li+": 50, "c3c1pyrr+": 50, "fsi-": 100},
        "full_to_scaled_charge_factor_0_75": all(
            abs(scaled_charges[name] - 0.75 * full_charges[name]) < 1e-8
            for name in candidate_validator.USED_MOLECULES
        ),
        "scaled_molecule_charges_expected": all(
            abs(scaled_charges[name] - expected) < 1e-8
            for name, expected in {"Li+": 0.75, "c3c1pyrr+": 0.75, "fsi-": -0.75}.items()
        ),
        "system_total_charge_zero": abs(
            sum(scaled_charges[name] * scaled_counts[name] for name in candidate_validator.USED_MOLECULES)
        )
        < 1e-8,
        "packmol_element_order_exact": actual_xyz == expected_xyz,
        "packmol_atom_count_2300": len(actual_xyz) == 2300,
        "gro_residue_order_exact": residues == expected_residues,
        "gro_residue_counts": Counter(residues) == Counter(expected_residues),
        "em_mdp_matches_canonical": sha256(input_dir / "em.mdp")
        == sha256(PROJECT / "07_Handoff" / "CILE_MD_Handoff_v0_DRAFT" / "mdp" / "01_em_strict.mdp"),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise AuditError(f"{run_dir.name}: scientific input checks failed: {failed}")
    return checks


def load_run(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    try:
        run_dir.relative_to(RUNS.resolve())
    except ValueError as exc:
        raise AuditError(f"replica run is outside 04_Runs: {run_dir}") from exc
    metrics_path = run_dir / "metrics.json"
    record_path = run_dir / "RUN_RECORD.md"
    commands_path = run_dir / "commands.log"
    checksums_path = run_dir / "INPUT_SHA256SUMS"
    packmol_path = run_dir / "input" / "pack.inp"
    initial_path = run_dir / "input" / "initial.gro"
    topology_path = run_dir / "input" / "topol.top"
    em_mdp_path = run_dir / "input" / "em.mdp"
    for path in (
        metrics_path,
        record_path,
        commands_path,
        checksums_path,
        packmol_path,
        initial_path,
        topology_path,
        em_mdp_path,
    ):
        if not path.is_file():
            raise AuditError(f"{run_dir.name}: required file is missing: {path.name}")

    metrics = read_json(metrics_path)
    if metrics.get("run_id") != run_dir.name:
        raise AuditError(f"{run_dir.name}: metrics run_id mismatch")
    if metrics.get("physics_status") != "NOT_VERIFIED":
        raise AuditError(f"{run_dir.name}: unexpected physics status")
    if metrics.get("atom_count") != 2300:
        raise AuditError(f"{run_dir.name}: metrics atom count mismatch")
    if not math.isclose(finite(metrics.get("charge_scaling_retained"), "charge scale"), 0.75):
        raise AuditError(f"{run_dir.name}: charge scale mismatch")

    requested = metrics.get("packmol_seed_requested")
    observed = metrics.get("packmol_seed_observed")
    if isinstance(requested, bool) or not isinstance(requested, int):
        raise AuditError(f"{run_dir.name}: requested Packmol seed is invalid")
    if isinstance(observed, bool) or not isinstance(observed, int):
        raise AuditError(f"{run_dir.name}: observed Packmol seed is invalid")
    if observed != requested:
        raise AuditError(f"{run_dir.name}: requested/observed metrics seed mismatch")
    input_seed = parse_single_seed_line(packmol_path.read_text(), run_dir.name)
    commands_text = commands_path.read_text()
    log_seed = parse_single_observed_seed(commands_text, run_dir.name)
    if not (requested == input_seed == log_seed):
        raise AuditError(f"{run_dir.name}: Packmol seed provenance mismatch")
    packmol_completion = validate_packmol_completion(commands_text, run_dir.name)

    record = record_path.read_text()
    record_status = read_status(record, run_dir.name)
    if record_status != "BUILT_NOT_EXECUTED":
        raise AuditError(f"{run_dir.name}: run is not in BUILT_NOT_EXECUTED state")
    metrics_status = metrics.get("technical_status")
    if metrics_status is not None and metrics_status != record_status:
        raise AuditError(f"{run_dir.name}: metrics/record technical status mismatch")
    forbidden_suffixes = {".tpr", ".edr", ".trr", ".xtc", ".cpt"}
    forbidden = [
        path
        for path in run_dir.rglob("*")
        if path.is_file()
        and "input" not in path.relative_to(run_dir).parts
        and (path.suffix.lower() in forbidden_suffixes or path.suffix.lower() == ".log")
        and path != commands_path
    ]
    if forbidden or (run_dir / "equilibration").exists():
        raise AuditError(f"{run_dir.name}: MD/EM execution artifacts already exist")
    if re.search(
        r"^\$\s+.*(?:^|\s)(?:\S*/)?gmx(?:_mpi)?\s+(?:grompp|mdrun)\b",
        commands_text,
        re.MULTILINE,
    ):
        raise AuditError(f"{run_dir.name}: commands log contains EM/MD execution")
    validate_gro(initial_path, run_dir.name)
    coordinate_error = validate_simbox_to_gro(run_dir / "input", run_dir.name)
    scientific_checks = validate_scientific_inputs(run_dir)

    checksum_evidence = validate_checksum_file(run_dir)
    return {
        "chain_id": run_dir.name,
        "packmol_seed": requested,
        "requested_density_kg_m3": finite(
            metrics.get("requested_density_kg_m3"), f"{run_dir.name} requested density"
        ),
        "initial_density_kg_m3": finite(
            metrics.get("initial_density_kg_m3"), f"{run_dir.name} initial density"
        ),
        "atom_count": 2300,
        "technical_status": "BUILT_NOT_EXECUTED",
        "packmol_completion": packmol_completion,
        "scientific_input_checks": scientific_checks,
        "packmol_to_gro_max_abs_error_angstrom": coordinate_error,
        "initial_gro": evidence(initial_path),
        "simbox_xyz": evidence(run_dir / "input" / "simbox.xyz"),
        "topol_top": evidence(topology_path),
        "em_mdp": evidence(em_mdp_path),
        "source_evidence": {
            "metrics.json": evidence(metrics_path),
            "RUN_RECORD.md": evidence(record_path),
            "commands.log": evidence(commands_path),
            "INPUT_SHA256SUMS": evidence(checksums_path),
            "input/pack.inp": evidence(packmol_path),
            "input/simbox.xyz": evidence(run_dir / "input" / "simbox.xyz"),
            "input/Li.zmat": evidence(run_dir / "input" / "Li.zmat"),
            "input/c3c1pyrr.zmat": evidence(run_dir / "input" / "c3c1pyrr.zmat"),
            "input/fsi.zmat": evidence(run_dir / "input" / "fsi.zmat"),
            "input/il.ff": evidence(run_dir / "input" / "il.ff"),
            "fftool": evidence(PROJECT / "90_Reproduce_Scripts" / "tools" / "fftool" / "fftool"),
        },
        "validated_checksum_entries": checksum_evidence,
    }


def validate_set(chains: list[dict[str, Any]]) -> None:
    if len(chains) != 3:
        raise AuditError("exactly three replica inputs are required")
    chain_ids = [chain["chain_id"] for chain in chains]
    seeds = [chain["packmol_seed"] for chain in chains]
    coordinates = [chain["initial_gro"]["sha256"] for chain in chains]
    packmol_outputs = [chain["simbox_xyz"]["sha256"] for chain in chains]
    topologies = [chain["topol_top"]["sha256"] for chain in chains]
    em_mdps = [chain["em_mdp"]["sha256"] for chain in chains]
    requested = [chain["requested_density_kg_m3"] for chain in chains]
    initial = [chain["initial_density_kg_m3"] for chain in chains]
    versions = [chain["packmol_completion"]["version"] for chain in chains]
    if len(set(chain_ids)) != 3:
        raise AuditError("replica chain IDs are not unique")
    if len(set(seeds)) != 3:
        raise AuditError("Packmol seeds are not unique")
    if len(set(coordinates)) != 3:
        raise AuditError("initial coordinate hashes are not unique")
    if len(set(packmol_outputs)) != 3:
        raise AuditError("direct Packmol output hashes are not unique")
    if len(set(topologies)) != 1:
        raise AuditError("replica topology hashes differ")
    if len(set(em_mdps)) != 1:
        raise AuditError("replica EM MDP hashes differ")
    if len(set(versions)) != 1:
        raise AuditError("replica Packmol versions differ")
    common_source_keys = (
        "input/Li.zmat",
        "input/c3c1pyrr.zmat",
        "input/fsi.zmat",
        "input/il.ff",
        "fftool",
    )
    for key in common_source_keys:
        hashes = [chain["source_evidence"][key]["sha256"] for chain in chains]
        if len(set(hashes)) != 1:
            raise AuditError(f"replica source hashes differ for {key}")
    if max(requested) - min(requested) > 1.0e-9:
        raise AuditError("requested replica densities differ")
    if max(initial) - min(initial) > 1.0e-9:
        raise AuditError("initial replica densities differ")


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def write_once(path: Path, payload: dict[str, Any]) -> None:
    resolved = path.resolve()
    for protected in (RUNS.resolve(), HANDOFF.resolve()):
        try:
            resolved.relative_to(protected)
        except ValueError:
            continue
        raise AuditError(f"refusing to write audit output under {protected}")
    content = canonical_bytes(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise AuditError(f"immutable audit differs: {path}")
        return
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    except FileExistsError:
        if path.read_bytes() != content:
            raise AuditError(f"audit was concurrently created with different content: {path}")
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dirs", type=Path, nargs=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    chains = sorted((load_run(path) for path in args.run_dirs), key=lambda item: item["chain_id"])
    validate_set(chains)
    payload = {
        "schema_version": SCHEMA,
        "technical_status": "PASS_PACKMOL_ARTIFACTS",
        "md_execution_status": "NOT_EXECUTED",
        "physics_status": "NOT_EVALUATED",
        "replica_count": 3,
        "packmol_seeds_unique": True,
        "initial_coordinate_hashes_unique": True,
        "direct_packmol_output_hashes_unique": True,
        "topology_hashes_identical": True,
        "em_mdp_hashes_identical": True,
        "chains": chains,
        "not_verified": [
            "same-seed byte-exact Packmol reproduction",
            "energy minimization",
            "independent GROMACS velocity seeds",
            "NVT and NPT execution",
            "replica stationarity and convergence",
            "equilibrium and production readiness",
        ],
    }
    write_once(args.output, payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (AuditError, KeyError, OSError, ValueError) as exc:
        print(f"replica input audit failed safely: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
