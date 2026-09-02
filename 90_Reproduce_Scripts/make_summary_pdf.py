from __future__ import annotations

from pathlib import Path
import csv

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "03_Analysis_Results" / "General_Analysis"
REPORT = ROOT / "05_Report" / "Report_Materials"
PDF = REPORT / "CILE_practice_analysis_summary.pdf"


def read_summary() -> list[dict[str, str]]:
    with (ANALYSIS / "summary.csv").open() as fh:
        return list(csv.DictReader(fh))


def add_title_page(pdf: PdfPages, rows: list[dict[str, str]]) -> None:
    fig = plt.figure(figsize=(11, 8.5))
    fig.text(0.06, 0.92, "CILE MD Practice Analysis Summary", fontsize=22, weight="bold")
    fig.text(0.06, 0.86, "Systems: L1P1, L1P2, L2P1, L3P1, L1P3", fontsize=12)
    fig.text(
        0.06,
        0.81,
        "Trajectory length: 50 ps practice runs. Values are for workflow validation, not final production conclusions.",
        fontsize=11,
    )

    table_rows = []
    for row in rows:
        table_rows.append(
            [
                row["label"],
                f'{float(row["temperature_avg"]):.1f}',
                f'{float(row["coordination_number_at_first_min"]):.2f}',
                f'{float(row["diffusion_li_m2_s"]):.2e}',
                f'{float(row["diffusion_pyr13_m2_s"]):.2e}',
                f'{float(row["diffusion_fsi_m2_s"]):.2e}',
            ]
        )

    ax = fig.add_axes([0.06, 0.36, 0.88, 0.36])
    ax.axis("off")
    table = ax.table(
        cellText=table_rows,
        colLabels=["System", "T avg (K)", "CN Li-O", "D Li", "D Pyr13", "D FSI"],
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.6)

    notes = [
        "Analysis generated:",
        "- Energy / temperature / pressure checks",
        "- Li-O(FSI) RDF and coordination number",
        "- MSD and diffusion estimates from 10-45 ps linear fits",
        "",
        "Recommended next step for final research: longer NPT production MD, ideally ns to tens of ns.",
    ]
    fig.text(0.06, 0.10, "\n".join(notes), fontsize=11, va="bottom")
    pdf.savefig(fig)
    plt.close(fig)


def add_plot_page(pdf: PdfPages, title: str, image_paths: list[Path]) -> None:
    fig, axes = plt.subplots(1, len(image_paths), figsize=(11, 8.5))
    if len(image_paths) == 1:
        axes = [axes]
    fig.suptitle(title, fontsize=18, weight="bold")
    for ax, image_path in zip(axes, image_paths):
        ax.imshow(mpimg.imread(image_path))
        ax.axis("off")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    pdf.savefig(fig)
    plt.close(fig)


def main() -> None:
    REPORT.mkdir(parents=True, exist_ok=True)
    rows = read_summary()
    with PdfPages(PDF) as pdf:
        add_title_page(pdf, rows)
        add_plot_page(
            pdf,
            "Overall comparison plots",
            [
                ANALYSIS / "overall_diffusion_coefficients.png",
                ANALYSIS / "overall_li_obt_coordination.png",
            ],
        )
        add_plot_page(
            pdf,
            "Temperature stability check",
            [ANALYSIS / "overall_temperature_check.png"],
        )
    print(PDF)


if __name__ == "__main__":
    main()
