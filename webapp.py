"""
Hospital Patient Data Analysis System - Flask Web Application

Green-themed operational analytics website with:
  - Login / access control
  - Dashboard (KPIs + charts)
  - Patient management (de-identified CRUD)
  - Department management (CRUD)
  - Visit recording (CRUD + filters)
  - Reports & analysis (aggregates, date filters, CSV export)

All analytics output is aggregated and labeled as operational statistics,
not clinical advice.

Run:
    python webapp.py
    open http://localhost:5000
"""

from __future__ import annotations

import csv
import io
import os
import secrets
from datetime import date, datetime, timedelta

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    Response,
    abort,
)

import config
from db import HospitalDB
import synthetic_data
import analysis

app = Flask(
    __name__,
    template_folder="web/templates",
    static_folder="web/static",
)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

# Simple credential for educational demo access control.
DEMO_USERS = {"admin": os.environ.get("ADMIN_PASSWORD", "admin123")}

DISCLAIMER = config.DISCLAIMER


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def get_db() -> HospitalDB:
    db = HospitalDB(restricted=True)
    db.connect()
    synthetic_data.seed_database(db)  # idempotent
    return db


def is_logged_in() -> bool:
    return session.get("logged_in", False)


def login_required(f):
    from functools import wraps

    @wraps(f)
    def wrapper(*args, **kwargs):
        if not is_logged_in():
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)

    return wrapper


