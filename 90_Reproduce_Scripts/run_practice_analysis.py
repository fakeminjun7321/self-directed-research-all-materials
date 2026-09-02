from __future__ import annotations

from pathlib import Path
import csv
import os
import re
import subprocess

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "02_Processed_Data" / "MD_Runs" / "50ps_Practice"
OUT = ROOT / "03_Analysis_Results" / "General_Analysis"
LABELS = ["L1P1", "L1P2", "L2P1", "L3P1", "L1P3"]

ENERGY_TERMS = ["Potential", "Total-Energy", "Temperature", "Pressure"]


def run(command: list[str], cwd: Path, stdin: str | None = None) -> str:
    env = os.environ.copy()
    env["GMX_MAXBACKUP"] = "-1"
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        input=stdin,
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


def safe_slope_diffusion(msd: np.ndarray, begin_ps: float = 10.0, end_ps: float = 45.0) -> float:
    mask = (msd[:, 0] >= begin_ps) & (msd[:, 0] <= end_ps)
    fit = msd[mask]
    if fit.shape[0] < 3:
        return float("nan")
    slope, _ = np.polyfit(fit[:, 0], fit[:, 1], 1)
    return slope / 6.0 * 1e-6


def rdf_peak_min_cn(rdf: np.ndarray, cn: np.ndarray) -> tuple[float, float, float]:
    r = rdf[:, 0]
    g = rdf[:, 1]
    mask = (r >= 0.10) & (r <= 1.20)
    if not np.any(mask):
        return float("nan"), float("nan"), float("nan")

    indices = np.where(mask)[0]
    peak_idx = indices[np.argmax(g[indices])]
    search = np.where((r > r[peak_idx]) & (r <= 0.60))[0]
    min_idx = peak_idx
    if search.size:
        smooth = np.convolve(g, np.ones(5) / 5, mode="same")
        local_min = []
        for idx in search:
            if idx <= 1 or idx >= len(smooth) - 2:
                continue
            if smooth[idx - 1] > smooth[idx] and smooth[idx + 1] > smooth[idx]:
                local_min.append(idx)
        if local_min:
            min_idx = local_min[0]
        else:
            min_idx = search[np.argmin(smooth[search])]

    cn_at_min = np.interp(r[min_idx], cn[:, 0], cn[:, 1])
    return float(r[peak_idx]), float(r[min_idx]), float(cn_at_min)


def make_index(label: str, work: Path, out_dir: Path) -> Path:
    ndx = out_dir / f"{label}_index.ndx"
    if not ndx.exists():
        run(["gmx", "make_ndx", "-f", "md_50ps.tpr", "-o", str(ndx)], work, stdin="q\n")
    return ndx


def analyze_energy(label: str, work: Path, out_dir: Path) -> dict[str, float]:
    xvg = out_dir / f"{label}_energy.xvg"
    stdout = run(
        ["gmx", "energy", "-f", "md_50ps.edr", "-o", str(xvg), "-xvg", "none"],
        work,
        stdin="\n".join(ENERGY_TERMS) + "\n",
    )
    (out_dir / f"{label}_energy_stdout.txt").write_text(stdout)
    data = read_xvg(xvg)

    summary: dict[str, float] = {}
    for idx, term in enumerate(ENERGY_TERMS, start=1):
        values = data[:, idx]
        key = term.lower().replace(" ", "_").replace("-", "_")
        summary[f"{key}_avg"] = float(np.mean(values))
        summary[f"{key}_std"] = float(np.std(values))

    fig, axes = plt.subplots(3, 1, figsize=(8, 8), sharex=True)
    axes[0].plot(data[:, 0], data[:, 1], color="#2f5597", linewidth=1.4)
    axes[0].set_ylabel("Potential\n(kJ/mol)")
    axes[1].plot(data[:, 0], data[:, 3], color="#c0504d", linewidth=1.4)
    axes[1].axhline(298, color="#888888", linestyle="--", linewidth=1)
    axes[1].set_ylabel("Temperature\n(K)")
    axes[2].plot(data[:, 0], data[:, 4], color="#548235", linewidth=1.4)
    axes[2].axhline(1, color="#888888", linestyle="--", linewidth=1)
    axes[2].set_ylabel("Pressure\n(bar)")
    axes[2].set_xlabel("Time (ps)")
    fig.suptitle(f"{label} energy and equilibration checks")
    fig.tight_layout()
    fig.savefig(out_dir / f"{label}_energy_temperature_pressure.png", dpi=180)
    plt.close(fig)

    return summary


