"""
AI Data Analyst Assistant — Phase 6: natural-language question -> plan.

WHAT THIS FILE IS:
The single entry point Streamlit runs. As of Phase 6, typing a question in
plain English and pressing "Analyse" works: nl_planner.py interprets the
question using rules and keywords (no AI yet — that's Phase 7) and turns
it into a plan, which analysis_engine.py then executes with real pandas
calculations. The manual analysis tool from Phase 5 is kept below as a
fallback/testing tool, since it uses the exact same engine.
"""

import streamlit as st

from data_loader import load_dataset
from data_quality import inspect_dataset
import analysis_engine
from analysis_engine import (
    aggregate_column,
    group_and_aggregate,
    filter_aggregate,
    top_n_rows,
    percent_of_total,
    compare_two_groups,
    descriptive_stats,
)
from nl_planner import parse_question

# st.set_page_config MUST be the first Streamlit command in the file.
st.set_page_config(
    page_title="AI Data Analyst",
    page_icon="📊",
    layout="centered",
)

st.title("📊 AI Data Analyst")
st.caption("Upload a dataset, ask a question, get a professional analysis.")


def render_result(result, question_text):
    """
    Displays a result dictionary from analysis_engine.py in the "Show Your
    Work" format from the project brief: Question -> Data Used -> Method
    -> Result -> Interpretation.

    WHY THIS IS A SHARED FUNCTION:
    Both the natural-language question flow (Section 4) and the manual
    analysis tool (Section 5) produce the exact same kind of result
    dictionary, so they can share this one display function instead of
    duplicating the same rendering code twice.
    """
    st.divider()
    st.markdown("##### Question")
    st.write(question_text)

    st.markdown("##### Data Used")
    st.write(", ".join(f"`{c}`" for c in result["columns_used"]))

    st.markdown("##### Method")
    st.write(result["method"])

    st.markdown("##### Result")
    if result.get("error"):
        st.error(result["error"])
    elif result["result_value"] is not None:
        value = result["result_value"]
        display_value = round(float(value), 2) if isinstance(value, float) else value
        st.metric(label="Result", value=display_value)
    elif result["result_table"] is not None:
        st.dataframe(result["result_table"], use_container_width=True, hide_index=True)

    if result.get("change") is not None:
        direction = "increased" if result["change"] > 0 else "decreased"
        pct = f" ({result['pct_change']:.1f}%)" if result.get("pct_change") is not None else ""
        st.markdown("##### Interpretation")
        st.write(f"The value {direction} by {abs(result['change']):.2f}{pct} between the two groups.")


# --- Section 1: Upload Dataset ---
st.header("1. Upload Dataset")
uploaded_file = st.file_uploader(
    "Upload an Excel (.xlsx) or CSV file",
    type=["xlsx", "csv"],
)

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
if st.session_state.get("df") is not None:
    df = st.session_state["df"]
    question = st.text_area(
        "Type a business question about your data",
        placeholder="e.g. Which store has the highest average sales?",
    )
    st.caption(
        "This uses rule-based matching (keywords like 'total', 'average', "
        "'by', 'top N', 'compare') — not AI yet. AI-powered understanding "
        "of messier phrasing comes in Phase 7."
    )

    if st.button("Analyse", type="primary", use_container_width=True):
        if not question.strip():
            st.warning("Please type a question first.")
        else:
            plan = parse_question(question, df)

            if plan["status"] == "ok":
                # WHY getattr:
                # The plan tells us the function's NAME as text (e.g.
                # "group_and_aggregate"). getattr looks up the actual
                # function with that name inside the analysis_engine
                # module, so we can call whichever one the plan chose
                # without writing a big if/elif for every possibility.
                engine_function = getattr(analysis_engine, plan["function"])
                result = engine_function(df, **plan["params"])
                render_result(result, plan["question_text"])
            elif plan["status"] == "clarify":
                st.info(f"I need a bit more detail: {plan['message']}")
            elif plan["status"] == "unsupported":
                st.warning(plan["message"])
            else:
                st.error(plan["message"])
else:
    st.write("Upload a file above to ask a question.")

