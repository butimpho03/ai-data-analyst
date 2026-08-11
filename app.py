"""
AI Data Analyst Assistant — Phase 0 skeleton.

WHAT THIS FILE IS:
This is the single entry point Streamlit runs. Right now it doesn't analyse
anything — it just proves the whole pipeline (your phone -> GitHub ->
Streamlit Cloud) actually works, with the section layout already in place.
We'll fill each section with real logic in later phases.
"""

import streamlit as st

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
st.info("File reading isn't wired up yet — that's Phase 2.")

# --- Section 2: Dataset Preview ---
st.header("2. Dataset Preview")
st.write("Once a file is uploaded, a preview table will appear here.")

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
st.write("A written, manager-friendly summary will appear here.")
