"""
Synthetic / de-identified data generator for the Hospital Patient Data
Analysis System.

Generates patients, departments, and visits. No real patient names, contact
details, diagnoses, or treatment information are ever created or stored —
consistent with the de-identified / operational-analytics scope.

Visit generation includes realistic seasonal variation (higher volume in
winter months) and department-specific base volumes.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any

import pandas as pd

import config
from db import HospitalDB


def generate_departments() -> list[dict[str, Any]]:
    """Return department reference rows."""
    return [{"department_name": name} for name in config.DEPARTMENTS]


def generate_patients(n: int = 2000) -> list[dict[str, Any]]:
    """
    Generate de-identified patient rows.

    Columns: patient_id (assigned by DB), age_band, gender_optional.
    Ages are bucketed into non-identifying age bands using weighted
    distribution.
    """
    random.seed(config.RANDOM_SEED)
    bands = list(config.AGE_BAND_WEIGHTS.keys())
    weights = list(config.AGE_BAND_WEIGHTS.values())
    patients = []
    for _ in range(n):
        age_band = random.choices(bands, weights=weights, k=1)[0]
        gender = random.choice(config.GENDERS)
        patients.append({"age_band": age_band, "gender_optional": gender})
    return patients


def generate_visits(
    patient_ids: list[int],
    department_ids: list[int],
    n: int = 5000,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict[str, Any]]:
    """
    Generate synthetic visit rows.

    Columns: visit_id (assigned by DB), patient_id, department_id,
    visit_date (ISO-8601), visit_type.

    Seasonal multipliers create higher winter volume; department weights
    create varied workload across departments.
    """
    random.seed(config.RANDOM_SEED + 1)
    if start_date is None:
        start_date = date.today() - timedelta(days=365)
    if end_date is None:
        end_date = date.today()

    # Department selection probabilities proportional to base weights.
    dept_weights = [config.DEPARTMENT_WEIGHTS.get(d, 1.0) for d in config.DEPARTMENTS]
    dept_id_by_name = {name: did for did, name in zip(department_ids, config.DEPARTMENTS)}
    ordered_ids = [dept_id_by_name[d] for d in config.DEPARTMENTS if d in dept_id_by_name]
    ordered_weights = [config.DEPARTMENT_WEIGHTS.get(d, 1.0)
                       for d in config.DEPARTMENTS if d in dept_id_by_name]
    total_weight = sum(ordered_weights)
    dept_probs = [w / total_weight for w in ordered_weights]

    delta_days = (end_date - start_date).days
    visits = []
    for _ in range(n):
        # Pick a day within range, then apply seasonal acceptance-rejection
        # to bias toward higher-volume winter months.
        visit_date = start_date + timedelta(days=random.randint(0, delta_days))
        seasonal_mult = config.SEASONAL_MULTIPLIERS.get(visit_date.month, 1.0)
        if random.random() > seasonal_mult / 1.2:
            visit_date = start_date + timedelta(days=random.randint(0, delta_days))

        dept_id = random.choices(ordered_ids, weights=dept_probs, k=1)[0]
        visits.append(
            {
                "patient_id": random.choice(patient_ids),
                "department_id": dept_id,
                "visit_date": visit_date.isoformat(),
                "visit_type": random.choice(config.VISIT_TYPES),
            }
        )
    return visits


def seed_database(db: HospitalDB, n_patients: int = 2000, n_visits: int = 5000) -> None:
    """
    Seed the database with synthetic data if tables are empty.

    Idempotent: existing rows are preserved.
    """
    with db.cursor() as cur:
        # Departments
        cur.execute("SELECT COUNT(*) AS c FROM departments")
        dept_count = cur.fetchone()["c"]
        if dept_count == 0:
            for dept in generate_departments():
                if db._mysql:
                    cur.execute(
                        "INSERT INTO departments (department_name) VALUES (%s)",
                        (dept["department_name"],),
                    )
                else:
                    cur.execute(
                        "INSERT INTO departments (department_name) VALUES (?)",
                        (dept["department_name"],),
                    )

        # Patients
        cur.execute("SELECT COUNT(*) AS c FROM patients")
        patient_count = cur.fetchone()["c"]
        if patient_count == 0:
            patients = generate_patients(n_patients)
            for p in patients:
                if db._mysql:
                    cur.execute(
                        "INSERT INTO patients (age_band, gender_optional) VALUES (%s, %s)",
                        (p["age_band"], p["gender_optional"]),
                    )
                else:
                    cur.execute(
                        "INSERT INTO patients (age_band, gender_optional) VALUES (?, ?)",
                        (p["age_band"], p["gender_optional"]),
                    )

        # Visits
        cur.execute("SELECT COUNT(*) AS c FROM visits")
        visit_count = cur.fetchone()["c"]
        if visit_count == 0:
            cur.execute("SELECT patient_id FROM patients")
            patient_ids = [r["patient_id"] for r in cur.fetchall()]
            cur.execute("SELECT department_id FROM departments")
            department_ids = [r["department_id"] for r in cur.fetchall()]
            visits = generate_visits(patient_ids, department_ids, n=n_visits)
            for v in visits:
                if db._mysql:
                    cur.execute(
                        "INSERT INTO visits "
                        "(patient_id, department_id, visit_date, visit_type) "
                        "VALUES (%s, %s, %s, %s)",
                        (
                            v["patient_id"],
                            v["department_id"],
                            v["visit_date"],
                            v["visit_type"],
                        ),
                    )
                else:
                    cur.execute(
                        "INSERT INTO visits "
                        "(patient_id, department_id, visit_date, visit_type) "
                        "VALUES (?, ?, ?, ?)",
                        (
                            v["patient_id"],
                            v["department_id"],
                            v["visit_date"],
                            v["visit_type"],
                        ),
                    )
    db._conn.commit()


def load_into_dataframe(db: HospitalDB) -> pd.DataFrame:
    """Convenience: load joined visit data into a pandas DataFrame."""
    return db.load_visits_dataframe()
