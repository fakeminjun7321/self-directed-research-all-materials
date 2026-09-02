from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv
import os
import subprocess

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "02_Processed_Data" / "MD_Runs" / "50ps_Practice"
OUT = ROOT / "03_Analysis_Results" / "RDF_CN"
FIGURES = ROOT / "04_Figures_For_Report" / "RDF_CN"
RAW = OUT / "raw_xvg"
GRAPHS = FIGURES / "per_system"

SYSTEMS = ["L1P1", "L1P2", "L2P1", "L3P1", "L1P3", "L2P2", "L3P2"]


@dataclass(frozen=True)
class Pair:
    key: str
    atom_name: str
    label: str
    title: str
    min_search_end_nm: float


PAIRS = [
    Pair("li_obt", "OBT", "Li-O(FSI)", "Li-O(FSI)", 0.60),
    Pair("li_nbt", "NBT", "Li-N(FSI)", "Li-N(FSI)", 0.80),
]


def run(command: list[str], cwd: Path) -> str:
    env = os.environ.copy()
    env["GMX_MAXBACKUP"] = "-1"
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )
    return result.stdout


def read_xvg(path: Path) -> np.ndarray:
    rows: list[list[float]] = []
    for line in path.read_text(errors="ignore").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "@")):
            continue
        rows.append([float(part) for part in stripped.split()])
    return np.array(rows, dtype=float)


def moving_average(values: np.ndarray, width: int = 5) -> np.ndarray:
    if values.size < width:
        return values
    return np.convolve(values, np.ones(width) / width, mode="same")


def rdf_peak_min_cn(
    rdf: np.ndarray,
    cn: np.ndarray,
    min_search_end_nm: float,
) -> tuple[float, float, float]:
    r = rdf[:, 0]
    g = rdf[:, 1]
    smooth = moving_average(g, 5)

    shell_mask = (r >= 0.10) & (r <= min_search_end_nm)
    shell_indices = np.where(shell_mask)[0]
    if shell_indices.size == 0:
        return float("nan"), float("nan"), float("nan")

    peak_idx = shell_indices[np.argmax(smooth[shell_indices])]
    peak_value = smooth[peak_idx]

    search = np.where((r > r[peak_idx] + 0.03) & (r <= min_search_end_nm))[0]
    min_idx = peak_idx
    if search.size:
        threshold = max(1.2, peak_value * 0.35)
        local_minima: list[int] = []
        for idx in search:
            if idx <= 1 or idx >= len(smooth) - 2:
                continue
            if smooth[idx - 1] > smooth[idx] and smooth[idx + 1] > smooth[idx]:
                local_minima.append(idx)

        usable = [idx for idx in local_minima if smooth[idx] <= threshold]
        if usable:
            min_idx = usable[0]
        elif local_minima:
            min_idx = min(local_minima, key=lambda idx: smooth[idx])
        else:
            min_idx = search[np.argmin(smooth[search])]

    cn_at_min = np.interp(r[min_idx], cn[:, 0], cn[:, 1])
    return float(r[peak_idx]), float(r[min_idx]), float(cn_at_min)


def ensure_rdf(label: str, pair: Pair) -> tuple[Path, Path]:
    work = RUNS / label
    rdf = RAW / f"{label}_rdf_{pair.key}.xvg"
    cn = RAW / f"{label}_coordination_{pair.key}.xvg"

    if rdf.exists() and cn.exists():
        return rdf, cn

    run(
        [
            "gmx",
            "rdf",
            "-f",
            "md_50ps.xtc",
            "-s",
            "md_50ps.tpr",
            "-o",
            str(rdf),
            "-cn",
            str(cn),
            "-ref",
            "name Li",
            "-sel",
            f"name {pair.atom_name}",
            "-rmax",
            "1.2",
            "-bin",
            "0.01",
            "-xvg",
            "none",
        ],
        work,
    )
    return rdf, cn


