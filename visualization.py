"""
Visualization module: Matplotlib charts for the Hospital Patient Data
Analysis System.

Every chart is annotated with the operational-statistics disclaimer so
results are never mistaken for clinical advice.
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for headless/report use
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

import config


def _style_axes(ax) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle="--", alpha=0.4)


def _add_disclaimer(fig) -> None:
    fig.text(
        0.5,
        0.015,
        config.DISCLAIMER,
        ha="center",
        fontsize=7,
        color="#555555",
        wrap=True,
    )


def save_chart(fig, filename: str) -> str:
    """Save a figure to the charts directory and return its path."""
    config.CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.CHARTS_DIR / filename
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return str(path)


def plot_department_workload(df: pd.DataFrame, filename: str = "department_workload.png") -> str:
    """Bar chart of department-wise workload."""
    if df.empty:
        raise ValueError("department_workload DataFrame is empty")
    plot_df = df.head(12).iloc[::-1]  # horizontal bars, largest on top

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.barh(
        plot_df["department_name"],
        plot_df["visit_count"],
        color="#4c72b0",
        edgecolor="black",
        linewidth=0.5,
    )
    for bar in bars:
        width = bar.get_width()
        ax.text(
            width + max(plot_df["visit_count"]) * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{int(width):,}",
            va="center",
            fontsize=8,
        )
    ax.set_xlabel("Number of Visits")
    ax.set_title("Department-Wise Workload (Visit Counts)", fontsize=12, pad=12)
    _style_axes(ax)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    _add_disclaimer(fig)
    return save_chart(fig, filename)


def plot_monthly_trends(df: pd.DataFrame, filename: str = "monthly_visit_trends.png") -> str:
    """Line chart of monthly visit trends."""
    if df.empty:
        raise ValueError("monthly_visits DataFrame is empty")

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(
        df["month"],
        df["visit_count"],
        marker="o",
        color="#55a868",
        linewidth=2,
        markersize=5,
    )
    ax.set_xlabel("Month")
    ax.set_ylabel("Number of Visits")
    ax.set_title("Monthly Visit Trends", fontsize=12, pad=12)
    ax.yaxis.set_major_formatter(mtick.StrMethodFormatter("{x:,.0f}"))
    fig.autofmt_xdate()
    _style_axes(ax)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    _add_disclaimer(fig)
    return save_chart(fig, filename)


def plot_age_band_distribution(df: pd.DataFrame, filename: str = "age_band_distribution.png") -> str:
    """Bar chart of visits by age band."""
    if df.empty:
        raise ValueError("age_band DataFrame is empty")
    order = [b for b in config.AGE_BANDS if b in df["age_band"].values]
    plot_df = df.set_index("age_band").reindex(order).reset_index()

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(
        plot_df["age_band"],
        plot_df["visit_count"],
        color="#dd8452",
        edgecolor="black",
        linewidth=0.5,
    )
    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            height + max(plot_df["visit_count"]) * 0.01,
            f"{int(height):,}",
            ha="center",
            fontsize=8,
        )
    ax.set_xlabel("Age Band")
    ax.set_ylabel("Number of Visits")
    ax.set_title("Visit Distribution by Age Band", fontsize=12, pad=12)
    _style_axes(ax)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    _add_disclaimer(fig)
    return save_chart(fig, filename)


def plot_daily_visits(df: pd.DataFrame, filename: str = "daily_visits.png") -> str:
    """Line chart of daily visit volumes."""
    if df.empty:
        raise ValueError("daily_visits DataFrame is empty")

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df["date"], df["visit_count"], color="#8172b3", linewidth=1.2)
    ax.set_xlabel("Date")
    ax.set_ylabel("Number of Visits")
    ax.set_title("Daily Visit Volumes", fontsize=12, pad=12)
    ax.yaxis.set_major_formatter(mtick.StrMethodFormatter("{x:,.0f}"))
    fig.autofmt_xdate()
    _style_axes(ax)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    _add_disclaimer(fig)
    return save_chart(fig, filename)


def plot_visit_type(df: pd.DataFrame, filename: str = "visit_type_distribution.png") -> str:
    """Bar chart of visits by visit type."""
    if df.empty:
        raise ValueError("visit_type DataFrame is empty")
    plot_df = df.iloc[::-1]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.barh(
        plot_df["visit_type"],
        plot_df["visit_count"],
        color="#64a0c8",
        edgecolor="black",
        linewidth=0.5,
    )
    for bar in bars:
        width = bar.get_width()
        ax.text(
            width + max(plot_df["visit_count"]) * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{int(width):,}",
            va="center",
            fontsize=8,
        )
    ax.set_xlabel("Number of Visits")
    ax.set_title("Visits by Visit Type", fontsize=12, pad=12)
    _style_axes(ax)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    _add_disclaimer(fig)
    return save_chart(fig, filename)


def generate_all_charts(aggregates: dict[str, pd.DataFrame]) -> dict[str, str]:
    """Generate all standard charts and return a name->path mapping."""
    paths = {}
    paths["department_workload"] = plot_department_workload(
        aggregates["department_workload"]
    )
    paths["monthly_trends"] = plot_monthly_trends(aggregates["monthly_visits"])
    paths["age_band"] = plot_age_band_distribution(aggregates["age_band"])
    paths["daily_visits"] = plot_daily_visits(aggregates["daily_visits"])
    paths["visit_type"] = plot_visit_type(aggregates["visit_type"])
    return paths
