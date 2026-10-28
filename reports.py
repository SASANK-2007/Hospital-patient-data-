"""
Report generation: plain-text and CSV operational reports.

Every report begins with the operational-statistics disclaimer so readers
understand these are aggregates, not clinical advice.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

import config
from analysis import all_aggregates, summary_statistics
from visualization import generate_all_charts


def _format_section(title: str) -> str:
    return f"\n{title}\n{'-' * len(title)}\n"


def build_text_report(db) -> str:
    """Build a full operational statistics report as plain text."""
    lines = []
    lines.append(config.REPORT_HEADER)
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"Database backend: {config.DB_BACKEND}\n")
    lines.append(f"Source database: {config.DB_PATH if config.DB_BACKEND == 'sqlite' else config.MYSQL_CONFIG['database']}\n")

    aggregates = all_aggregates(db)
    stats = summary_statistics(db)

    # Summary statistics
    lines.append(_format_section("SUMMARY STATISTICS"))
    for key, value in stats.items():
        lines.append(f"  {key.replace('_', ' ').title()}: {value}")

    # Department workload
    lines.append(_format_section("DEPARTMENT-WISE WORKLOAD REPORT"))
    dept = aggregates["department_workload"]
    if dept.empty:
        lines.append("  No data available.\n")
    else:
        lines.append(
            f"  {'Department':<24} {'Visits':>8} {'Unique Patients':>16} {'Share %':>8}"
        )
        for _, row in dept.iterrows():
            lines.append(
                f"  {row['department_name']:<24} {int(row['visit_count']):>8} "
                f"{int(row['unique_patients']):>16} {row['share_of_total_percent']:>7.2f}%"
            )
        lines.append(
            f"  {'TOTAL':<24} {int(dept['visit_count'].sum()):>8} "
            f"{'':>16} {100.0:>7.2f}%\n"
        )

    # Monthly trends
    lines.append(_format_section("VISIT TRENDS — MONTHLY"))
    monthly = aggregates["monthly_visits"]
    if monthly.empty:
        lines.append("  No data available.\n")
    else:
        lines.append(f"  {'Month':<12} {'Visits':>8}")
        for _, row in monthly.iterrows():
            month_str = (
                row["month"].strftime("%Y-%m")
                if hasattr(row["month"], "strftime")
                else str(row["month"])[:7]
            )
            lines.append(f"  {month_str:<12} {int(row['visit_count']):>8}")

    # Age band summary
    lines.append(_format_section("AGE-BAND SUMMARY (AGGREGATED, NON-IDENTIFYING)"))
    age = aggregates["age_band"]
    if age.empty:
        lines.append("  No data available.\n")
    else:
        lines.append(
            f"  {'Age Band':<12} {'Visits':>8} {'Unique Patients':>16} {'Share %':>8}"
        )
        for _, row in age.iterrows():
            lines.append(
                f"  {row['age_band']:<12} {int(row['visit_count']):>8} "
                f"{int(row['unique_patients']):>16} {row['share_of_total_percent']:>7.2f}%"
            )

    # Visit type
    lines.append(_format_section("VISITS BY VISIT TYPE"))
    vtype = aggregates["visit_type"]
    if vtype.empty:
        lines.append("  No data available.\n")
    else:
        lines.append(f"  {'Visit Type':<20} {'Visits':>8} {'Share %':>8}")
        for _, row in vtype.iterrows():
            lines.append(
                f"  {row['visit_type']:<20} {int(row['visit_count']):>8} "
                f"{row['share_of_total_percent']:>7.2f}%"
            )

    # Gender
    lines.append(_format_section("VISITS BY GENDER (OPTIONAL, DE-IDENTIFIED)"))
    gender = aggregates["gender"]
    if gender.empty:
        lines.append("  No data available.\n")
    else:
        lines.append(f"  {'Gender':<24} {'Visits':>8} {'Share %':>8}")
        for _, row in gender.iterrows():
            lines.append(
                f"  {row['gender']:<24} {int(row['visit_count']):>8} "
                f"{row['share_of_total_percent']:>7.2f}%"
            )

    lines.append("\n")
    lines.append("END OF REPORT\n")
    lines.append(config.DISCLAIMER + "\n")
    lines.append("=" * 78 + "\n")
    return "".join(lines)


def save_text_report(db, filename: str | None = None) -> str:
    """Save the text report and return its path."""
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"operational_report_{timestamp}.txt"
    path = config.REPORTS_DIR / filename
    content = build_text_report(db)
    path.write_text(content, encoding="utf-8")
    return str(path)


def save_csv_reports(db) -> list[str]:
    """Save each aggregate table as a separate CSV file. Returns paths."""
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    aggregates = all_aggregates(db)
    paths = []
    for name, df in aggregates.items():
        path = config.REPORTS_DIR / f"{name}.csv"
        df.to_csv(path, index=False, encoding="utf-8")
        paths.append(str(path))
    return paths


def generate_full_output(db) -> dict[str, Any]:
    """
    Generate charts, text report, and CSV reports.

    Returns a dictionary with paths to all generated artifacts.
    """
    chart_paths = generate_all_charts(all_aggregates(db))
    text_path = save_text_report(db)
    csv_paths = save_csv_reports(db)
    return {
        "charts": chart_paths,
        "report": text_path,
        "csv_reports": csv_paths,
    }
