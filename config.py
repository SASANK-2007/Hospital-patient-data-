"""
Configuration for the Hospital Patient Data Analysis System.

All data is synthetic / de-identified. This system is for educational
operational analytics only and must not be used for clinical decisions.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
CHARTS_DIR = OUTPUT_DIR / "charts"
REPORTS_DIR = OUTPUT_DIR / "reports"
DB_PATH = DATA_DIR / "hospital_analytics.sqlite"

# Ensure output directories exist
for _d in (DATA_DIR, OUTPUT_DIR, CHARTS_DIR, REPORTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Database choice
# ---------------------------------------------------------------------------
# Default: SQLite (no external server required).
# Set HOSPITAL_DB_BACKEND=mysql plus HOSPITAL_DB_* env vars to use MySQL.
DB_BACKEND = os.getenv("HOSPITAL_DB_BACKEND", "sqlite")

MYSQL_CONFIG = {
    "host": os.getenv("HOSPITAL_DB_HOST", "localhost"),
    "port": int(os.getenv("HOSPITAL_DB_PORT", "3306")),
    "user": os.getenv("HOSPITAL_DB_USER", "root"),
    "password": os.getenv("HOSPITAL_DB_PASSWORD", ""),
    "database": os.getenv("HOSPITAL_DB_NAME", "hospital_analytics"),
}

# ---------------------------------------------------------------------------
# Synthetic reference data (de-identified)
# ---------------------------------------------------------------------------
DEPARTMENTS = [
    "Cardiology",
    "Neurology",
    "Orthopedics",
    "Pediatrics",
    "Oncology",
    "Emergency",
    "General Surgery",
    "Gynecology",
    "Dermatology",
    "Ophthalmology",
]

AGE_BANDS = ["0-17", "18-29", "30-44", "45-59", "60-74", "75+"]

GENDERS = ["M", "F", "Other", "Prefer not to say"]

VISIT_TYPES = ["Consultation", "Follow-up", "Procedure", "Emergency", "Screening"]

# Seasonal multipliers by month index (1=January ... 12=December).
# Simulates higher respiratory/Emergency volume in winter months.
SEASONAL_MULTIPLIERS = {
    1: 1.15, 2: 1.12, 3: 1.05, 4: 0.98, 5: 0.95, 6: 0.94,
    7: 0.96, 8: 0.97, 9: 1.00, 10: 1.03, 11: 1.10, 12: 1.18,
}

# Department base-visit weights (relative volume).
DEPARTMENT_WEIGHTS = {
    "Emergency": 1.30,
    "General Surgery": 1.10,
    "Cardiology": 1.05,
    "Orthopedics": 1.00,
    "Pediatrics": 1.05,
    "Gynecology": 0.95,
    "Oncology": 0.90,
    "Neurology": 0.90,
    "Dermatology": 0.85,
    "Ophthalmology": 0.80,
}

# Age-band distribution weights (must sum to 1.0 conceptually).
AGE_BAND_WEIGHTS = {
    "0-17": 0.14,
    "18-29": 0.16,
    "30-44": 0.18,
    "45-59": 0.18,
    "60-74": 0.18,
    "75+": 0.16,
}

# ---------------------------------------------------------------------------
# Labeling / disclaimer
# ---------------------------------------------------------------------------
DISCLAIMER = (
    "OPERATIONAL STATISTICS ONLY - NOT CLINICAL ADVICE. "
    "These aggregates are derived from synthetic / de-identified hospital "
    "visit records for educational operational analytics. They do not "
    "constitute diagnoses, treatment recommendations, or medical guidance."
)

REPORT_HEADER = "\n".join(
    [
        "=" * 78,
        "HOSPITAL PATIENT DATA ANALYSIS SYSTEM - OPERATIONAL REPORT",
        "=" * 78,
        DISCLAIMER,
        "=" * 78,
        "",
    ]
) + "\n"

CHART_FOOTNOTE = DISCLAIMER

RANDOM_SEED = 42

# Acceptance criteria checklist (used by verify_acceptance.py)
ACCEPTANCE_CRITERIA = [
    "Synthetic / de-identified data only (no PII, diagnoses, or treatments)",
    "Restricted access to raw records (aggregate queries only by default)",
    "Reports contain aggregates only (no patient-level records)",
    "Results labeled as operational statistics, not clinical advice",
    "Department-wise workload report generated",
    "Visit trends (daily/monthly) generated",
    "Age-band summary (aggregated, non-identifying) generated",
    "Aggregated charts (Matplotlib) generated",
]
