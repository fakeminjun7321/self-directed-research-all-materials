"""
기존 Li-O(FSI), Li-N(FSI) RDF에 더해 다음 추가 쌍의 RDF/CN을 계산한다.

- Li-N4 (Pyr13의 4차 질소; 양이온-양이온 거리)
- Li-Li (Li 응집/분산)
- NBT-NBT (FSI 음이온 간 거리)
- N4-NBT (Pyr+ 와 FSI- 간 거리)

5개 시스템(L1P1, L1P2, L2P1, L3P1, L1P3) 모두에 대해 50 ps xtc로 계산.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv
import os
import subprocess

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "02_Processed_Data" / "MD_Runs" / "50ps_Practice"
OUT = ROOT / "03_Analysis_Results" / "Extended_RDF"
RAW = OUT / "raw_xvg"

SYSTEMS = ["L1P1", "L1P2", "L2P1", "L3P1", "L1P3"]


@dataclass(frozen=True)
class Pair:
    key: str
    ref: str
    sel: str
    title: str
    rmax: float = 1.5


PAIRS = [
    Pair("li_n4", "name Li", "name N4", "Li-N4(Pyr+)"),
    Pair("li_li", "name Li", "name Li", "Li-Li"),
    Pair("nbt_nbt", "name NBT", "name NBT", "N(FSI)-N(FSI)"),
    Pair("n4_nbt", "name N4", "name NBT", "N4(Pyr+)-N(FSI)"),
]


def run(cmd: list[str], cwd: Path) -> None:
    env = os.environ.copy()
    env["GMX_MAXBACKUP"] = "-1"
    subprocess.run(cmd, cwd=cwd, env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def read_xvg(path: Path) -> np.ndarray:
    rows = []
    for line in path.read_text(errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith(("#", "@")):
            continue
        rows.append([float(v) for v in s.split()])
    return np.array(rows, dtype=float)


def ensure_rdf(label: str, pair: Pair) -> tuple[Path, Path]:
    work = RUNS / label
    rdf = RAW / f"{label}_rdf_{pair.key}.xvg"
    cn = RAW / f"{label}_cn_{pair.key}.xvg"
    if rdf.exists() and cn.exists():
        return rdf, cn
    RAW.mkdir(parents=True, exist_ok=True)
    cmd = [
        "gmx", "rdf",
        "-f", "md_50ps.xtc",
        "-s", "md_50ps.tpr",
        "-o", str(rdf),
        "-cn", str(cn),
        "-ref", pair.ref,
        "-sel", pair.sel,
        "-rmax", str(pair.rmax),
        "-bin", "0.01",
        "-xvg", "none",
    ]
    run(cmd, work)
    return rdf, cn


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    for sys in SYSTEMS:
        for pair in PAIRS:
            rdf_path, cn_path = ensure_rdf(sys, pair)
            rdf = read_xvg(rdf_path)
            cn = read_xvg(cn_path)
            peak_idx = np.argmax(rdf[10:, 1]) + 10  # r > 0.1 nm
            peak_r = rdf[peak_idx, 0]
            peak_g = rdf[peak_idx, 1]
            results.append({
                "system": sys,
                "pair": pair.title,
                "peak_r_nm": round(float(peak_r), 4),
                "peak_g": round(float(peak_g), 4),
            })
            print(f"{sys} {pair.title:25s} peak r={peak_r:.3f} nm  g={peak_g:.2f}")
    with (OUT / "extended_rdf_peaks.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["system", "pair", "peak_r_nm", "peak_g"])
        w.writeheader()
        for r in results:
            w.writerow(r)
    print(f"\nsaved: {(OUT / 'extended_rdf_peaks.csv').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