def analyze_rdf(label: str, work: Path, out_dir: Path) -> dict[str, float]:
    rdf = out_dir / f"{label}_rdf_li_obt.xvg"
    cn = out_dir / f"{label}_coordination_li_obt.xvg"
    stdout = run(
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
            "name OBT",
            "-rmax",
            "1.2",
            "-bin",
            "0.01",
            "-xvg",
            "none",
        ],
        work,
    )
    (out_dir / f"{label}_rdf_stdout.txt").write_text(stdout)
    rdf_data = read_xvg(rdf)
    cn_data = read_xvg(cn)
    peak_r, first_min_r, cn_at_min = rdf_peak_min_cn(rdf_data, cn_data)

    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax1.plot(rdf_data[:, 0], rdf_data[:, 1], color="#2f5597", linewidth=1.6, label="RDF Li-OBT")
    ax1.set_xlabel("r (nm)")
    ax1.set_ylabel("g(r)")
    ax1.axvline(peak_r, color="#2f5597", linestyle="--", linewidth=1)
    ax1.axvline(first_min_r, color="#999999", linestyle=":", linewidth=1)

    ax2 = ax1.twinx()
    ax2.plot(cn_data[:, 0], cn_data[:, 1], color="#c0504d", linewidth=1.4, label="Coordination number")
    ax2.set_ylabel("Coordination number")
    ax1.set_title(f"{label} Li-O(FSI) RDF and coordination")
    fig.tight_layout()
    fig.savefig(out_dir / f"{label}_rdf_li_obt.png", dpi=180)
    plt.close(fig)

    return {
        "rdf_peak_r_nm": peak_r,
        "rdf_first_min_r_nm": first_min_r,
        "coordination_number_at_first_min": cn_at_min,
    }


def analyze_msd(label: str, work: Path, out_dir: Path, ndx: Path) -> dict[str, float]:
    selections = [
        ("Li", "group 2", "atom"),
        ("Pyr13", "group 3", "whole_mol_com"),
        ("FSI", "group 4", "whole_mol_com"),
    ]
    diffusion: dict[str, float] = {}
    msd_data: dict[str, np.ndarray] = {}

    for name, selection, seltype in selections:
        xvg = out_dir / f"{label}_msd_{name.lower()}.xvg"
        stdout = run(
            [
                "gmx",
                "msd",
                "-f",
                "md_50ps.xtc",
                "-s",
                "md_50ps.tpr",
                "-n",
                str(ndx),
                "-o",
                str(xvg),
                "-sel",
                selection,
                "-seltype",
                seltype,
                "-beginfit",
                "10",
                "-endfit",
                "45",
                "-xvg",
                "none",
            ],
            work,
        )
        (out_dir / f"{label}_msd_{name.lower()}_stdout.txt").write_text(stdout)
        data = read_xvg(xvg)
        msd_data[name] = data
        diffusion[f"diffusion_{name.lower()}_m2_s"] = safe_slope_diffusion(data)

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = {"Li": "#2f5597", "Pyr13": "#c0504d", "FSI": "#548235"}
    for name, data in msd_data.items():
        ax.plot(data[:, 0], data[:, 1], linewidth=1.5, color=colors[name], label=name)
    ax.set_xlabel("Time lag (ps)")
    ax.set_ylabel("MSD (nm$^2$)")
    ax.set_title(f"{label} MSD comparison")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / f"{label}_msd_comparison.png", dpi=180)
    plt.close(fig)

    return diffusion