def fetch_aggregates(db: HospitalDB, date_from: str | None = None,
                     date_to: str | None = None) -> dict:
    """Return aggregate tables, optionally filtered by date range."""
    import pandas as pd

    # Build date filter SQL fragments (aggregate-safe).
    where = ""
    params: tuple = ()
    if date_from:
        where += " AND v.visit_date >= ?"
        params += (date_from,)
    if date_to:
        where += " AND v.visit_date <= ?"
        params += (date_to,)

    if where:
        dept_sql = f"""
            SELECT d.department_name, COUNT(*) AS visit_count,
                   COUNT(DISTINCT v.patient_id) AS unique_patients
            FROM visits v JOIN departments d ON d.department_id = v.department_id
            WHERE 1=1 {where}
            GROUP BY d.department_id, d.department_name
            ORDER BY visit_count DESC
        """
        monthly_sql = f"""
            SELECT strftime('%Y-%m', v.visit_date) AS month, COUNT(*) AS visit_count
            FROM visits v WHERE 1=1 {where}
            GROUP BY month ORDER BY month
        """
        daily_sql = f"""
            SELECT v.visit_date AS date, COUNT(*) AS visit_count
            FROM visits v WHERE 1=1 {where}
            GROUP BY v.visit_date ORDER BY v.visit_date
        """
        age_sql = f"""
            SELECT p.age_band, COUNT(*) AS visit_count,
                   COUNT(DISTINCT v.patient_id) AS unique_patients
            FROM visits v JOIN patients p ON p.patient_id = v.patient_id
            WHERE 1=1 {where}
            GROUP BY p.age_band ORDER BY
              CASE p.age_band WHEN '0-17' THEN 1 WHEN '18-29' THEN 2
                WHEN '30-44' THEN 3 WHEN '45-59' THEN 4
                WHEN '60-74' THEN 5 WHEN '75+' THEN 6 ELSE 7 END
        """
        vtype_sql = f"""
            SELECT v.visit_type, COUNT(*) AS visit_count
            FROM visits v WHERE 1=1 {where}
            GROUP BY v.visit_type ORDER BY visit_count DESC
        """
        gender_sql = f"""
            SELECT COALESCE(p.gender_optional,'Not disclosed') AS gender,
                   COUNT(*) AS visit_count
            FROM visits v JOIN patients p ON p.patient_id = v.patient_id
            WHERE 1=1 {where}
            GROUP BY gender ORDER BY visit_count DESC
        """
        stats_sql = f"""
            SELECT COUNT(*) AS total_visits,
                   COUNT(DISTINCT visit_date) AS days_active,
                   COALESCE(AVG(cnt),0) AS mean_visits,
                   COALESCE(MIN(cnt),0) AS min_visits,
                   COALESCE(MAX(cnt),0) AS max_visits
            FROM (SELECT v.visit_date AS visit_date, COUNT(*) AS cnt
                  FROM visits v WHERE 1=1 {where}
                  GROUP BY v.visit_date)
        """
    else:
        dept_sql = """
            SELECT d.department_name, COUNT(*) AS visit_count,
                   COUNT(DISTINCT v.patient_id) AS unique_patients
            FROM visits v JOIN departments d ON d.department_id = v.department_id
            GROUP BY d.department_id, d.department_name
            ORDER BY visit_count DESC
        """
        monthly_sql = """
            SELECT strftime('%Y-%m', visit_date) AS month, COUNT(*) AS visit_count
            FROM visits GROUP BY month ORDER BY month
        """
        daily_sql = """
            SELECT visit_date AS date, COUNT(*) AS visit_count
            FROM visits GROUP BY visit_date ORDER BY visit_date
        """
        age_sql = """
            SELECT p.age_band, COUNT(*) AS visit_count,
                   COUNT(DISTINCT v.patient_id) AS unique_patients
            FROM visits v JOIN patients p ON p.patient_id = v.patient_id
            GROUP BY p.age_band ORDER BY
              CASE p.age_band WHEN '0-17' THEN 1 WHEN '18-29' THEN 2
                WHEN '30-44' THEN 3 WHEN '45-59' THEN 4
                WHEN '60-74' THEN 5 WHEN '75+' THEN 6 ELSE 7 END
        """
        vtype_sql = """
            SELECT visit_type, COUNT(*) AS visit_count
            FROM visits GROUP BY visit_type ORDER BY visit_count DESC
        """
        gender_sql = """
            SELECT COALESCE(p.gender_optional,'Not disclosed') AS gender,
                   COUNT(*) AS visit_count
            FROM visits v JOIN patients p ON p.patient_id = v.patient_id
            GROUP BY gender ORDER BY visit_count DESC
        """
        stats_sql = """
            SELECT COUNT(*) AS total_visits,
                   COUNT(DISTINCT visit_date) AS days_active,
                   COALESCE(AVG(cnt),0) AS mean_visits,
                   COALESCE(MIN(cnt),0) AS min_visits,
                   COALESCE(MAX(cnt),0) AS max_visits
            FROM (SELECT visit_date, COUNT(*) AS cnt
                  FROM visits GROUP BY visit_date)
        """

    def q(sql, p=()):
        with db.cursor() as cur:
            cur.execute(sql, p)
            return [dict(r) for r in cur.fetchall()]

    dept = q(dept_sql, params)
    monthly = q(monthly_sql, params)
    daily = q(daily_sql, params)
    age = q(age_sql, params)
    vtype = q(vtype_sql, params)
    gender = q(gender_sql, params)
    stats = q(stats_sql, params)[0]

    total = stats.get("total_visits") or 0
    for rows in (dept, age, vtype, gender):
        for r in rows:
            r["share"] = round((r["visit_count"] / total * 100) if total else 0, 2)

    # Peak day
    peak = max(daily, key=lambda r: r["visit_count"]) if daily else None

    return {
        "dept": dept, "monthly": monthly, "daily": daily, "age": age,
        "vtype": vtype, "gender": gender, "stats": stats, "peak": peak,
    }


