#!/usr/bin/env python3
"""Recompute composition, density, and cubic-box constraints using stdlib only."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

DALTON_KG = 1.66053906660e-27
MASS_LI = 6.941
MASS_PYR13 = 128.239
MASS_FSI = 180.124
IL_PAIR_KG_PER_MOL = (MASS_PYR13 + MASS_FSI) / 1000.0

SYSTEMS = {
    "L1P1": (25, 25, 50, 5.28770),
    "L1P2": (25, 50, 75, 6.41140),
    "L2P1": (50, 25, 75, 5.64600),
    "L3P1": (75, 25, 100, 5.96390),
    "L1P3": (25, 75, 100, 7.23840),
    "L1P1x2": (50, 50, 100, None),
}


def total_mass_u(li: int, pyr: int, fsi: int) -> float:
    return li * MASS_LI + pyr * MASS_PYR13 + fsi * MASS_FSI


def atom_count(li: int, pyr: int, fsi: int) -> int:
    return li + 27 * pyr + 9 * fsi


def density_kg_m3(mass_u: float, box_nm: float) -> float:
    return mass_u * DALTON_KG / (box_nm * 1e-9) ** 3


def box_nm_for_density(mass_u: float, density: float) -> float:
    return (mass_u * DALTON_KG / density) ** (1.0 / 3.0) * 1e9


def rows(cutoff_nm: float) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for label, (li, pyr, fsi, current_box) in SYSTEMS.items():
        mass = total_mass_u(li, pyr, fsi)
        row: dict[str, str] = {
            "system_id": label,
            "li_count": str(li),
            "pyr13_count": str(pyr),
            "fsi_count": str(fsi),
            "atom_count": str(atom_count(li, pyr, fsi)),
            "total_mass_u": f"{mass:.3f}",
            "molality_mol_kg": f"{(li / pyr) / IL_PAIR_KG_PER_MOL:.3f}",
            "x_lifsi": f"{li / (li + pyr):.3f}",
            "current_box_nm": "" if current_box is None else f"{current_box:.5f}",
            "current_density_kg_m3": "" if current_box is None else f"{density_kg_m3(mass, current_box):.2f}",
        }
        for density in (1200, 1400, 1500, 1550):
            box = box_nm_for_density(mass, density)
            row[f"box_at_{density}_kg_m3_nm"] = f"{box:.6f}"
            row[f"box_at_{density}_cutoff_ok"] = str(box > 2.0 * cutoff_nm)
        out.append(row)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cutoff-nm", type=float, default=1.2)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    calculated = rows(args.cutoff_nm)
    fieldnames = list(calculated[0])
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(calculated)
    else:
        writer = csv.DictWriter(__import__("sys").stdout, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(calculated)


if __name__ == "__main__":
    main()

