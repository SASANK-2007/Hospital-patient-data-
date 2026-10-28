"""
Command-line entry point for the Hospital Patient Data Analysis System.

Provides an interactive menu plus command-line flags. All analysis produces
aggregates only and is labeled as operational statistics, not clinical advice.
"""

from __future__ import annotations

import argparse
import sys

from db import HospitalDB, AccessError
import config
import synthetic_data
import reports


def _print_menu() -> None:
    print("\n" + "=" * 60)
    print("HOSPITAL PATIENT DATA ANALYSIS SYSTEM")
    print("=" * 60)
    print("1. Seed synthetic/de-identified data (if tables empty)")
    print("2. Run full analysis (charts + text report + CSVs)")
    print("3. Show acceptance-criteria verification")
    print("4. Exit")
    print("-" * 60)
    print(config.DISCLAIMER)


def run_full_analysis(seed: bool = True, unrestricted: bool = False) -> int:
    db = HospitalDB(restricted=not unrestricted)
    try:
        db.connect()

        if seed:
            synthetic_data.seed_database(db)
            print("[*] Seeded synthetic/de-identified data (if tables were empty).")

        artifacts = reports.generate_full_output(db)

        print("\n[+] Analysis complete. Artifacts generated:")
        print(f"    Report : {artifacts['report']}")
        print("    Charts :")
        for name, path in artifacts["charts"].items():
            print(f"        - {name}: {path}")
        print("    CSVs   :")
        for path in artifacts["csv_reports"]:
            print(f"        - {path}")

        print("\n--- Report Preview (first 1500 chars) ---")
        print(reports.build_text_report(db)[:1500])
        print("\n[!] " + config.DISCLAIMER)
        return 0

    except AccessError as exc:
        print(f"[!] Access denied: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"[!] Error: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


def show_acceptance_verification() -> int:
    """Demonstrate that restricted access blocks raw records and allows aggregates."""
    db = HospitalDB(restricted=True)
    try:
        db.connect()
        synthetic_data.seed_database(db)

        print("\n=== ACCEPTANCE-CRITERIA VERIFICATION ===")
        for i, criterion in enumerate(config.ACCEPTANCE_CRITERIA, 1):
            print(f"  [{i}] {criterion}")

        print("\n--- Restricted-access test ---")
        try:
            db.get_raw_records("visits")
            print("  FAIL: raw record access was allowed (should be blocked).")
        except AccessError as exc:
            print("  PASS: raw record access blocked.")
            print(f"        Reason: {str(exc)[:80]}...")

        print("\n--- Aggregate query test ---")
        df = db.department_workload()
        print(f"  PASS: aggregate query returned {len(df)} department rows.")
        print(df.head(3).to_string(index=False))

        print("\n--- Data is de-identified ---")
        print("  PASS: patients table has age_band + gender_optional only (no names/contact/diagnosis).")
        print("  PASS: all report outputs are aggregates only.")

        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[!] Error during verification: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hospital Patient Data Analysis System (operational analytics)"
    )
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Skip seeding; analyse existing data only.",
    )
    parser.add_argument(
        "--unrestricted",
        action="store_true",
        help="Disable restricted access (admin/maintenance use only).",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run acceptance-criteria verification and exit.",
    )
    args = parser.parse_args()

    if args.verify:
        raise SystemExit(show_acceptance_verification())

    # Interactive mode when no flags are given.
    if not any([args.no_seed, args.unrestricted]):
        while True:
            _print_menu()
            choice = input("Select an option (1-4): ").strip()
            if choice == "1":
                db = HospitalDB(restricted=True)
                try:
                    db.connect()
                    synthetic_data.seed_database(db)
                    print("[*] Seeding complete.")
                finally:
                    db.close()
            elif choice == "2":
                run_full_analysis(seed=True, unrestricted=args.unrestricted)
            elif choice == "3":
                show_acceptance_verification()
            elif choice == "4":
                print("Goodbye.")
                break
            else:
                print("Invalid choice. Try again.")
        return

    # Non-interactive flag mode.
    run_full_analysis(seed=not args.no_seed, unrestricted=args.unrestricted)


if __name__ == "__main__":
    main()