def kpis_today_month(db: HospitalDB) -> dict:
    today = date.today().isoformat()
    month_prefix = date.today().strftime("%Y-%m")
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM visits WHERE visit_date = ?", (today,))
        today_count = cur.fetchone()["c"]
        cur.execute(
            "SELECT COUNT(*) AS c FROM visits WHERE strftime('%Y-%m', visit_date) = ?",
            (month_prefix,),
        )
        month_count = cur.fetchone()["c"]
        cur.execute(
            """SELECT d.department_name, COUNT(*) AS c FROM visits v
               JOIN departments d ON d.department_id = v.department_id
               GROUP BY d.department_id ORDER BY c DESC LIMIT 1"""
        )
        row = cur.fetchone()
        busiest = dict(row) if row else {"department_name": "-", "c": 0}
        cur.execute("SELECT COUNT(*) AS c FROM visits")
        total = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM patients")
        patients = cur.fetchone()["c"]
    return {
        "total_visits": total,
        "today_visits": today_count,
        "month_visits": month_count,
        "busiest": busiest["department_name"],
        "busiest_count": busiest["c"],
        "total_patients": patients,
    }


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("username", "").strip()
        pwd = request.form.get("password", "")
        if user in DEMO_USERS and DEMO_USERS[user] == pwd:
            session["logged_in"] = True
            session["user"] = user
            nxt = request.args.get("next") or url_for("dashboard")
            return redirect(nxt)
        flash("Invalid username or password.", "danger")
    return render_template("login.html", disclaimer=DISCLAIMER)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
@app.route("/")
@login_required
def dashboard():
    db = get_db()
    try:
        agg = fetch_aggregates(db)
        kpi = kpis_today_month(db)
        chart = {
            "dept_labels": [r["department_name"] for r in agg["dept"]],
            "dept_values": [r["visit_count"] for r in agg["dept"]],
            "month_labels": [r["month"] for r in agg["monthly"]],
            "month_values": [r["visit_count"] for r in agg["monthly"]],
            "age_labels": [r["age_band"] for r in agg["age"]],
            "age_values": [r["visit_count"] for r in agg["age"]],
            "vtype_labels": [r["visit_type"] for r in agg["vtype"]],
            "vtype_values": [r["visit_count"] for r in agg["vtype"]],
        }
        return render_template(
            "dashboard.html", kpi=kpi, chart=chart, agg=agg,
            disclaimer=DISCLAIMER, user=session.get("user"),
        )
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# Patients (de-identified CRUD)
# --------------------------------------------------------------------------- #
@app.route("/patients")
@login_required
def patients():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """SELECT p.patient_id, p.age_band, p.gender_optional,
                          COUNT(v.visit_id) AS visit_count
                   FROM patients p LEFT JOIN visits v ON v.patient_id = p.patient_id
                   GROUP BY p.patient_id ORDER BY p.patient_id"""
            )
            rows = [dict(r) for r in cur.fetchall()]
        return render_template(
            "patients.html", rows=rows, age_bands=config.AGE_BANDS,
            genders=config.GENDERS, disclaimer=DISCLAIMER,
            user=session.get("user"),
        )
    finally:
        db.close()


@app.route("/patients/add", methods=["POST"])
@login_required
def patient_add():
    age_band = request.form.get("age_band", "")
    gender = request.form.get("gender", "")
    if age_band not in config.AGE_BANDS:
        flash("Invalid age band.", "warning")
        return redirect(url_for("patients"))
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO patients (age_band, gender_optional) VALUES (?, ?)",
                (age_band, gender or None),
            )
        db._conn.commit()
        flash("Synthetic patient record added (de-identified).", "success")
    finally:
        db.close()
    return redirect(url_for("patients"))


@app.route("/patients/<int:pid>/delete", methods=["POST"])
@login_required
def patient_delete(pid: int):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("DELETE FROM visits WHERE patient_id = ?", (pid,))
            cur.execute("DELETE FROM patients WHERE patient_id = ?", (pid,))
        db._conn.commit()
        flash("Patient record and linked visits removed.", "info")
    finally:
        db.close()
    return redirect(url_for("patients"))


# --------------------------------------------------------------------------- #
# Departments CRUD
# --------------------------------------------------------------------------- #
@app.route("/departments")
@login_required
def departments():
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                """SELECT d.department_id, d.department_name,
                          COUNT(v.visit_id) AS visit_count
                   FROM departments d LEFT JOIN visits v
                     ON v.department_id = d.department_id
                   GROUP BY d.department_id ORDER BY d.department_name"""
            )
            rows = [dict(r) for r in cur.fetchall()]
        return render_template(
            "departments.html", rows=rows, disclaimer=DISCLAIMER,
            user=session.get("user"),
        )
    finally:
        db.close()


