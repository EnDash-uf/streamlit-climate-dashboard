"""Data ingestion and reporting helpers for the climate dashboard."""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
from fpdf import FPDF

from .auth import get_user_dir


@dataclass
class DatasetInfo:
    """Metadata describing a stored dataset."""

    path: Path
    uploaded_at: datetime
    rows: int
    columns: int


def _metadata_path(user_dir: Path) -> Path:
    return user_dir / "metadata.json"


def save_uploaded_dataset(username: str, file_name: str, file_bytes: bytes) -> DatasetInfo:
    """Persist an uploaded CSV file and return basic metadata.

    The dataset is saved with a timestamped filename and also recorded in a
    simple ``metadata.json`` file so the UI can display the most recent upload.
    """

    user_dir = get_user_dir(username)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    target_path = user_dir / f"dataset_{timestamp}.csv"
    target_path.write_bytes(file_bytes)

    df = pd.read_csv(io.BytesIO(file_bytes))
    info = DatasetInfo(
        path=target_path,
        uploaded_at=datetime.utcnow(),
        rows=len(df),
        columns=len(df.columns),
    )

    meta = {
        "latest_file": target_path.name,
        "uploaded_at": info.uploaded_at.isoformat(),
        "rows": info.rows,
        "columns": info.columns,
    }
    _metadata_path(user_dir).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return info


def load_latest_dataset(username: str) -> Tuple[pd.DataFrame | None, DatasetInfo | None]:
    """Return the most recent dataset and its metadata, if available."""

    user_dir = get_user_dir(username)
    metadata_file = _metadata_path(user_dir)
    if not metadata_file.exists():
        return None, None

    meta = json.loads(metadata_file.read_text(encoding="utf-8"))
    latest_file = user_dir / meta.get("latest_file", "")
    if not latest_file.exists():
        return None, None

    df = pd.read_csv(latest_file)
    info = DatasetInfo(
        path=latest_file,
        uploaded_at=datetime.fromisoformat(meta["uploaded_at"]),
        rows=meta.get("rows", len(df)),
        columns=meta.get("columns", len(df.columns)),
    )
    return df, info


def summarize_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return descriptive statistics for numeric columns."""

    numeric_cols = df.select_dtypes(include="number")
    if numeric_cols.empty:
        return pd.DataFrame()

    summary = numeric_cols.describe().transpose()
    summary = summary.rename(
        columns={
            "mean": "Mean",
            "std": "Std Dev",
            "min": "Min",
            "max": "Max",
            "25%": "Q1",
            "50%": "Median",
            "75%": "Q3",
        }
    )
    return summary[["Mean", "Std Dev", "Min", "Q1", "Median", "Q3", "Max", "count"]]


def build_report_text(df: pd.DataFrame, settings: Dict[str, any]) -> str:
    """Compose a markdown report for the dataset and user preferences."""

    rows, cols = df.shape
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    units = settings.get("unit_preference", "metric").title()
    setpoints = settings.get("ideal_setpoints", {})

    report_lines: List[str] = [
        "# Climate Data Summary",
        "",
        f"*Generated on:* {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        f"*Dataset size:* {rows} rows × {cols} columns",
        f"*Numeric columns analysed:* {', '.join(numeric_cols) if numeric_cols else 'None'}",
        "",
        "## User Preferences",
        f"- Unit preference: **{units}**",
    ]

    if setpoints:
        report_lines.append("- Ideal setpoints:")
        for key, value in setpoints.items():
            report_lines.append(f"  - {key.title()}: {value}")
    report_lines.append("")

    if numeric_cols:
        summary = summarize_numeric_columns(df)
        top_focus = summary.sort_values("Mean", ascending=False).head(3)
        report_lines.append("## Key Metrics")
        for feature, row in top_focus.iterrows():
            report_lines.append(
                f"- **{feature}** averages {row['Mean']:.2f} with highs near {row['Max']:.2f}"
            )
        report_lines.append("")

    report_lines.append(
        "This lightweight report is designed as a starting point. "
        "Future iterations can expand on anomaly detection, trend analysis, "
        "and chatbot-powered insights."
    )
    return "\n".join(report_lines)


def build_pdf(report_text: str, summary: pd.DataFrame | None = None) -> bytes:
    """Render a PDF version of the analysis report."""

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 10, "Climate Data Analysis Report")
    pdf.ln(2)

    pdf.set_font("Helvetica", size=12)
    for line in report_text.split("\n"):
        pdf.multi_cell(0, 8, line)
    pdf.ln(4)

    if summary is not None and not summary.empty:
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Numeric Summary", ln=True)
        pdf.set_font("Helvetica", size=10)
        headers = list(summary.columns)
        col_width = pdf.epw / (len(headers) + 1)
        pdf.multi_cell(0, 6, "")

        # Header row
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(col_width, 8, "Feature", border=1)
        for header in headers:
            pdf.cell(col_width, 8, header, border=1)
        pdf.ln(8)

        pdf.set_font("Helvetica", size=9)
        for feature, row in summary.iterrows():
            pdf.cell(col_width, 6, str(feature), border=1)
            for header in headers:
                value = row.get(header, "")
                if isinstance(value, float):
                    pdf.cell(col_width, 6, f"{value:.2f}", border=1)
                else:
                    pdf.cell(col_width, 6, str(value), border=1)
            pdf.ln(6)

    return pdf.output(dest="S").encode("latin1")

