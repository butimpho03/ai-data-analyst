"""
AI Data Analyst Assistant — Phase 3: data-quality inspection.

WHAT THIS FILE IS:
The single entry point Streamlit runs. As of Phase 3, uploaded files are
automatically checked for missing values, duplicates, inconsistent
categories, invalid dates, stray whitespace, and outliers. Nothing is ever
changed automatically — findings are only reported. Analysis, AI, and
charts are still placeholders for later phases.
"""

import streamlit as st

from data_loader import load_dataset
from data_quality import inspect_dataset

# st.set_page_config MUST be the first Streamlit command in the file.
# WHY: it configures the browser tab (title, icon, mobile-friendly wide/centered
# layout) before anything else renders.
st.set_page_config(
    page_title="AI Data Analyst",
    page_icon="📊",
    layout="centered",  # "centered" reads better on a phone screen than "wide"
)

st.title("📊 AI Data Analyst")
st.caption("Upload a dataset, ask a question, get a professional analysis.")

# --- Section 1: Upload Dataset ---
st.header("1. Upload Dataset")
uploaded_file = st.file_uploader(
    "Upload an Excel (.xlsx) or CSV file",
    type=["xlsx", "csv"],
)

# WHY st.session_state:
# Streamlit re-runs this entire file top-to-bottom every time you interact
# with the page (upload a file, type in a box, click a button). Without
# session_state, the dataframe we just loaded would be forgotten the moment
# you, say, typed a letter into the question box below. session_state is a
# dictionary-like storage that survives across those re-runs, tied to your
# browser session.
if uploaded_file is not None:
    df, error, notice = load_dataset(uploaded_file)
    if error:
        st.error(error)
        st.session_state["df"] = None
    else:
        st.session_state["df"] = df
        st.success(f"Loaded **{uploaded_file.name}** — {df.shape[0]} rows, {df.shape[1]} columns.")
        if notice:
            st.warning(notice)

# --- Section 2: Dataset Preview ---
st.header("2. Dataset Preview")
if st.session_state.get("df") is not None:
    df = st.session_state["df"]
    st.dataframe(df.head(10), use_container_width=True)
    st.caption(f"Showing the first 10 of {df.shape[0]} rows.")

    with st.expander("Column details"):
        # dtype tells us what pandas thinks each column contains, e.g.
        # int64 (whole numbers), float64 (decimals), object (text/mixed).
        # This is a first, rough look — Phase 3 will do proper type/quality
        # checking, since pandas' guesses aren't always right (e.g. dates
        # often get read in as plain text).
        info = df.dtypes.reset_index()
        info.columns = ["Column", "Detected type"]
        st.dataframe(info, use_container_width=True, hide_index=True)
else:
    st.write("Upload a file above to see a preview here.")

# --- Section 3: Data Quality ---
st.header("3. Data Quality")
if st.session_state.get("df") is not None:
    df = st.session_state["df"]
    findings = inspect_dataset(df)

    if not findings:
        st.success("No data-quality issues detected.")
    else:
        warnings = [f for f in findings if f["severity"] == "warning"]
        infos = [f for f in findings if f["severity"] == "info"]
        st.write(
            f"Found **{len(warnings)} issue(s) worth checking** and "
            f"**{len(infos)} minor note(s)** before analysing this data."
        )

        # WHY WE SEPARATE WARNING vs INFO:
        # "warning" issues are more likely to skew a calculation (missing
        # values, duplicates, mismatched categories). "info" issues are
        # worth knowing but less likely to break a result (outliers,
        # stray whitespace). Showing warnings first helps you prioritise.
        for finding in warnings:
            st.warning(f"**{finding['title']}**\n\n{finding['detail']}")
        for finding in infos:
            st.info(f"**{finding['title']}**\n\n{finding['detail']}")

    st.caption(
        "Nothing above has been changed or removed from your data — "
        "these are just things to be aware of. Cleaning tools are coming "
        "in a later phase."
    )
else:
    st.write("Upload a file above to see data-quality checks here.")

# --- Section 4: Ask Your Question ---
st.header("4. Ask Your Question")
question = st.text_area(
    "Type a business question about your data",
    placeholder="e.g. Which store has the highest average sales?",
)

# --- Section 5: Analysis button ---
if st.button("Analyse", type="primary", use_container_width=True):
    st.warning("The analysis engine isn't built yet — coming in Phase 5.")

# --- Section 6: Results ---
st.header("6. Results")
st.write("Tables and calculation results will appear here.")

# --- Section 7: Charts ---
st.header("7. Charts")
st.write("Charts will appear here.")

# --- Section 8: Business Summary ---
st.header("8. Business Summary")
st.write("A written, manager-friendly summary will appear here.")