@app.route("/departments/add", methods=["POST"])
@login_required
def department_add():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Department name is required.", "warning")
        return redirect(url_for("departments"))
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO departments (department_name) VALUES (?)", (name,)
            )
        db._conn.commit()
        flash(f"Department '{name}' added.", "success")
    except Exception:
        flash("Department already exists.", "warning")
    finally:
        db.close()
    return redirect(url_for("departments"))


@app.route("/departments/<int:did>/update", methods=["POST"])
@login_required
def department_update(did: int):
    name = request.form.get("name", "").strip()
    if name:
        db = get_db()
        try:
            with db.cursor() as cur:
                cur.execute(
                    "UPDATE departments SET department_name = ? WHERE department_id = ?",
                    (name, did),
                )
            db._conn.commit()
            flash("Department updated.", "success")
        finally:
            db.close()
    return redirect(url_for("departments"))


@app.route("/departments/<int:did>/delete", methods=["POST"])
@login_required
def department_delete(did: int):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS c FROM visits WHERE department_id = ?", (did,)
            )
            if cur.fetchone()["c"] > 0:
                flash(
                    "Cannot delete: department still has recorded visits.",
                    "warning",
                )
                return redirect(url_for("departments"))
            cur.execute("DELETE FROM departments WHERE department_id = ?", (did,))
        db._conn.commit()
        flash("Department removed.", "info")
    finally:
        db.close()
    return redirect(url_for("departments"))


