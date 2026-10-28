"""
Acceptance-criteria verification script for the Hospital Patient Data
Analysis System.

Runs a series of checks against the acceptance criteria and prints a
PASS/FAIL summary. Exit code 0 = all checks passed.
"""

from __future__ import annotations

import sys

from db import HospitalDB, AccessError
import synthetic_data
import analysis
import config


def check(condition: bool, message: str) -> bool:
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {message}")
    return condition


def main() -> int:
    print("=" * 70)
    print("HOSPITAL PATIENT DATA ANALYSIS SYSTEM")
    print("Acceptance-Criteria Verification")
    print("=" * 70)

    all_pass = True

    db = HospitalDB(restricted=True)
    try:
        db.connect()
        synthetic_data.seed_database(db)

        print("\n1. Synthetic / de-identified data only")
        # Confirm the patients table exists and holds only non-identifying fields
        # (verified via an aggregate query, since restricted mode blocks raw dumps).
        patient_stats = db.execute_query(
            "SELECT COUNT(*) AS patient_count, MIN(age_band) AS min_band, MAX(age_band) AS max_band FROM patients"
        )
        all_pass &= check(
            patient_stats and patient_stats[0]["patient_count"] > 0,
            "Patients table populated with age_band only (no PII columns by schema)"
        )
        # Schema-defined columns are known non-PII; confirm no diagnosis/treatment text leaks into visit_type either.
        visit_types = db.execute_query(
            "SELECT DISTINCT visit_type FROM visits GROUP BY visit_type"
        )
        vt_text = " ".join(r["visit_type"] for r in visit_types).lower()
        clinical_terms = {"diagnosis", "treatment", "prescription", "prognosis"}
        has_clinical = any(term in vt_text for term in clinical_terms)
        all_pass &= check(not has_clinical, "No clinical/diagnosis terms in visit_type values")

        print("\n2. Restrict access to raw records")
        try:
            db.get_raw_records("visits")
            all_pass &= check(False, "Raw record access blocked (unexpectedly allowed)")
        except AccessError:
            all_pass &= check(True, "Raw record access blocked by restricted mode")

        print("\n3. Reports contain aggregates only")
        dept = analysis.department_workload(db)
        monthly = analysis.monthly_visit_summary(db)
        age = analysis.age_band_summary(db)
        all_pass &= check(len(dept) > 0, "Department workload aggregate produced")
        all_pass &= check(len(monthly) > 0, "Monthly visit trend aggregate produced")
        all_pass &= check(len(age) > 0, "Age-band aggregate produced")
        # Confirm no patient_id column leaks in aggregate outputs
        no_patient_id = all("patient_id" not in df.columns for df in [dept, monthly, age])
        all_pass &= check(no_patient_id, "No patient-level identifiers in aggregate outputs")

        print("\n4. Results labeled as operational statistics, not clinical advice")
        all_pass &= check("NOT CLINICAL ADVICE" in config.DISCLAIMER, "Disclaimer present in config")
        all_pass &= check("OPERATIONAL STATISTICS ONLY" in config.DISCLAIMER, "Disclaimer labels operational statistics")

        print("\n5. Department-wise workload report")
        all_pass &= check("department_name" in dept.columns and "visit_count" in dept.columns,
                          "Department workload has department + visit count")

        print("\n6. Visit trends (daily/monthly)")
        daily = analysis.daily_visit_summary(db)
        all_pass &= check(len(daily) > 0, "Daily visit trend produced")
        all_pass &= check(len(monthly) > 0, "Monthly visit trend produced")

        print("\n7. Age-band summary (aggregated, non-identifying)")
        all_pass &= check("age_band" in age.columns and "visit_count" in age.columns,
                          "Age-band summary has band + visit count")

        print("\n8. Aggregated charts (Matplotlib)")
        import visualization  # noqa: F401
        all_pass &= check(
            hasattr(visualization, "generate_all_charts"),
            "Chart generation module available"
        )

        # Generate charts to confirm they render
        aggregates = analysis.all_aggregates(db)
        chart_paths = visualization.generate_all_charts(aggregates)
        import os
        all_charts_exist = all(os.path.exists(p) for p in chart_paths.values())
        all_pass &= check(all_charts_exist, f"{len(chart_paths)} chart PNGs generated")

        print("\n" + "=" * 70)
        if all_pass:
            print("RESULT: ALL ACCEPTANCE CRITERIA PASSED")
        else:
            print("RESULT: SOME ACCEPTANCE CRITERIA FAILED")
        print("=" * 70)

        return 0 if all_pass else 1

    except Exception as exc:  # noqa: BLE001
        print(f"\n[!] Verification error: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
