"""
AI Data Analyst Assistant — Phase 10: testing, security & polish.

WHAT THIS FILE IS:
The single entry point Streamlit runs. Phase 10 didn't add new analysis
features — it hardened what already existed: fixed two real parsing bugs
found via stress-testing (unicode/decorated column names), stopped raw
internal error messages from being shown in this public deployment, and
added a "Start Over" reset plus a short privacy note, since this app
handles other people's uploaded business data.
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
from ai_provider import get_ai_provider, build_explanation_prompt
import chart_builder
from business_summary import record_result, build_summary_prompt
import ai_planner

# st.set_page_config MUST be the first Streamlit command in the file.
st.set_page_config(
    page_title="AI Data Analyst",
    page_icon="📊",
    layout="centered",
)

st.title("📊 AI Data Analyst")
st.caption("Upload a dataset, ask a question, get a professional analysis.")

with st.expander("🔒 Privacy & how this app handles your data"):
    st.write(
        "- Your uploaded file is only kept in memory for this browser "
        "session — it isn't saved to a database or written to disk.\n"
        "- If AI features are used, only a small summary of a result "
        "(numbers and column names already shown in the app) is sent to "
        "the AI provider — never your full raw dataset.\n"
        "- Closing this tab or rebooting the app clears everything. Use "
        "**Start Over** below any time to clear it yourself."
    )

# WHY WE BUILD THE PROVIDER ONCE, HERE:
# get_ai_provider() checks for a configured API key and returns None if
# there isn't one. Building it once at the top means every section below
# can check "if ai_provider:" without repeating the lookup logic.
ai_provider = get_ai_provider()

if st.session_state.get("df") is not None:
    if st.button("🔄 Start Over (clear uploaded data and results)"):
        # WHY WE LIST KEYS EXPLICITLY INSTEAD OF st.session_state.clear():
        # Streamlit ties some internal widget state to session_state too;
        # clearing only the keys THIS app created is safer and avoids
        # accidentally breaking widgets that haven't re-rendered yet.
        for key in [
            "df", "nl_plan", "nl_result", "nl_question_text", "nl_multi_steps",
            "manual_result", "manual_question_text",
            "chart_table", "chart_suggestion", "chart_question",
            "results_history", "business_summary_text",
        ]:
            st.session_state.pop(key, None)
        st.rerun()


def render_result(result, question_text, key_suffix=""):
    """
    Displays a result dictionary from analysis_engine.py in the "Show Your
    Work" format from the project brief: Question -> Data Used -> Method
    -> Result -> Interpretation, plus an optional AI explanation button.

    WHY THIS IS A SHARED FUNCTION:
    Both the natural-language question flow (Section 4) and the manual
    analysis tool (Section 5) produce the exact same kind of result
    dictionary, so they can share this one display function.

    WHY key_suffix:
    Streamlit needs every button to have a unique key. Since this function
    is called from two different sections, key_suffix (e.g. "nl" or
    "manual") keeps their buttons from colliding.
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

    # WHY WE UPDATE THE CHART STATE HERE:
    # This keeps Section 7 (Charts) always showing a chart for the most
    # recently computed table-shaped result, no matter whether it came
    # from Section 4 (a typed question) or Section 5 (the manual tool) —
    # both call this same function. If the new result isn't chartable
    # (e.g. a single number, or descriptive stats with no clean category),
    # we clear the old chart rather than leaving a stale, unrelated one on
    # screen — the project brief specifically says not to show a chart
    # when it wouldn't improve understanding.
    if result["result_table"] is not None and chart_builder.suggest_chart_type(result["result_table"]) is not None:
        st.session_state["chart_table"] = result["result_table"]
        st.session_state["chart_suggestion"] = chart_builder.suggest_chart_type(result["result_table"])
        st.session_state["chart_question"] = question_text
    else:
        st.session_state["chart_table"] = None

    if result.get("change") is not None:
        direction = "increased" if result["change"] > 0 else "decreased"
        pct = f" ({result['pct_change']:.1f}%)" if result.get("pct_change") is not None else ""
        st.markdown("##### Interpretation")
        st.write(f"The value {direction} by {abs(result['change']):.2f}{pct} between the two groups.")

    # WHY THIS IS A BUTTON, NOT AUTOMATIC:
    # Calling the AI on every single result would use up the free rate
    # limit quickly and cost time waiting on every click. Making it opt-in
    # keeps you in control of when it's used.
    if ai_provider and not result.get("error"):
        if st.button("✨ Explain this with AI", key=f"explain_{key_suffix}"):
            with st.spinner("Asking AI to explain this result..."):
                try:
                    prompt = build_explanation_prompt(question_text, result["method"], result)
                    explanation = ai_provider.generate_text(prompt)
                    st.markdown("##### AI Explanation")
                    st.write(explanation)
                except Exception:
                    # WHY WE DON'T SHOW THE RAW EXCEPTION (str(e)) HERE:
                    # This app is deployed publicly. Displaying the exact
                    # internal error text to any visitor is unnecessary and
                    # is a small but real security/privacy habit worth
                    # having — error details could occasionally include
                    # more about the request than a visitor needs to see.
                    # A short, generic message is enough for the user to
                    # know what to do next.
                    st.warning(
                        "AI explanation isn't available right now. The "
                        "calculated result above is still accurate — it "
                        "doesn't depend on the AI. Please try again in a "
                        "moment."
                    )


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

    # WHY A CONTROL INSTEAD OF ALWAYS SHOWING 10:
    # A fixed 10-row preview was too limiting for someone actually
    # checking their data before analysing it. Every other section
    # (analysis, charts, summary) has always used the FULL dataset
    # regardless of this preview size — this only changes how much you
    # can browse here.
    max_preview = min(len(df), 2000)  # capped to keep the phone browser responsive
    default_preview = min(10, max_preview)
    preview_rows = st.slider(
        "Rows to preview",
        min_value=min(5, max_preview),
        max_value=max_preview,
        value=default_preview,
        step=5,
    )
    st.dataframe(df.head(preview_rows), use_container_width=True)
    st.caption(
        f"Showing {min(preview_rows, len(df))} of {df.shape[0]} rows. "
        f"(All {df.shape[0]} rows are always used for analysis, charts, "
        f"and the summary below — this slider only changes what you can "
        f"browse here.)"
    )

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
    if ai_provider:
        st.caption("🟢 AI connected — an 'Explain with AI' button will appear after each result.")
    else:
        st.caption(
            "⚪ AI not connected (no GROQ_API_KEY found). The app still "
            "calculates real results below — you just won't get an "
            "AI-written explanation. Question understanding uses "
            "rule-based keyword matching either way, not AI."
        )

    if st.button("Analyse", type="primary", use_container_width=True):
        if not question.strip():
            st.warning("Please type a question first.")
            st.session_state["nl_plan"] = None
            st.session_state["nl_multi_steps"] = None
        else:
            # WHY WE TRY THE AI PLANNER FIRST, THEN FALL BACK:
            # The rule-based planner (nl_planner.py) only ever extracts ONE
            # operation per question — a real limitation found by testing
            # with a compound question ("total sales AND sales by division
            # AND top 10 AND bottom 10", all at once). The AI planner can
            # break a question like that into several steps. If AI isn't
            # connected, or its proposed plan fails validation entirely,
            # this safely falls back to the same single-step rule-based
            # planner that's been tested since Phase 6 — the app never
            # depends on the AI planner working.
            multi_steps = ai_planner.plan_multi_step(question, df, ai_provider) if ai_provider else None

            if multi_steps:
                st.session_state["nl_plan"] = None
                computed_steps = []
                for step in multi_steps:
                    engine_function = getattr(analysis_engine, step["function"])
                    result = engine_function(df, **step["params"])
                    computed_steps.append({"question_text": step["question_text"], "result": result})
                    entry = record_result(step["question_text"], result)
                    if entry:
                        st.session_state.setdefault("results_history", [])
                        st.session_state["results_history"].append(entry)
                st.session_state["results_history"] = st.session_state.get("results_history", [])[-8:]
                st.session_state["nl_multi_steps"] = computed_steps
            else:
                st.session_state["nl_multi_steps"] = None
                plan = parse_question(question, df)
                # WHY WE STORE THE PLAN AND RESULT IN session_state HERE,
                # INSTEAD OF JUST DISPLAYING THEM DIRECTLY:
                # This fixed a real bug — the "Explain with AI" button used to
                # live inside this "if st.button(Analyse)" block. Streamlit
                # reruns the whole script on every click, including a click on
                # that inner AI button. On that rerun, "Analyse" itself hadn't
                # been clicked, so this whole block was skipped — making the
                # result (and the very button just clicked) disappear. Storing
                # the plan/result in session_state and rendering it OUTSIDE
                # this button block (below) means it survives every future
                # rerun until you run a new analysis.
                st.session_state["nl_plan"] = plan
                if plan["status"] == "ok":
                    engine_function = getattr(analysis_engine, plan["function"])
                    st.session_state["nl_result"] = engine_function(df, **plan["params"])
                    st.session_state["nl_question_text"] = plan["question_text"]
                    entry = record_result(plan["question_text"], st.session_state["nl_result"])
                    if entry:
                        st.session_state.setdefault("results_history", [])
                        st.session_state["results_history"].append(entry)
                        st.session_state["results_history"] = st.session_state["results_history"][-8:]
                else:
                    st.session_state["nl_result"] = None

    # WHY THIS IS OUTSIDE THE BUTTON'S if BLOCK:
    # See the comment above — this needs to run on every rerun, not just
    # the one where "Analyse" was clicked, so it stays visible.
    multi_steps = st.session_state.get("nl_multi_steps")
    if multi_steps:
        st.caption(f"🤖 AI broke this question into {len(multi_steps)} step(s):")
        for i, step in enumerate(multi_steps, start=1):
            render_result(step["result"], f"{i}. {step['question_text']}", key_suffix=f"nl{i}")
    else:
        plan = st.session_state.get("nl_plan")
        if plan:
            if plan["status"] == "ok" and st.session_state.get("nl_result") is not None:
                render_result(st.session_state["nl_result"], st.session_state["nl_question_text"], key_suffix="nl")
            elif plan["status"] == "clarify":
                st.info(f"I need a bit more detail: {plan['message']}")
            elif plan["status"] == "unsupported":
                st.warning(plan["message"])
            elif plan["status"] == "not_understood":
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

            # WHY WE SAVE TO session_state HERE:
            # Same reason as Section 4 — the "Explain with AI" button inside
            # render_result() needs this result to survive future reruns
            # (like the AI button's own click), not just the one rerun
            # where "Run" was pressed.
            if result is not None:
                st.session_state["manual_result"] = result
                st.session_state["manual_question_text"] = question_text
                # Same reasoning as Section 4 -- record history only at the
                # moment of a fresh computation, not on every redisplay.
                entry = record_result(question_text, result)
                if entry:
                    st.session_state.setdefault("results_history", [])
                    st.session_state["results_history"].append(entry)
                    st.session_state["results_history"] = st.session_state["results_history"][-8:]

            if st.session_state.get("manual_result") is not None:
                render_result(st.session_state["manual_result"], st.session_state["manual_question_text"], key_suffix="manual")