# --------------------------------------------------------------------------- #
# Visits CRUD + filters
# --------------------------------------------------------------------------- #
@app.route("/visits")
@login_required
def visits():
    dept_filter = request.args.get("department", "")
    type_filter = request.args.get("visit_type", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    db = get_db()
    try:
        with db.cursor() as cur:
            where, params = [], []
            if dept_filter:
                where.append("v.department_id = ?")
                params.append(dept_filter)
            if type_filter:
                where.append("v.visit_type = ?")
                params.append(type_filter)
            if date_from:
                where.append("v.visit_date >= ?")
                params.append(date_from)
            if date_to:
                where.append("v.visit_date <= ?")
                params.append(date_to)
            clause = (" WHERE " + " AND ".join(where)) if where else ""

            cur.execute(
                f"""SELECT v.visit_id, v.patient_id, v.visit_date, v.visit_type,
                           d.department_name
                    FROM visits v
                    JOIN departments d ON d.department_id = v.department_id
                    {clause}
                    ORDER BY v.visit_date DESC, v.visit_id DESC LIMIT 500""",
                tuple(params),
            )
            rows = [dict(r) for r in cur.fetchall()]

            cur.execute(
                "SELECT department_id, department_name FROM departments ORDER BY department_name"
            )
            dept_options = [dict(r) for r in cur.fetchall()]

            cur.execute(
                "SELECT COUNT(*) AS c FROM visits v " + clause, tuple(params)
            )
            total_matching = cur.fetchone()["c"]

        return render_template(
            "visits.html", rows=rows, dept_options=dept_options,
            visit_types=config.VISIT_TYPES, total_matching=total_matching,
            filters={"department": dept_filter, "visit_type": type_filter,
                     "date_from": date_from, "date_to": date_to},
            disclaimer=DISCLAIMER, user=session.get("user"),
        )
    finally:
        db.close()


@app.route("/visits/add", methods=["POST"])
@login_required
def visit_add():
    patient_id = request.form.get("patient_id", "").strip()
    department_id = request.form.get("department_id", "").strip()
    visit_date = request.form.get("visit_date", "").strip()
    visit_type = request.form.get("visit_type", "").strip()

    if not (patient_id and department_id and visit_date and visit_type):
        flash("All fields are required.", "warning")
        return redirect(url_for("visits"))
    if visit_type not in config.VISIT_TYPES:
        flash("Invalid visit type.", "warning")
        return redirect(url_for("visits"))
    try:
        datetime.strptime(visit_date, "%Y-%m-%d")
    except ValueError:
        flash("Invalid date format (use YYYY-MM-DD).", "warning")
        return redirect(url_for("visits"))

    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("SELECT 1 FROM patients WHERE patient_id = ?", (int(patient_id),))
            if not cur.fetchone():
                flash("Patient ID does not exist.", "warning")
                return redirect(url_for("visits"))
            cur.execute(
                "SELECT 1 FROM departments WHERE department_id = ?", (int(department_id),)
            )
            if not cur.fetchone():
                flash("Department does not exist.", "warning")
                return redirect(url_for("visits"))
            cur.execute(
                """INSERT INTO visits (patient_id, department_id, visit_date, visit_type)
                   VALUES (?, ?, ?, ?)""",
                (int(patient_id), int(department_id), visit_date, visit_type),
            )
        db._conn.commit()
        flash("Visit recorded successfully.", "success")
    except Exception as exc:  # noqa: BLE001
        flash(f"Error recording visit: {exc}", "danger")
    finally:
        db.close()
    return redirect(url_for("visits"))


@app.route("/visits/<int:vid>/delete", methods=["POST"])
@login_required
def visit_delete(vid: int):
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute("DELETE FROM visits WHERE visit_id = ?", (vid,))
        db._conn.commit()
        flash("Visit record removed.", "info")
    finally:
        db.close()
    return redirect(url_for("visits"))


# --------------------------------------------------------------------------- #
# Reports & analysis (aggregates + CSV export)
# --------------------------------------------------------------------------- #
@app.route("/reports")
@login_required
def reports():
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    db = get_db()
    try:
        agg = fetch_aggregates(db, date_from or None, date_to or None)
        stats = agg["stats"]
        chart = {
            "dept_labels": [r["department_name"] for r in agg["dept"]],
            "dept_values": [r["visit_count"] for r in agg["dept"]],
            "month_labels": [r["month"] for r in agg["monthly"]],
            "month_values": [r["visit_count"] for r in agg["monthly"]],
            "daily_labels": [r["date"] for r in agg["daily"]],
            "daily_values": [r["visit_count"] for r in agg["daily"]],
            "age_labels": [r["age_band"] for r in agg["age"]],
            "age_values": [r["visit_count"] for r in agg["age"]],
        }
        return render_template(
            "reports.html", agg=agg, stats=stats, chart=chart,
            date_from=date_from, date_to=date_to,
            disclaimer=DISCLAIMER, user=session.get("user"),
        )
    finally:
        db.close()


EXPORTS = {
    "department_workload": ("Department-wise workload", "dept"),
    "monthly_visits": ("Monthly visit trend", "monthly"),
    "daily_visits": ("Daily visit volumes", "daily"),
    "age_band": ("Age-band summary", "age"),
    "visit_type": ("Visits by visit type", "vtype"),
    "gender": ("Visits by gender", "gender"),
}


@app.route("/export/<name>")
@login_required
def export_csv(name: str):
    if name not in EXPORTS:
        abort(404)
    label, key = EXPORTS[name]
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    db = get_db()
    try:
        agg = fetch_aggregates(db, date_from or None, date_to or None)
        rows = agg.get(key, [])
        if not rows:
            return Response(
                f"# {DISCLAIMER}\n# No data for {label}\n",
                mimetype="text/csv",
                headers={"Content-Disposition": f"attachment; filename={name}.csv"},
            )
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        csv_data = output.getvalue()
        # Prepend disclaimer as comment lines
        preamble = f"# {DISCLAIMER}\n# {label}\n"
        return Response(
            preamble + csv_data,
            mimetype="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={name}.csv"
            },
        )
    finally:
        db.close()


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    print("=" * 60)
    print("Hospital Patient Data Analysis System - Web Site")
    print("Local URL : http://localhost:5000")
    print("Login     : admin / admin123")
    print(DISCLAIMER)
    print("=" * 60)
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=False,
    )
