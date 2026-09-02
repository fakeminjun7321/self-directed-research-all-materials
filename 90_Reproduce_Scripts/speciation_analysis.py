"""
Li+ 음이온 배위 환경(speciation) 분석.

각 frame에서 Li마다 첫 shell(Li-O 거리 ≤ R_CUT) 안에 들어오는 고유한 FSI- 분자 수를 센다.
- 0 FSI: Free Li+
- 1 FSI: CIP (contact ion pair)
- 2 FSI: AGG-I
- 3+ FSI: AGG-II
"""

from __future__ import annotations

from pathlib import Path
import csv

import numpy as np
import MDAnalysis as mda

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "02_Processed_Data" / "MD_Runs" / "50ps_Practice"
OUT = ROOT / "03_Analysis_Results" / "Speciation"
OUT.mkdir(parents=True, exist_ok=True)

SYSTEMS = ["L1P1", "L1P2", "L2P1", "L3P1", "L1P3"]
R_CUT = 0.33  # nm; Li-O(FSI) 첫 shell 컷오프 (RDF 1st minimum 부근)
LABELS = ["Free", "CIP", "AGG-I", "AGG-II"]


def classify(n_fsi: int) -> str:
    if n_fsi == 0:
        return "Free"
    if n_fsi == 1:
        return "CIP"
    if n_fsi == 2:
        return "AGG-I"
    return "AGG-II"


def analyse_system(label: str) -> dict:
    work = RUNS / label
    # tpr 2026 버전을 MDA가 아직 지원 안해서 gro/xtc 조합으로
    u = mda.Universe(str(work / "md_50ps.gro"), str(work / "md_50ps.xtc"))
    li = u.select_atoms("name Li")
    obt = u.select_atoms("name OBT")
    # FSI residue index = atom resid 처럼 동작; FSI 분자 id를 매핑
    fsi_resids = obt.resids  # 길이는 OBT 수, 4개당 같은 resid (FSI 1개)

    counts = {lbl: 0 for lbl in LABELS}
    total = 0

    # 거리 계산 — 모든 frame
    from MDAnalysis.lib.distances import distance_array

    for ts in u.trajectory:
        box = ts.dimensions  # Å, A B C alpha beta gamma
        # Li (Å) vs OBT (Å) 거리 행렬
        d = distance_array(li.positions, obt.positions, box=box) / 10.0  # nm
        mask = d < R_CUT  # (n_Li, n_OBT)
        for li_idx in range(len(li)):
            near = mask[li_idx]
            if not near.any():
                n = 0
            else:
                unique_fsi = np.unique(fsi_resids[near])
                n = len(unique_fsi)
            counts[classify(n)] += 1
            total += 1

    fractions = {k: counts[k] / total for k in LABELS}
    return {"system": label, "total_li_frames": total, **fractions}


def main() -> None:
    rows = []
    for sys in SYSTEMS:
        print(f"[{sys}] analysing ...", flush=True)
        row = analyse_system(sys)
        print("  ", {k: f"{row[k]:.3f}" for k in LABELS})
        rows.append(row)

    out_csv = OUT / "speciation_fractions.csv"
    with out_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["system", "total_li_frames"] + LABELS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"saved: {out_csv.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