else:
    st.write("Upload a file above to run an analysis.")

# --- Section 6: Results ---
st.header("6. Results")
st.write("Results appear directly inside Sections 4 and 5 above, next to the question or analysis you run.")

# --- Section 7: Charts ---
st.header("7. Charts")
chart_table = st.session_state.get("chart_table")
if chart_table is not None:
    feasible_types = chart_builder.feasible_chart_types(chart_table)
    suggested = st.session_state.get("chart_suggestion")

    st.caption(f"Chart for: {st.session_state.get('chart_question', '')}")

    # WHY A SELECTBOX INSTEAD OF JUST SHOWING THE SUGGESTED CHART:
    # The suggestion is a sensible default, not the only valid choice —
    # e.g. a table might work as either a bar or a pie chart. Letting you
    # pick keeps you in control instead of the app deciding silently.
    default_index = feasible_types.index(suggested) if suggested in feasible_types else 0
    chart_type = st.selectbox(
        "Chart type",
        feasible_types,
        index=default_index,
        format_func=lambda t: {"bar": "Bar chart", "line": "Line chart", "pie": "Pie chart", "scatter": "Scatter plot"}.get(t, t),
    )
    try:
        fig = chart_builder.build_chart(chart_table, chart_type)
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"Couldn't build this chart: {e}")
else:
    st.write(
        "Run an analysis above that produces a table with a category and "
        "a number (like grouping, top N, or comparing values) to see a "
        "chart here. A single number or a statistics table won't show a "
        "chart, since a chart wouldn't add anything useful there."
    )

