# Hospital Patient Data Analysis System

**Project 7 — Intermediate difficulty**  
Educational operational analytics for de-identified / synthetic hospital visit records.

## Scope & boundaries
- Educational operational analytics only.
- No diagnoses or treatment recommendations are produced.
- All data is synthetic / de-identified; no real patient names or contact details.
- Results are **aggregates only** and are labeled **operational statistics, not clinical advice**.

## Suggested entities (implemented)
- `patients(patient_id, age_band, gender_optional)`
- `departments(department_id, department_name)`
- `visits(visit_id, patient_id, department_id, visit_date, visit_type)`

## Features
- Synthetic patient, department, and visit record generation (with realistic seasonal patterns).
- Daily / monthly visit summaries and department-wise workload.
- Age-band analysis using non-identifying aggregated data.
- Pandas grouped analysis + NumPy summary statistics.
- Matplotlib charts (department workload, monthly trends, age bands, daily volumes, visit type).
- Plain-text and CSV operational reports.
- Interactive CLI menu (`main.py`).
- Streamlit web dashboard (`app.py`).
- Acceptance-criteria verification script (`verify_acceptance.py`).

## Acceptance criteria
| Criterion | How it is met |
|---|---|
| Synthetic / de-identified data | `synthetic_data.py` generates only age bands, gender, dates, departments, visit types — no names, contacts, diagnoses. |
| Restrict access to records | `HospitalDB` defaults to `restricted=True`; raw record dumps are blocked; only aggregated queries are allowed. Verified by `verify_acceptance.py`. |
| Report aggregates only | Analysis module returns grouped DataFrames; no patient-level rows leave the DB layer. |
| Label results as operational statistics | Every chart and report carries the disclaimer: *"OPERATIONAL STATISTICS ONLY - NOT CLINICAL ADVICE..."* |
| Department-wise workload report | `department_workload()` + chart + text/CSV sections. |
| Visit trends | `daily_visit_summary()` / `monthly_visit_summary()` + charts. |
| Age-band summary | `age_band_summary()` + chart (non-identifying bands). |
| Aggregated charts | Five Matplotlib PNG charts, each footnoted with the disclaimer. |

## Quick start — CLI

```bash
cd hospital_patient_data_analysis
pip install -r requirements.txt
python main.py
```

This seeds the database (if empty), runs the analysis, and writes outputs to:

- `output/charts/*.png` — aggregated charts
- `output/reports/operational_report_*.txt` — full text report
- `output/reports/*.csv` — per-table CSV extracts

### CLI options
- `python main.py` — interactive menu (seed, analyze, verify, exit).
- `python main.py --no-seed` — analyse existing data without re-seeding.
- `python main.py --unrestricted` — allow raw-record access (admin/maintenance only).
- `python main.py --verify` — run acceptance-criteria verification and exit.

## Quick start — Streamlit dashboard

```bash
cd hospital_patient_data_analysis
streamlit run app.py
```

A browser window opens with KPIs, department workload, monthly trends,
age-band distribution, visit-type/gender breakdowns, summary statistics,
and a downloadable full report.

## Quick start — MySQL backend (optional)

By default SQLite is used (no server required). To use MySQL:

```bash
pip install pymysql
export HOSPITAL_DB_BACKEND=mysql
export HOSPITAL_DB_HOST=localhost
export HOSPITAL_DB_USER=root
export HOSPITAL_DB_PASSWORD=your_password
export HOSPITAL_DB_NAME=hospital_analytics
python main.py
```

## Output artifacts
- Department-wise workload report
- Monthly visit trends
- Daily visit volumes
- Age-band summary (aggregated)
- Visit-type and gender breakdowns
- Summary statistics (mean/median/std/min/max visits per day, peak day)

## Disclaimer
OPERATIONAL STATISTICS ONLY - NOT CLINICAL ADVICE. These aggregates are
derived from synthetic / de-identified hospital visit records for
educational operational analytics. They do not constitute diagnoses,
treatment recommendations, or medical guidance.
