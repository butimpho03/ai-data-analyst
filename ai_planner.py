"""
ai_planner.py — uses the AI to break a compound question into multiple
analysis_engine.py steps, with strict validation before any step runs.

WHY THIS FILE EXISTS:
nl_planner.py (the rule-based planner) only ever extracts ONE operation
per question — a real, known limitation surfaced by testing on a real
retail dataset with a compound question ("total sales AND sales by
division AND top 10 products AND ..." all at once). This file lets the
AI propose a multi-step plan for exactly that kind of question.

THE SECURITY RULE THIS FILE FOLLOWS:
The AI's output is NEVER trusted or executed directly. It's treated as an
untrusted suggestion: every proposed step is checked against a fixed
whitelist of real analysis_engine.py functions, every column name is
checked against the dataset's REAL columns, and every parameter is
type-checked and cleaned before analysis_engine ever sees it. If the AI
suggests a function that doesn't exist, a column that isn't real, or
returns malformed output, that step (or the whole plan) is safely
rejected rather than crashing or running something unintended.

WHAT HAPPENS IF THIS FAILS OR AI IS UNAVAILABLE:
plan_multi_step() returns None, and app.py falls back to the existing
rule-based nl_planner.py — the app never depends on this working.
"""

import json
import re

# WHY THIS WHITELIST EXISTS:
# Maps each real analysis_engine.py function name to the ONLY parameter
# names it's allowed to receive. Any parameter the AI suggests outside
# this list is silently dropped rather than passed through — this is what
# stops a hallucinated or malformed AI response from ever reaching pandas
# with unexpected arguments.
ALLOWED_FUNCTIONS = {
    "aggregate_column": {"value_column", "agg"},
    "group_and_aggregate": {"group_column", "value_column", "agg", "sort", "limit"},
    "filter_aggregate": {"filter_column", "filter_value", "value_column", "agg"},
    "top_n_rows": {"sort_column", "n", "ascending", "display_columns"},
    "percent_of_total": {"group_column", "value_column"},
    "compare_two_groups": {"filter_column", "group_a_value", "group_b_value", "value_column", "agg"},
    "descriptive_stats": set(),
}
ALLOWED_AGGS = {"sum", "average", "count", "min", "max"}
COLUMN_PARAM_NAMES = {"value_column", "group_column", "filter_column", "sort_column"}
MAX_STEPS = 8


def _build_planning_prompt(question, df):
    """
    Builds the prompt asking the AI to propose a plan. Sends only column
    names and types — never the actual data rows.
    """
    columns_description = []
    for col in df.columns:
        kind = "number" if col in df.select_dtypes(include="number").columns else "text"
        columns_description.append(f"- {col} ({kind})")

    function_docs = (
        "aggregate_column(value_column, agg) — overall SUM/AVERAGE/COUNT/MIN/MAX of one column\n"
        "group_and_aggregate(group_column, value_column, agg, sort, limit) — group by a column, "
        "aggregate another; sort is 'asc', 'desc', or null; limit is a number or null\n"
        "filter_aggregate(filter_column, filter_value, value_column, agg) — filter to rows where "
        "filter_column equals filter_value, then aggregate value_column\n"
        "top_n_rows(sort_column, n, ascending, display_columns) — top/bottom N raw rows by a "
        "column; display_columns is an array of 2-5 column names to show (pick relevant "
        "identifying columns plus sort_column — never omit display_columns, since showing every "
        "column is unreadable)\n"
        "percent_of_total(group_column, value_column) — each group's % share of the total\n"
        "compare_two_groups(filter_column, group_a_value, group_b_value, value_column, agg) — "
        "compare an aggregate between two specific values\n"
        "descriptive_stats() — standard statistics for all numeric columns, no parameters\n"
    )

    return (
        f"Dataset columns:\n" + "\n".join(columns_description) + "\n\n"
        f"Available functions (use ONLY these names and parameter names exactly):\n{function_docs}\n"
        f'agg must be one of: "sum", "average", "count", "min", "max"\n\n'
        f'User question: "{question}"\n\n'
        "Break this question into the minimum number of separate steps needed to fully answer "
        "it, using ONLY the functions and columns listed above. Respond with ONLY a JSON array, "
        "no other text, no markdown code fences. Each item must have exactly these keys: "
        '"function", "params", "question_text" (a short label for this step). '
        "If a requested part of the question can't be answered with the available functions and "
        "columns, skip that part rather than guessing. Example format:\n"
        '[{"function": "aggregate_column", "params": {"value_column": "Sales", "agg": "sum"}, '
        '"question_text": "Total Sales"}]'
    )