# --- Section 8: Business Summary ---
st.header("8. Business Summary")
if st.session_state.get("df") is None:
    st.write("Upload a file above to generate a business summary.")
elif not st.session_state.get("results_history"):
    st.info(
        "No analyses have been run yet. Ask a question in Section 4 or "
        "run an analysis in Section 5 first — the summary is built only "
        "from real results already calculated above, never invented."
    )
elif not ai_provider:
    st.warning(
        "AI isn't connected (no GROQ_API_KEY configured), so a written "
        "summary can't be generated — this is the one feature that "
        "genuinely needs AI, since there's no deterministic way to write "
        "prose. Your calculated results, charts, and data-quality "
        "findings above are all still fully usable without it."
    )
else:
    df = st.session_state["df"]
    history = st.session_state["results_history"]
    st.caption(f"Will summarize {len(history)} analysis result(s) run so far in this session.")

    if st.button("📝 Generate Business Summary", type="primary", use_container_width=True):
        with st.spinner("Writing summary..."):
            try:
                quality_findings = inspect_dataset(df)
                prompt = build_summary_prompt(df.shape, quality_findings, history)
                summary_text = ai_provider.generate_text(prompt)
                st.session_state["business_summary_text"] = summary_text
            except Exception:
                # Same reasoning as the AI explanation button above — don't
                # surface raw exception details from a public deployment.
                st.session_state["business_summary_text"] = None
                st.warning("Couldn't generate the summary right now. Please try again in a moment.")

    # WHY THIS IS OUTSIDE THE BUTTON'S if BLOCK:
    # Same nested-button lesson from Phase 7 — this needs to stay visible
    # across future reruns, not just the one where the button was clicked.
    if st.session_state.get("business_summary_text"):
        st.divider()
        st.markdown(st.session_state["business_summary_text"])
        st.caption(
            "This summary was written by AI based only on the real "
            "results and data-quality findings shown above in this app — "
            "it did not calculate anything new itself."
        )
