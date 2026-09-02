#!/usr/bin/env python3
"""Validate a generated candidate against source ordering and legacy parameters."""

from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re

PROJECT = Path(__file__).resolve().parents[2]
LEGACY_L2P2 = (
    PROJECT
    / "02_Processed_Data"
    / "MD_Runs"
    / "50ps_Practice"
    / "L2P2"
    / "topol.top"
)
USED_MOLECULES = ("Li+", "c3c1pyrr+", "fsi-")
USED_TYPES = ("Li", "N4", "C1", "C2", "H1", "HC", "CT", "FSI", "SBT", "NBT", "OBT")


def data_lines(text: str):
    section = ""
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped.strip("[] ").lower()
            yield ("__section__", section)
        elif stripped and not stripped.startswith((";", "!", "#")):
            yield (section, stripped.split())


def normalized_token(token: str) -> str:
    try:
        value = Decimal(token)
    except InvalidOperation:
        return token
    if value == 0:
        return "0"
    return str(value.normalize())


def normalized_tokens(tokens: list[str]) -> list[str]:
    return [normalized_token(token) for token in tokens]


def parse_atomtypes(text: str) -> dict[str, list[str]]:
    output: dict[str, list[str]] = {}
    for section, payload in data_lines(text):
        if section == "atomtypes":
            assert isinstance(payload, list)
            output[payload[0]] = normalized_tokens(payload[1:])
    return output


def parse_defaults(text: str) -> list[str]:
    for section, payload in data_lines(text):
        if section == "defaults":
            assert isinstance(payload, list)
            return normalized_tokens(payload)
    raise ValueError("missing defaults")


def parse_molecules(text: str) -> tuple[dict[str, dict[str, list[list[str]]]], dict[str, int]]:
    definitions: dict[str, dict[str, list[list[str]]]] = {}
    counts: dict[str, int] = {}
    section = ""
    current: str | None = None
    need_name = False
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped.strip("[] ").lower()
            need_name = section == "moleculetype"
            continue
        if not stripped or stripped.startswith((";", "!", "#")):
            continue
        parts = stripped.split()
        if section == "moleculetype" and need_name:
            current = parts[0]
            definitions.setdefault(current, {"moleculetype": [normalized_tokens(parts)]})
            need_name = False
        elif section == "molecules":
            counts[parts[0]] = int(parts[1])
        elif current and section in {"atoms", "bonds", "constraints", "pairs", "angles", "dihedrals"}:
            if section == "atoms":
                # Ignore residue and coordinate atom labels; retain topology type, charge, and indices.
                reduced = [parts[0], parts[1], parts[2], parts[5], parts[6]]
                definitions[current].setdefault(section, []).append(normalized_tokens(reduced))
            else:
                definitions[current].setdefault(section, []).append(normalized_tokens(parts))
    return definitions, counts


def parse_xyz_elements(path: Path) -> list[str]:
    lines = path.read_text().splitlines()
    count = int(lines[0].strip())
    elements = [line.split()[0] for line in lines[2 : 2 + count]]
    if len(elements) != count:
        raise ValueError(f"XYZ atom count mismatch: {path}")
    return elements


def gro_residue_sequence(path: Path) -> list[str]:
    lines = path.read_text().splitlines()
    atom_count = int(lines[1].strip())
    atoms = lines[2 : 2 + atom_count]
    sequence: list[str] = []
    last_id: str | None = None
    for line in atoms:
        residue_id = line[:5]
        if residue_id != last_id:
            sequence.append(line[5:10].strip())
            last_id = residue_id
    return sequence


def molecule_charge_sums(text: str) -> dict[str, float]:
    definitions, _counts = parse_molecules(text)
    return {
        molecule: sum(float(atom[-1]) for atom in sections.get("atoms", []))
        for molecule, sections in definitions.items()
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    input_dir = run_dir / "input"

    scaled_text = (input_dir / "topol.top").read_text()
    full_charge_path = input_dir / "field_full_charge_REFERENCE_ONLY.top"
    if not full_charge_path.exists():
        full_charge_path = input_dir / "field.top"
    field_text = full_charge_path.read_text()
    legacy_text = LEGACY_L2P2.read_text()
    scaled_defs, scaled_counts = parse_molecules(scaled_text)
    legacy_defs, legacy_counts = parse_molecules(legacy_text)
    scaled_types = parse_atomtypes(scaled_text)
    legacy_types = parse_atomtypes(legacy_text)

    expected_xyz = (
        parse_xyz_elements(input_dir / "Li_pack.xyz") * 50
        + parse_xyz_elements(input_dir / "c3c1pyrr_pack.xyz") * 50
        + parse_xyz_elements(input_dir / "fsi_pack.xyz") * 100
    )
    actual_xyz = parse_xyz_elements(input_dir / "simbox.xyz")
    residue_sequence = gro_residue_sequence(input_dir / "initial.gro")
    expected_residues = ["Li"] * 50 + ["c3c"] * 50 + ["fsi"] * 100

    scaled_charges = molecule_charge_sums(scaled_text)
    full_charges = molecule_charge_sums(field_text)
    charge_factor_ok = all(
        abs(scaled_charges[name] - 0.75 * full_charges[name]) < 1e-8
        for name in USED_MOLECULES
    )

    checks = {
        "defaults_equal_legacy": parse_defaults(scaled_text) == parse_defaults(legacy_text),
        "active_atomtypes_equal_legacy": all(
            scaled_types.get(name) == legacy_types.get(name) for name in USED_TYPES
        ),
        "active_molecule_parameters_equal_legacy": all(
            scaled_defs.get(name) == legacy_defs.get(name) for name in USED_MOLECULES
        ),
        "molecule_counts_equal_legacy": all(
            scaled_counts.get(name) == legacy_counts.get(name) for name in USED_MOLECULES
        ),
        "molecule_counts_expected": scaled_counts == {"Li+": 50, "c3c1pyrr+": 50, "fsi-": 100},
        "full_to_scaled_charge_factor_0_75": charge_factor_ok,
        "scaled_molecule_charges_expected": all(
            abs(scaled_charges[name] - expected) < 1e-8
            for name, expected in {"Li+": 0.75, "c3c1pyrr+": 0.75, "fsi-": -0.75}.items()
        ),
        "system_total_charge_zero": abs(
            sum(scaled_charges[name] * scaled_counts[name] for name in USED_MOLECULES)
        ) < 1e-8,
        "packmol_element_order_exact": actual_xyz == expected_xyz,
        "packmol_atom_count_2300": len(actual_xyz) == 2300,
        "gro_residue_order_exact": residue_sequence == expected_residues,
        "gro_residue_counts": Counter(residue_sequence) == Counter(expected_residues),
    }

    report = {
        "run_id": run_dir.name,
        "legacy_reference": str(LEGACY_L2P2.relative_to(PROJECT)),
        "scaled_molecule_charges": scaled_charges,
        "full_molecule_charges": full_charges,
        "checks": checks,
        "all_passed": all(checks.values()),
        "physics_status": "NOT_VERIFIED",
    }
    output = args.output or (run_dir / "validation.json")
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not report["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
