"""
Database layer for the Hospital Patient Data Analysis System.

Design principles (acceptance criteria):
  * Synthetic / de-identified data only.
  * Restricted access to raw records — the default path only exposes
    aggregated data suitable for analysis and reporting.
  * All results are labeled as operational statistics, not clinical advice.

The default backend is SQLite (no external server required). Set
HOSPITAL_DB_BACKEND=mysql plus the HOSPITAL_DB_* env vars to use MySQL.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Optional

import pandas as pd

import config


class AccessError(PermissionError):
    """Raised when an operation violates the restricted-access policy."""


class HospitalDB:
    """
    Wrapper around the hospital analytics database.

    Parameters
    ----------
    restricted : bool
        When True (default), raw-record access is blocked. Only aggregate
        queries are permitted through the public API.
    """

    SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS departments (
        department_id   INTEGER PRIMARY KEY AUTOINCREMENT,
        department_name   TEXT NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS patients (
        patient_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        age_band        TEXT NOT NULL,
        gender_optional TEXT
    );

    CREATE TABLE IF NOT EXISTS visits (
        visit_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id    INTEGER NOT NULL,
        department_id INTEGER NOT NULL,
        visit_date    TEXT NOT NULL,       -- ISO-8601 date (YYYY-MM-DD)
        visit_type    TEXT NOT NULL,
        FOREIGN KEY (patient_id)    REFERENCES patients(patient_id),
        FOREIGN KEY (department_id) REFERENCES departments(department_id)
    );

    CREATE INDEX IF NOT EXISTS idx_visits_date ON visits(visit_date);
    CREATE INDEX IF NOT EXISTS idx_visits_dept ON visits(department_id);
    CREATE INDEX IF NOT EXISTS idx_visits_patient ON visits(patient_id);
    """

    def __init__(self, db_path: str | None = None, restricted: bool = True):
        self.db_path = db_path or str(config.DB_PATH)
        self.restricted = restricted
        self._conn: Optional[sqlite3.Connection] = None
        self._mysql = False

    # ------------------------------------------------------------------ #
    # Connection management
    # ------------------------------------------------------------------ #
    def connect(self) -> "HospitalDB":
        if config.DB_BACKEND == "mysql":
            return self._connect_mysql()
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._initialize_schema()
        return self

    def _connect_mysql(self) -> "HospitalDB":
        try:
            import pymysql  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dep
            raise ImportError(
                "MySQL backend requested but 'pymysql' is not installed. "
                "Install it with: pip install pymysql"
            ) from exc
        self._conn = pymysql.connect(
            host=config.MYSQL_CONFIG["host"],
            port=config.MYSQL_CONFIG["port"],
            user=config.MYSQL_CONFIG["user"],
            password=config.MYSQL_CONFIG["password"],
            database=config.MYSQL_CONFIG["database"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
        )
        self._mysql = True
        self._initialize_schema()
        return self

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @contextmanager
    def cursor(self):
        if self._conn is None:
            raise RuntimeError("Database not connected. Call .connect() first.")
        cur = self._conn.cursor()
        try:
            yield cur
        finally:
            cur.close()

    def _initialize_schema(self) -> None:
        with self.cursor() as cur:
            if self._mysql:
                schema = """
                CREATE TABLE IF NOT EXISTS departments (
                    department_id INT AUTO_INCREMENT PRIMARY KEY,
                    department_name VARCHAR(100) NOT NULL UNIQUE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

                CREATE TABLE IF NOT EXISTS patients (
                    patient_id INT AUTO_INCREMENT PRIMARY KEY,
                    age_band VARCHAR(20) NOT NULL,
                    gender_optional VARCHAR(30)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

                CREATE TABLE IF NOT EXISTS visits (
                    visit_id INT AUTO_INCREMENT PRIMARY KEY,
                    patient_id INT NOT NULL,
                    department_id INT NOT NULL,
                    visit_date DATE NOT NULL,
                    visit_type VARCHAR(50) NOT NULL,
                    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
                    FOREIGN KEY (department_id) REFERENCES departments(department_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """
                for stmt in filter(None, schema.split(";")):
                    cur.execute(stmt)
            else:
                cur.executescript(self.SCHEMA_SQL)
        self._conn.commit()

    # ------------------------------------------------------------------ #
    # Restricted access helpers
    # ------------------------------------------------------------------ #
    def _enforce_restricted(self, operation: str) -> None:
        if self.restricted:
            raise AccessError(
                f"Restricted access is enabled: '{operation}' is not permitted. "
                "Use the aggregate query methods instead."
            )

    def get_raw_records(self, table: str, limit: int = 100) -> list[dict]:
        """
        Return raw records from a table.

        Blocked when restricted=True. Only an explicitly unrestricted
        instance (admin/maintenance use) may call this.
        """
        self._enforce_restricted(f"get_raw_records({table})")
        allowed = {"departments", "patients", "visits"}
        if table not in allowed:
            raise ValueError(f"Unknown table: {table}")
        with self.cursor() as cur:
            cur.execute(f"SELECT * FROM {table} LIMIT %s", (limit,))
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def execute_query(self, sql: str, params: tuple = ()) -> list[dict]:
        """
        Execute a read-only query.

        When restricted=True, the query must be a SELECT that contains an
        aggregate function or a GROUP BY clause — raw row dumps are
        rejected so that only aggregates leave the database layer.
        """
        if not sql or not sql.strip().lower().startswith("select"):
            raise AccessError("Only SELECT queries are permitted.")

        if self.restricted:
            lowered = sql.lower()
            has_aggregate = any(
                fn in lowered for fn in ("count(", "sum(", "avg(", "min(", "max(")
            )
            has_group_by = "group by" in lowered
            if not (has_aggregate or has_group_by):
                raise AccessError(
                    "Restricted mode: queries must return aggregated data "
                    "(include COUNT/SUM/AVG/MIN/MAX or GROUP BY)."
                )

        with self.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # Data loading for analysis
    # ------------------------------------------------------------------ #
    def load_visits_dataframe(self) -> pd.DataFrame:
        """Load visits joined with patients and departments as a DataFrame."""
        sql = """
        SELECT
            v.visit_id,
            v.patient_id,
            v.department_id,
            d.department_name,
            v.visit_date,
            v.visit_type,
            p.age_band,
            p.gender_optional
        FROM visits AS v
        JOIN departments AS d ON d.department_id = v.department_id
        JOIN patients   AS p ON p.patient_id = v.patient_id
        ORDER BY v.visit_date
        """
        rows = self.execute_query(sql)
        df = pd.DataFrame(rows)
        if not df.empty:
            df["visit_date"] = pd.to_datetime(df["visit_date"])
        return df

    # Convenience aggregate loaders used by the analysis module.
    def department_workload(self) -> pd.DataFrame:
        sql = """
        SELECT
            d.department_name,
            COUNT(*) AS visit_count,
            COUNT(DISTINCT v.patient_id) AS unique_patients
        FROM visits AS v
        JOIN departments AS d ON d.department_id = v.department_id
        GROUP BY d.department_id, d.department_name
        ORDER BY visit_count DESC
        """
        return pd.DataFrame(self.execute_query(sql))

    def monthly_visits(self) -> pd.DataFrame:
        sql = """
        SELECT
            strftime('%Y-%m', visit_date) AS month,
            COUNT(*) AS visit_count
        FROM visits
        GROUP BY month
        ORDER BY month
        """
        df = pd.DataFrame(self.execute_query(sql))
        if not df.empty:
            df["month"] = pd.to_datetime(df["month"] + "-01")
        return df

    def daily_visits(self) -> pd.DataFrame:
        sql = """
        SELECT
            visit_date AS date,
            COUNT(*) AS visit_count
        FROM visits
        GROUP BY visit_date
        ORDER BY visit_date
        """
        df = pd.DataFrame(self.execute_query(sql))
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
        return df

    def age_band_summary(self) -> pd.DataFrame:
        sql = """
        SELECT
            p.age_band,
            COUNT(*) AS visit_count,
            COUNT(DISTINCT v.patient_id) AS unique_patients
        FROM visits AS v
        JOIN patients AS p ON p.patient_id = v.patient_id
        GROUP BY p.age_band
        ORDER BY
            CASE p.age_band
                WHEN '0-17' THEN 1
                WHEN '18-29' THEN 2
                WHEN '30-44' THEN 3
                WHEN '45-59' THEN 4
                WHEN '60-74' THEN 5
                WHEN '75+' THEN 6
                ELSE 7
            END
        """
        return pd.DataFrame(self.execute_query(sql))

    def visit_type_summary(self) -> pd.DataFrame:
        sql = """
        SELECT
            v.visit_type,
            COUNT(*) AS visit_count
        FROM visits AS v
        GROUP BY v.visit_type
        ORDER BY visit_count DESC
        """
        return pd.DataFrame(self.execute_query(sql))

    def gender_summary(self) -> pd.DataFrame:
        sql = """
        SELECT
            COALESCE(p.gender_optional, 'Not disclosed') AS gender,
            COUNT(*) AS visit_count
        FROM visits AS v
        JOIN patients AS p ON p.patient_id = v.patient_id
        GROUP BY gender
        ORDER BY visit_count DESC
        """
        return pd.DataFrame(self.execute_query(sql))