# --- Section 5: Run an Analysis (manual engine test / fallback tool) ---
st.header("5. Run an Analysis (manual tool)")
if st.session_state.get("df") is not None:
    df = st.session_state["df"]
    all_columns = list(df.columns)
    numeric_columns = list(df.select_dtypes(include="number").columns)

    with st.expander("Prefer to build the analysis manually instead of typing a question?"):
        if not numeric_columns:
            st.info(
                "This dataset has no numeric columns, so calculations like "
                "SUM or AVERAGE aren't available."
            )
        else:
            analysis_type = st.selectbox(
                "Choose an analysis type",
                [
                    "Overall total/average/count of a column",
                    "Group by a column and aggregate another (e.g. average sales per store)",
                    "Filter by a value and aggregate (e.g. total sales where Store = Store A)",
                    "Top N rows by a column",
                    "Percentage of total by group",
                    "Compare two specific values (e.g. compare Jan vs Feb)",
                    "Descriptive statistics (all numeric columns)",
                ],
            )

            result = None
            question_text = ""

            if analysis_type == "Overall total/average/count of a column":
                value_col = st.selectbox("Column to calculate", numeric_columns, key="a1_col")
                agg = st.selectbox("Calculation", ["sum", "average", "count", "min", "max"], key="a1_agg")
                question_text = f"What is the {agg} of '{value_col}'?"
                if st.button("Run", key="run1"):
                    result = aggregate_column(df, value_col, agg)

            elif analysis_type == "Group by a column and aggregate another (e.g. average sales per store)":
                group_col = st.selectbox("Group by", all_columns, key="a2_group")
                value_col = st.selectbox("Column to calculate", numeric_columns, key="a2_value")
                agg = st.selectbox("Calculation", ["sum", "average", "count", "min", "max"], key="a2_agg")
                sort = st.selectbox("Sort", ["desc (highest first)", "asc (lowest first)", "no sort"], key="a2_sort")
                limit = st.number_input("Limit to top N groups (0 = show all)", min_value=0, value=0, key="a2_limit")
                sort_arg = "desc" if sort.startswith("desc") else ("asc" if sort.startswith("asc") else None)
                question_text = f"What is the {agg} of '{value_col}' for each '{group_col}'?"
                if st.button("Run", key="run2"):
                    result = group_and_aggregate(df, group_col, value_col, agg, sort=sort_arg, limit=limit or None)

            elif analysis_type == "Filter by a value and aggregate (e.g. total sales where Store = Store A)":
                filter_col = st.selectbox("Filter column", all_columns, key="a3_filtercol")
                filter_val = st.text_input("Filter value (must match exactly, e.g. 'Store A')", key="a3_filterval")
                value_col = st.selectbox("Column to calculate", numeric_columns, key="a3_value")
                agg = st.selectbox("Calculation", ["sum", "average", "count", "min", "max"], key="a3_agg")
                question_text = f"What is the {agg} of '{value_col}' where '{filter_col}' equals '{filter_val}'?"
                if st.button("Run", key="run3") and filter_val:
                    result = filter_aggregate(df, filter_col, filter_val, value_col, agg)

            elif analysis_type == "Top N rows by a column":
                sort_col = st.selectbox("Sort by", all_columns, key="a4_sortcol")
                n = st.number_input("How many rows", min_value=1, value=5, key="a4_n")
                direction = st.selectbox("Direction", ["highest first", "lowest first"], key="a4_dir")
                question_text = f"What are the top {n} rows by '{sort_col}' ({direction})?"
                if st.button("Run", key="run4"):
                    result = top_n_rows(df, sort_col, n=n, ascending=(direction == "lowest first"))

            elif analysis_type == "Percentage of total by group":
                group_col = st.selectbox("Group by", all_columns, key="a5_group")
                value_col = st.selectbox("Column to calculate", numeric_columns, key="a5_value")
                question_text = f"What percentage of total '{value_col}' does each '{group_col}' represent?"
                if st.button("Run", key="run5"):
                    result = percent_of_total(df, group_col, value_col)

            elif analysis_type == "Compare two specific values (e.g. compare Jan vs Feb)":
                filter_col = st.selectbox("Column to compare within", all_columns, key="a6_filtercol")
                val_a = st.text_input("First value (e.g. Jan)", key="a6_vala")
                val_b = st.text_input("Second value (e.g. Feb)", key="a6_valb")
                value_col = st.selectbox("Column to calculate", numeric_columns, key="a6_value")
                agg = st.selectbox("Calculation", ["sum", "average", "count", "min", "max"], key="a6_agg")
                question_text = f"How does {agg} of '{value_col}' compare between '{val_a}' and '{val_b}' in '{filter_col}'?"
                if st.button("Run", key="run6") and val_a and val_b:
                    result = compare_two_groups(df, filter_col, val_a, val_b, value_col, agg=agg)

            elif analysis_type == "Descriptive statistics (all numeric columns)":
                question_text = "What are the descriptive statistics for the numeric columns?"
                if st.button("Run", key="run7"):
                    result = descriptive_stats(df)

            if result is not None:
                render_result(result, question_text)
else:
    st.write("Upload a file above to run an analysis.")

# --- Section 6: Results ---
st.header("6. Results")
st.write("Results appear directly inside Sections 4 and 5 above, next to the question or analysis you run.")

# --- Section 7: Charts ---
st.header("7. Charts")
st.write("Charts will appear here.")

# --- Section 8: Business Summary ---
st.header("8. Business Summary")
st.write("A written, manager-friendly summary will appear here.")
