"""
각 Li 주변 FSI O원자 개수의 시간/Li-별 분포를 계산.
평균 CN뿐 아니라 분포(histogram)를 보여줘서 균질한 4배위인지 다양한 배위가 섞여있는지 확인.
"""

from __future__ import annotations

from pathlib import Path
import csv

import numpy as np
import MDAnalysis as mda
from MDAnalysis.lib.distances import distance_array

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "02_Processed_Data" / "MD_Runs" / "50ps_Practice"
OUT = ROOT / "03_Analysis_Results" / "CN_Distribution"
OUT.mkdir(parents=True, exist_ok=True)

SYSTEMS = ["L1P1", "L1P2", "L2P1", "L3P1", "L1P3"]
R_CUT = 0.33  # nm


def histogram_system(label: str) -> dict:
    work = RUNS / label
    u = mda.Universe(str(work / "md_50ps.gro"), str(work / "md_50ps.xtc"))
    li = u.select_atoms("name Li")
    obt = u.select_atoms("name OBT")
    nbt = u.select_atoms("name NBT")

    o_counts: list[int] = []
    n_counts: list[int] = []

    for ts in u.trajectory:
        box = ts.dimensions
        d_o = distance_array(li.positions, obt.positions, box=box) / 10.0
        d_n = distance_array(li.positions, nbt.positions, box=box) / 10.0
        o_counts.extend((d_o < R_CUT).sum(axis=1).tolist())
        n_counts.extend((d_n < 0.55).sum(axis=1).tolist())  # Li-N 1st shell ≈ 0.55 nm

    o_hist = np.bincount(o_counts, minlength=12)
    n_hist = np.bincount(n_counts, minlength=12)
    return {
        "system": label,
        "o_hist": o_hist.tolist(),
        "n_hist": n_hist.tolist(),
        "o_mean": float(np.mean(o_counts)),
        "o_std": float(np.std(o_counts)),
        "n_mean": float(np.mean(n_counts)),
        "n_std": float(np.std(n_counts)),
    }


def main() -> None:
    rows = []
    for sys in SYSTEMS:
        print(f"[{sys}]", flush=True)
        rows.append(histogram_system(sys))

    out_csv = OUT / "cn_distribution.csv"
    with out_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["system", "type", "mean", "std"] + [f"n={i}" for i in range(12)])
        for r in rows:
            w.writerow([r["system"], "Li-O(FSI)", round(r["o_mean"], 3), round(r["o_std"], 3)] + r["o_hist"])
            w.writerow([r["system"], "Li-N(FSI)", round(r["n_mean"], 3), round(r["n_std"], 3)] + r["n_hist"])
    print(f"saved: {out_csv.relative_to(ROOT)}")
    for r in rows:
        print(f"  {r['system']}: Li-O CN mean={r['o_mean']:.2f}±{r['o_std']:.2f}, "
              f"Li-N CN mean={r['n_mean']:.2f}±{r['n_std']:.2f}")


if __name__ == "__main__":
    main()
