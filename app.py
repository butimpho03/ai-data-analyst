"""
AI Data Analyst Assistant — Phase 2: file upload + dataset preview.

WHAT THIS FILE IS:
The single entry point Streamlit runs. As of Phase 2, it can now actually
read an uploaded .csv or .xlsx file and show a preview table. Data-quality
checks, analysis, AI, and charts are still placeholders for later phases.
"""

import streamlit as st

from data_loader import load_dataset

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
    df, error = load_dataset(uploaded_file)
    if error:
        st.error(error)
        st.session_state["df"] = None
    else:
        st.session_state["df"] = df
        st.success(f"Loaded **{uploaded_file.name}** — {df.shape[0]} rows, {df.shape[1]} columns.")

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

# --- Section 3: Ask Your Question ---
st.header("3. Ask Your Question")
question = st.text_area(
    "Type a business question about your data",
    placeholder="e.g. Which store has the highest average sales?",
)

# --- Section 4: Analysis button ---
if st.button("Analyse", type="primary", use_container_width=True):
    st.warning("The analysis engine isn't built yet — coming in Phase 5.")

# --- Section 5: Results ---
st.header("5. Results")
st.write("Tables and calculation results will appear here.")

# --- Section 6: Charts ---
st.header("6. Charts")
st.write("Charts will appear here.")

# --- Section 7: Business Summary ---
st.header("7. Business Summary")
st.write("A written, manager-friendly summary will appear here.")# --- Section 3: Ask Your Question ---
st.header("3. Ask Your Question")
question = st.text_area(
    "Type a business question about your data",
    placeholder="e.g. Which store has the highest average sales?",
)

# --- Section 4: Analysis button ---
if st.button("Analyse", type="primary", use_container_width=True):
    st.warning("The analysis engine isn't built yet — coming in Phase 5.")

# --- Section 5: Results ---
st.header("5. Results")
st.write("Tables and calculation results will appear here.")

# --- Section 6: Charts ---
st.header("6. Charts")
st.write("Charts will appear here.")

# --- Section 7: Business Summary ---
st.header("7. Business Summary")
st.write("A written, manager-friendly summary will appear here.")