def _validate_step(step, df):
    """
    Checks a single AI-proposed step against real functions, real columns,
    and real parameter types. Returns a cleaned, safe step dict, or None
    if the step can't be trusted (wrong function, missing column, etc.).
    """
    if not isinstance(step, dict):
        return None

    function_name = step.get("function")
    if function_name not in ALLOWED_FUNCTIONS:
        return None

    raw_params = step.get("params", {})
    if not isinstance(raw_params, dict):
        raw_params = {}

    allowed_keys = ALLOWED_FUNCTIONS[function_name]
    clean_params = {k: v for k, v in raw_params.items() if k in allowed_keys}

    # Every column-shaped parameter must be a column that actually exists
    for key in COLUMN_PARAM_NAMES:
        if key in clean_params and clean_params[key] not in df.columns:
            return None

    if "agg" in clean_params and clean_params["agg"] not in ALLOWED_AGGS:
        return None

    if "sort" in clean_params and clean_params["sort"] not in (None, "asc", "desc"):
        clean_params["sort"] = None

    if "limit" in clean_params:
        try:
            clean_params["limit"] = int(clean_params["limit"]) if clean_params["limit"] is not None else None
        except (TypeError, ValueError):
            clean_params["limit"] = None

    if "n" in clean_params:
        try:
            clean_params["n"] = int(clean_params["n"])
        except (TypeError, ValueError):
            clean_params["n"] = 5

    if "ascending" in clean_params and not isinstance(clean_params["ascending"], bool):
        clean_params["ascending"] = False

    if "display_columns" in clean_params:
        raw_list = clean_params["display_columns"]
        if isinstance(raw_list, list):
            # Keep only real columns, in the order given, dropping anything hallucinated
            valid_columns = [c for c in raw_list if c in df.columns]
            if valid_columns:
                clean_params["display_columns"] = valid_columns
            else:
                del clean_params["display_columns"]
        else:
            del clean_params["display_columns"]

    question_text = step.get("question_text")
    if not isinstance(question_text, str) or not question_text.strip():
        question_text = function_name.replace("_", " ").title()

    return {"function": function_name, "params": clean_params, "question_text": question_text}


def plan_multi_step(question, df, ai_provider):
    """
    Asks the AI to break the question into steps, validates every step,
    and returns a list of safe, ready-to-execute plan dicts (same shape
    as nl_planner.py's single-step plans). Returns None if the AI is
    unavailable, the response can't be parsed, or no valid steps survive
    validation — the caller should fall back to nl_planner.py in that case.
    """
    if ai_provider is None:
        return None

    try:
        prompt = _build_planning_prompt(question, df)
        raw_response = ai_provider.generate_text(prompt)
    except Exception:
        return None

    # WHY WE STRIP CODE FENCES:
    # AI models sometimes wrap JSON in ```json ... ``` even when told not
    # to. Stripping this defensively is safer than trusting instructions
    # alone.
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw_response.strip(), flags=re.MULTILINE).strip()

    try:
        proposed_steps = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(proposed_steps, list):
        return None

    valid_steps = []
    for step in proposed_steps[:MAX_STEPS]:
        validated = _validate_step(step, df)
        if validated:
            valid_steps.append(validated)

    return valid_steps if valid_steps else None