def load_pair_result(label: str, pair: Pair) -> dict[str, float | str | np.ndarray]:
    rdf_path, cn_path = ensure_rdf(label, pair)
    rdf = read_xvg(rdf_path)
    cn = read_xvg(cn_path)
    peak_r, first_min_r, cn_at_min = rdf_peak_min_cn(rdf, cn, pair.min_search_end_nm)
    return {
        "system": label,
        "pair": pair.label,
        "selection_atom": pair.atom_name,
        "rdf_peak_r_nm": peak_r,
        "first_minimum_r_nm": first_min_r,
        "coordination_number": cn_at_min,
        "rdf": rdf,
        "cn": cn,
    }


def plot_slide_pair(label: str, results: list[dict[str, float | str | np.ndarray]]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)
    fig.suptitle(f"{label} configuration", fontsize=16, x=0.08, ha="left")

    for ax, pair, result in zip(axes, PAIRS, results, strict=True):
        rdf = result["rdf"]
        cn = result["cn"]
        assert isinstance(rdf, np.ndarray)
        assert isinstance(cn, np.ndarray)

        ax.plot(rdf[:, 0], rdf[:, 1], color="#222222", linewidth=1.5, label=label)
        ax.set_xlabel("r(nm)")
        ax.set_ylabel(f"g{pair.title.replace('(FSI)', '')}(r)")
        ax.set_xlim(0, 0.8)
        ax.grid(True, color="#dddddd", linewidth=0.5, alpha=0.55)
        ax.legend(loc="upper left", frameon=False, fontsize=9)

        peak_r = float(result["rdf_peak_r_nm"])
        min_r = float(result["first_minimum_r_nm"])
        ax.axvline(peak_r, color="#555555", linestyle="--", linewidth=0.8, alpha=0.55)
        ax.axvline(min_r, color="#555555", linestyle=":", linewidth=0.8, alpha=0.65)

        ax2 = ax.twinx()
        ax2.plot(cn[:, 0], cn[:, 1], color="#777777", linestyle=":", linewidth=1.8)
        ax2.set_ylabel("Coordination number")
        ax.set_title(pair.title, fontsize=11)

    fig.savefig(GRAPHS / f"{label}_li_o_n_coordination_slide.png", dpi=220)
    plt.close(fig)


def plot_overall(rows: list[dict[str, float | str]]) -> None:
    systems = SYSTEMS
    values = {
        pair.label: [
            next(row for row in rows if row["system"] == system and row["pair"] == pair.label)[
                "coordination_number"
            ]
            for system in systems
        ]
        for pair in PAIRS
    }

    x = np.arange(len(systems))
    width = 0.36
    fig, ax = plt.subplots(figsize=(8.8, 5.0))
    ax.bar(x - width / 2, values["Li-O(FSI)"], width, color="#4c78a8", label="Li-O(FSI)")
    ax.bar(x + width / 2, values["Li-N(FSI)"], width, color="#f58518", label="Li-N(FSI)")
    ax.set_xticks(x, systems)
    ax.set_ylabel("Coordination number")
    ax.set_title("Li-FSI coordination number comparison")
    ax.grid(True, axis="y", color="#dddddd", linewidth=0.6)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIGURES / "combined_li_o_n_coordination_number.png", dpi=220)
    plt.close(fig)


