"""
Analysis module: Pandas grouped analysis + NumPy summary statistics.

All outputs are aggregates only — no patient-level records are returned —
consistent with the de-identified / restricted-access acceptance criteria.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

import config
from db import HospitalDB


def _require_columns(df: pd.DataFrame, columns: list[str]) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame missing required columns: {missing}")


def daily_visit_summary(db: HospitalDB) -> pd.DataFrame:
    """Visits grouped by date (daily volumes)."""
    df = db.daily_visits()
    if df.empty:
        return df
    _require_columns(df, ["date", "visit_count"])
    return df.sort_values("date").reset_index(drop=True)


def monthly_visit_summary(db: HospitalDB) -> pd.DataFrame:
    """Visits grouped by calendar month (monthly trend)."""
    df = db.monthly_visits()
    if df.empty:
        return df
    _require_columns(df, ["month", "visit_count"])
    return df.sort_values("month").reset_index(drop=True)


def department_workload(db: HospitalDB) -> pd.DataFrame:
    """Department-wise workload: visit counts and unique patients."""
    df = db.department_workload()
    if df.empty:
        return df
    _require_columns(df, ["department_name", "visit_count", "unique_patients"])
    df = df.sort_values("visit_count", ascending=False).reset_index(drop=True)
    df["share_of_total_percent"] = (
        df["visit_count"] / df["visit_count"].sum() * 100
    ).round(2)
    return df


def age_band_summary(db: HospitalDB) -> pd.DataFrame:
    """Visit and patient counts aggregated by non-identifying age band."""
    df = db.age_band_summary()
    if df.empty:
        return df
    _require_columns(df, ["age_band", "visit_count", "unique_patients"])
    total = df["visit_count"].sum()
    df["share_of_total_percent"] = (df["visit_count"] / total * 100).round(2)
    order = [b for b in config.AGE_BANDS if b in df["age_band"].values]
    df = df.set_index("age_band").reindex(order).reset_index()
    return df


def visit_type_summary(db: HospitalDB) -> pd.DataFrame:
    """Visit counts by visit type."""
    df = db.visit_type_summary()
    if df.empty:
        return df
    _require_columns(df, ["visit_type", "visit_count"])
    df["share_of_total_percent"] = (
        df["visit_count"] / df["visit_count"].sum() * 100
    ).round(2)
    return df.sort_values("visit_count", ascending=False).reset_index(drop=True)


def gender_summary(db: HospitalDB) -> pd.DataFrame:
    """Visit counts by gender (optional, de-identified)."""
    df = db.gender_summary()
    if df.empty:
        return df
    _require_columns(df, ["gender", "visit_count"])
    df["share_of_total_percent"] = (
        df["visit_count"] / df["visit_count"].sum() * 100
    ).round(2)
    return df.sort_values("visit_count", ascending=False).reset_index(drop=True)


def summary_statistics(db: HospitalDB) -> dict[str, Any]:
    """
    NumPy summary statistics over daily visit volumes.

    Returns dictionary of scalar statistics suitable for reporting.
    """
    daily = daily_visit_summary(db)
    if daily.empty:
        return {
            "total_visits": 0,
            "days_active": 0,
            "mean_visits_per_day": 0.0,
            "median_visits_per_day": 0.0,
            "std_visits_per_day": 0.0,
            "min_visits_per_day": 0,
            "max_visits_per_day": 0,
            "peak_date": None,
            "peak_visits": 0,
        }

    counts = daily["visit_count"].to_numpy(dtype=float)
    peak_idx = int(np.argmax(counts))
    peak_row = daily.iloc[peak_idx]

    peak_date = peak_row["date"]
    if hasattr(peak_date, "date"):
        peak_date = str(peak_date.date())
    else:
        peak_date = str(peak_date)

    stats = {
        "total_visits": int(daily["visit_count"].sum()),
        "days_active": int(len(daily)),
        "mean_visits_per_day": float(np.mean(counts)),
        "median_visits_per_day": float(np.median(counts)),
        "std_visits_per_day": float(np.std(counts)),
        "min_visits_per_day": int(np.min(counts)),
        "max_visits_per_day": int(np.max(counts)),
        "peak_date": peak_date,
        "peak_visits": int(peak_row["visit_count"]),
    }
    return stats


def all_aggregates(db: HospitalDB) -> dict[str, pd.DataFrame]:
    """Convenience: return every aggregate table as a dictionary of DataFrames."""
    return {
        "department_workload": department_workload(db),
        "monthly_visits": monthly_visit_summary(db),
        "daily_visits": daily_visit_summary(db),
        "age_band": age_band_summary(db),
        "visit_type": visit_type_summary(db),
        "gender": gender_summary(db),
    }
