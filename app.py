"""
Streamlit web dashboard for the Hospital Patient Data Analysis System.

Run with:
    streamlit run app.py

All figures are aggregates only and labeled as operational statistics,
not clinical advice.
"""

from __future__ import annotations

import streamlit as st

import config
from db import HospitalDB
import synthetic_data
import analysis
import visualization
import reports


st.set_page_config(
    page_title="Hospital Patient Data Analysis",
    page_icon="🏥",
    layout="wide",
)

st.title("🏥 Hospital Patient Data Analysis System")
st.caption("Educational operational analytics — synthetic / de-identified data only")

st.warning(
    "OPERATIONAL STATISTICS ONLY - NOT CLINICAL ADVICE. "
    "These aggregates are derived from synthetic / de-identified hospital "
    "visit records for educational operational analytics. They do not "
    "constitute diagnoses, treatment recommendations, or medical guidance."
)


@st.cache_resource(show_spinner=False)
def get_db():
    db = HospitalDB(restricted=True)
    db.connect()
    synthetic_data.seed_database(db)
    return db


db = get_db()

# Sidebar controls
st.sidebar.header("Controls")
if st.sidebar.button("Re-seed synthetic data"):
    synthetic_data.seed_database(db)
    st.sidebar.success("Re-seeded.")

st.sidebar.markdown("---")
st.sidebar.subheader("Database backend")
st.sidebar.code(config.DB_BACKEND)
st.sidebar.markdown("---")
st.sidebar.subheader("Access mode")
st.sidebar.code("restricted (aggregates only)")

# Load aggregates
aggregates = analysis.all_aggregates(db)
stats = analysis.summary_statistics(db)

# KPI row
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Visits", f"{stats['total_visits']:,}")
k2.metric("Days Active", stats["days_active"])
k3.metric("Mean Visits/Day", f"{stats['mean_visits_per_day']:.1f}")
k4.metric("Peak Visits/Day", stats["max_visits_per_day"])
k5.metric("Peak Date", stats["peak_date"] or "—")

st.divider()

# Department workload
st.subheader("Department-Wise Workload")
dept_df = aggregates["department_workload"]
if not dept_df.empty:
    st.dataframe(
        dept_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "share_of_total_percent": st.column_config.ProgressColumn(
                "Share %", format="%.2f%%", min_value=0, max_value=100
            ),
        },
    )
    st.image(visualization.plot_department_workload(dept_df), use_container_width=True)
else:
    st.info("No department data available.")

st.divider()

# Monthly trends
st.subheader("Visit Trends — Monthly")
monthly_df = aggregates["monthly_visits"]
if not monthly_df.empty:
    st.line_chart(
        monthly_df.set_index("month")["visit_count"],
        use_container_width=True,
    )
    st.dataframe(monthly_df, use_container_width=True, hide_index=True)
    st.image(visualization.plot_monthly_trends(monthly_df), use_container_width=True)
else:
    st.info("No monthly data available.")

st.divider()

# Age band
st.subheader("Age-Band Summary (Aggregated, Non-Identifying)")
age_df = aggregates["age_band"]
if not age_df.empty:
    st.bar_chart(age_df.set_index("age_band")["visit_count"], use_container_width=True)
    st.dataframe(age_df, use_container_width=True, hide_index=True)
    st.image(visualization.plot_age_band_distribution(age_df), use_container_width=True)
else:
    st.info("No age-band data available.")

st.divider()

# Visit type & gender
col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Visits by Visit Type")
    vtype_df = aggregates["visit_type"]
    if not vtype_df.empty:
        st.bar_chart(vtype_df.set_index("visit_type")["visit_count"], use_container_width=True)
        st.dataframe(vtype_df, use_container_width=True, hide_index=True)
        st.image(visualization.plot_visit_type(vtype_df), use_container_width=True)
    else:
        st.info("No visit-type data available.")

with col_b:
    st.subheader("Visits by Gender (Optional, De-identified)")
    gender_df = aggregates["gender"]
    if not gender_df.empty:
        st.bar_chart(gender_df.set_index("gender")["visit_count"], use_container_width=True)
        st.dataframe(gender_df, use_container_width=True, hide_index=True)
    else:
        st.info("No gender data available.")

st.divider()

# Summary statistics
st.subheader("Summary Statistics (NumPy)")
stat_rows = [
    ("Total Visits", stats["total_visits"]),
    ("Days Active", stats["days_active"]),
    ("Mean Visits/Day", f"{stats['mean_visits_per_day']:.2f}"),
    ("Median Visits/Day", f"{stats['median_visits_per_day']:.2f}"),
    ("Std Dev Visits/Day", f"{stats['std_visits_per_day']:.2f}"),
    ("Min Visits/Day", stats["min_visits_per_day"]),
    ("Max Visits/Day", stats["max_visits_per_day"]),
    ("Peak Date", stats["peak_date"] or "—"),
    ("Peak Visits", stats["peak_visits"]),
]
for label, value in stat_rows:
    st.write(f"**{label}:** {value}")

st.divider()

# Full report download
st.subheader("Download Full Report")
report_text = reports.build_text_report(db)
st.download_button(
    label="Download operational report (TXT)",
    data=report_text,
    file_name="operational_report.txt",
    mime="text/plain",
)
st.text_area("Report preview", report_text, height=300)

st.caption(config.DISCLAIMER)