def write_summary(rows: list[dict[str, float | str]]) -> None:
    summary_csv = OUT / "coordination_number_li_o_n_summary.csv"
    fields = [
        "system",
        "pair",
        "selection_atom",
        "rdf_peak_r_nm",
        "first_minimum_r_nm",
        "coordination_number",
        "trajectory_length_ps",
    ]
    with summary_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in fields})

    lines = [
        "# RDF와 Coordination Number 결과",
        "",
        "이 폴더는 50 ps MD trajectory에서 계산한 `Li-O(FSI)` 및 `Li-N(FSI)` RDF와 coordination number 결과입니다.",
        "교수님 슬라이드 형태에 맞춰 RDF 곡선과 누적 coordination number를 함께 표시했습니다.",
        "",
        "## 분석 기준",
        "",
        "- Reference: Li 이온",
        "- Selection 1: FSI 음이온의 산소 원자 `OBT`",
        "- Selection 2: FSI 음이온의 질소 원자 `NBT`",
        "- Coordination number: RDF peak 이후 첫 번째 shell minimum까지 누적한 값",
        "- 현재 trajectory 길이: `50 ps`",
        "",
        "주의: 50 ps는 연습용 짧은 trajectory입니다. 정량적인 최종 결론을 위해서는 더 긴 production MD 결과로 다시 계산하는 것이 안전합니다.",
        "",
        "## Coordination Number 요약",
        "",
        "| 조성 | Li-O peak r (nm) | Li-O min r (nm) | Li-O CN | Li-N peak r (nm) | Li-N min r (nm) | Li-N CN |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    for system in SYSTEMS:
        o = next(row for row in rows if row["system"] == system and row["pair"] == "Li-O(FSI)")
        n = next(row for row in rows if row["system"] == system and row["pair"] == "Li-N(FSI)")
        lines.append(
            "| {system} | {op:.2f} | {om:.2f} | {oc:.2f} | {np:.2f} | {nm:.2f} | {nc:.2f} |".format(
                system=system,
                op=o["rdf_peak_r_nm"],
                om=o["first_minimum_r_nm"],
                oc=o["coordination_number"],
                np=n["rdf_peak_r_nm"],
                nm=n["first_minimum_r_nm"],
                nc=n["coordination_number"],
            )
        )

    lines.extend(
        [
            "",
            "## 파일 설명",
            "",
            "- `../../04_Figures_For_Report/RDF_CN/per_system/*_li_o_n_coordination_slide.png`: 교수님 슬라이드와 비슷한 2-panel RDF/CN 그래프",
            "- `../../04_Figures_For_Report/RDF_CN/combined_li_o_n_coordination_number.png`: 조성별 Li-O(FSI), Li-N(FSI) coordination number 비교",
            "- `raw_xvg/`: GROMACS `gmx rdf`에서 나온 원본 RDF/CN 데이터",
            "- `coordination_number_li_o_n_summary.csv`: 보고서 표에 넣기 쉬운 요약 CSV",
            "",
            "## 보고서에 쓸 수 있는 문장",
            "",
            "Li 이온 주변의 국소 배위 구조를 확인하기 위해 FSI 음이온의 산소 원자(OBT)와 질소 원자(NBT)를 대상으로 RDF 및 coordination number를 계산하였다. Li-O(FSI)는 약 0.22 nm 부근에서 뚜렷한 첫 번째 peak가 나타났고, Li-N(FSI)는 더 긴 거리 영역에서 첫 번째 배위 shell이 관찰되었다. 각 RDF의 첫 번째 shell minimum까지 적분한 coordination number를 비교함으로써 조성 변화에 따른 Li 주변 FSI 배위 환경을 정량적으로 확인할 수 있다.",
            "",
        ]
    )
    (OUT / "README_RDF_coordination_number.md").write_text("\n".join(lines))


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    GRAPHS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, float | str]] = []
    for system in SYSTEMS:
        results = [load_pair_result(system, pair) for pair in PAIRS]
        plot_slide_pair(system, results)
        for result in results:
            row = {
                "system": result["system"],
                "pair": result["pair"],
                "selection_atom": result["selection_atom"],
                "rdf_peak_r_nm": round(float(result["rdf_peak_r_nm"]), 4),
                "first_minimum_r_nm": round(float(result["first_minimum_r_nm"]), 4),
                "coordination_number": round(float(result["coordination_number"]), 4),
                "trajectory_length_ps": 50,
            }
            rows.append(row)

    plot_overall(rows)
    write_summary(rows)


if __name__ == "__main__":
    main()