def write_overall_plots(rows: list[dict[str, float | str]]) -> None:
    labels = [str(row["label"]) for row in rows]

    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(labels))
    width = 0.25
    for offset, key, title, color in [
        (-width, "diffusion_li_m2_s", "Li", "#2f5597"),
        (0, "diffusion_pyr13_m2_s", "Pyr13", "#c0504d"),
        (width, "diffusion_fsi_m2_s", "FSI", "#548235"),
    ]:
        values = [float(row[key]) for row in rows]
        ax.bar(x + offset, values, width=width, label=title, color=color)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Diffusion estimate (m$^2$/s)")
    ax.set_title("Estimated diffusion coefficients from 50 ps practice trajectories")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "overall_diffusion_coefficients.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    values = [float(row["coordination_number_at_first_min"]) for row in rows]
    ax.bar(labels, values, color="#8064a2")
    ax.set_ylabel("Coordination number")
    ax.set_title("Li-O(FSI) coordination estimate")
    fig.tight_layout()
    fig.savefig(OUT / "overall_li_obt_coordination.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    temperatures = [float(row["temperature_avg"]) for row in rows]
    ax.bar(labels, temperatures, color="#f79646")
    ax.axhline(298, color="#777777", linestyle="--", linewidth=1)
    ax.set_ylabel("Average temperature (K)")
    ax.set_title("Average temperature check")
    fig.tight_layout()
    fig.savefig(OUT / "overall_temperature_check.png", dpi=180)
    plt.close(fig)


def write_summary(rows: list[dict[str, float | str]]) -> None:
    fieldnames = [
        "label",
        "potential_avg",
        "potential_std",
        "temperature_avg",
        "temperature_std",
        "pressure_avg",
        "pressure_std",
        "rdf_peak_r_nm",
        "rdf_first_min_r_nm",
        "coordination_number_at_first_min",
        "diffusion_li_m2_s",
        "diffusion_pyr13_m2_s",
        "diffusion_fsi_m2_s",
    ]
    with (OUT / "summary.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})

    lines = [
        "# 분석 결과 요약",
        "",
        "이 폴더는 50 ps 연습용 trajectory에서 만든 자동 분석 결과입니다.",
        "강의에서 요구한 RDF, coordination number, MSD/diffusion, 온도/압력 확인 그래프를 모아 두었습니다.",
        "",
        "주의: 강의자료에는 production MD가 50 ns 수준으로 제시되어 있습니다. 현재 결과는 50 ps라서 값 자체를 논문식 결론으로 쓰기보다는, 분석 방법을 연습하고 보고서 예시 그림으로 쓰는 용도입니다.",
        "",
        "## 핵심 파일",
        "",
        "- `summary.csv`: 조성별 숫자 요약",
        "- `overall_diffusion_coefficients.png`: Li, Pyr13, FSI diffusion estimate 비교",
        "- `overall_li_obt_coordination.png`: Li-O(FSI) coordination number 비교",
        "- `overall_temperature_check.png`: 온도 안정성 확인",
        "",
        "## 조성별 폴더",
        "",
        "각 조성 폴더에는 다음 그림이 있습니다.",
        "",
        "- `*_energy_temperature_pressure.png`: potential energy, temperature, pressure",
        "- `*_rdf_li_obt.png`: Li와 FSI 산소(OBT)의 RDF 및 coordination",
        "- `*_msd_comparison.png`: Li, Pyr13, FSI MSD 비교",
        "",
    ]
    lines.append("## 조성별 숫자 요약")
    lines.append("")
    lines.append("| label | T avg (K) | CN Li-O | D Li (m2/s) | D Pyr13 (m2/s) | D FSI (m2/s) |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for row in rows:
        lines.append(
            "| {label} | {temperature_avg:.2f} | {coordination_number_at_first_min:.2f} | {diffusion_li_m2_s:.3e} | {diffusion_pyr13_m2_s:.3e} | {diffusion_fsi_m2_s:.3e} |".format(
                **row
            )
        )
    (OUT / "README_analysis.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, float | str]] = []

    for label in LABELS:
        work = RUNS / label
        out_dir = OUT / label
        out_dir.mkdir(parents=True, exist_ok=True)

        ndx = make_index(label, work, out_dir)
        row: dict[str, float | str] = {"label": label}
        row.update(analyze_energy(label, work, out_dir))
        row.update(analyze_rdf(label, work, out_dir))
        row.update(analyze_msd(label, work, out_dir, ndx))
        rows.append(row)

    write_overall_plots(rows)
    write_summary(rows)
    print(f"Done. Analysis results: {OUT}")


if __name__ == "__main__":
    main()
