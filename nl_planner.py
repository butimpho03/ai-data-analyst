"""
nl_planner.py — turns a typed English question into a structured plan.

WHY THIS FILE EXISTS, AND WHY IT DOESN'T USE AI YET:
The project brief calls for the app to keep working with basic analysis
even if the AI service is down. This file is that fallback, built first:
a rule-based (keyword and pattern matching) parser that recognises common
question phrasings and turns them into a "plan" — a small dictionary that
says exactly which analysis_engine.py function to call and with what
parameters. In Phase 7, an AI provider will be added as a smarter
alternative for understanding messier phrasings, but this file keeps
working as the reliable fallback either way.

WHAT THIS FILE DOES NOT DO:
It never invents an answer. If it can't confidently match your question to
something the engine can compute, it says so honestly (status
"not_understood") or asks a clarifying question (status "clarify") —
per the project's anti-hallucination rule. It also recognises questions
that are reasonable but not built yet (like "which products are
declining?", which needs a more advanced trend engine we haven't built),
and says so clearly instead of guessing.

THE PLAN FORMAT:
Every successful plan looks like:
    {
        "status": "ok",
        "function": "group_and_aggregate",   # name of an analysis_engine function
        "params": {...},                      # keyword arguments for that function
        "question_text": "...",               # for the Show Your Work display
    }
Other statuses: "clarify" (needs more info), "unsupported" (recognised
but not built yet), "not_understood" (no match found).
"""

import re

# WHY THESE LISTS:
# Centralising the keyword vocabulary here means it's easy to extend later
# — e.g. add "mean" as another way of saying "average" — without touching
# the matching logic itself.
AGG_KEYWORDS = {
    "average": "average", "avg": "average", "mean": "average",
    "total": "sum", "sum": "sum",
    "count": "count", "how many": "count", "number of": "count",
    "minimum": "min", "min": "min", "lowest": "min",
    "maximum": "max", "max": "max", "highest": "max",
}

# Phrases that describe a real, reasonable request our engine doesn't
# support yet. Recognising these lets us give an honest "not built yet"
# answer instead of a wrong guess or a generic "I don't understand".
UNSUPPORTED_PATTERNS = [
    (r"declin|decreas.*over time|trend", "Detecting declining/trending products over time needs a time-series engine, which isn't built yet (planned for a later phase)."),
    (r"\bchart\b|\bgraph\b|\bplot\b|visuali[sz]e", "Charts aren't built yet — that's Phase 8 in the project plan."),
    (r"professional summary|summary for my manager|business summary", "AI-written business summaries aren't built yet — that's a later phase, once the AI provider is connected."),
    (r"\bclean\b.*dataset|clean this data", "Automatic data cleaning isn't built — by design, this app never changes your data automatically. See the Data Quality section instead."),
    (r"unusual value|anomal|find.*outlier", "For unusual values, check the Data Quality section above — it already reports outliers, missing values, and inconsistencies."),
]


def parse_question(question, df):
    """
    Attempt to turn a typed question into an executable analysis plan.

    Returns a dict with a "status" key:
    - "ok": plan is ready — includes "function" and "params" to call the
      matching analysis_engine.py function.
    - "unsupported": a real, reasonable request, but not built yet.
    - "clarify": partially understood, but missing a detail (e.g. which column).
    - "not_understood": no confident match found at all.
    All statuses include a "message" explaining the outcome in plain English.
    """
    if not question or not question.strip():
        return {"status": "not_understood", "message": "Please type a question first."}

    text = question.strip().lower()
    # WHY THIS CLEANUP: trailing punctuation like "region." or "sales?" was
    # breaking pattern matches below, since the matching relied on the
    # phrase ending cleanly at the end of the string. Stripping punctuation
    # (but keeping spaces) makes matching reliable regardless of how the
    # question is punctuated.
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    columns = list(df.columns)
    numeric_columns = list(df.select_dtypes(include="number").columns)

    # STEP 1: check for recognised-but-unsupported requests first, so we
    # give an honest "not built yet" instead of a wrong guess.
    for pattern, explanation in UNSUPPORTED_PATTERNS:
        if re.search(pattern, text):
            return {"status": "unsupported", "message": explanation}

    # STEP 2: "compare X and Y" — needs a column to filter within and a
    # value column, so this often needs a clarifying question.
    compare_match = re.search(r"compare (.+?) (?:and|vs\.?|versus) (.+?)(?:\?|$)", text)
    if compare_match:
        return _plan_compare(compare_match, df, columns, numeric_columns, question)

    # STEP 3: "top N ... by/of <column>" — either grouped top-N or raw top-N rows
    top_n_match = re.search(r"top (\d+)", text)
    if top_n_match:
        return _plan_top_n(text, int(top_n_match.group(1)), df, columns, numeric_columns, question)

    # STEP 4: "<agg> ... by/per <group column>" — e.g. "total sales by region",
    # "which store had the highest average sales"
    group_match = re.search(r"\b(?:by|per)\s+([a-zA-Z0-9_ ]+?)(?:\?|$)", text)
    agg = _find_agg_keyword(text)
    if group_match and agg:
        return _plan_group_aggregate(text, agg, group_match.group(1), df, columns, numeric_columns, question)

    # STEP 5: "which <thing> had the highest/lowest <agg> <value>" without
    # an explicit "by" — e.g. "Which store had the highest average sales?"
    which_match = re.search(r"which ([a-zA-Z_]+)", text)
    if which_match and agg:
        return _plan_group_aggregate(text, agg, which_match.group(1), df, columns, numeric_columns, question)

    # STEP 6: plain aggregate with no grouping — e.g. "total sales", "average price"
    if agg:
        return _plan_plain_aggregate(text, agg, df, columns, numeric_columns, question)

    # STEP 7: descriptive statistics
    if re.search(r"describ|statistic|summary of the data|summary statistics", text):
        return {
            "status": "ok",
            "function": "descriptive_stats",
            "params": {},
            "question_text": question,
        }

    return {
        "status": "not_understood",
        "message": (
            "I cannot determine this from the available columns and question "
            "wording. Try rephrasing (e.g. 'total sales by region', 'top 5 "
            "products by revenue'), or use the manual analysis tool below."
        ),
    }


def _find_agg_keyword(text):
    # Check longer phrases first (e.g. "how many" before "how")
    for phrase in sorted(AGG_KEYWORDS.keys(), key=len, reverse=True):
        if phrase in text:
            return AGG_KEYWORDS[phrase]
    return None


def _find_column(candidate_text, columns):
    """
    Matches a chunk of free text (e.g. "stores" or "average sales") against
    the dataset's real column names. Tries exact-ish matches first, then
    handles simple plurals (e.g. "stores" -> "Store") by stripping a
    trailing 's'.
    """
    candidate_text = candidate_text.strip().lower()
    best_match = None
    for column in columns:
        col_lower = str(column).lower()
        col_singular = col_lower.rstrip("s")
        if col_lower in candidate_text or candidate_text in col_lower:
            if best_match is None or len(col_lower) > len(str(best_match).lower()):
                best_match = column
        elif col_singular and col_singular in candidate_text:
            if best_match is None or len(col_singular) > len(str(best_match).lower()):
                best_match = column
    return best_match


def _find_value_column(text, numeric_columns):
    """
    Finds which numeric column the question is talking about. If exactly
    one numeric column exists, we assume that's the one (common case for
    simple sales-style datasets) — otherwise we require a name match.
    """
    match = _find_column(text, numeric_columns)
    if match:
        return match
    if len(numeric_columns) == 1:
        return numeric_columns[0]
    return None


def _plan_group_aggregate(text, agg, group_phrase, df, columns, numeric_columns, question):
    group_col = _find_column(group_phrase, columns)
    value_col = _find_value_column(text, numeric_columns)

    if not group_col:
        return {
            "status": "clarify",
            "message": f"I couldn't match '{group_phrase.strip()}' to a column in your data. Available columns: {', '.join(str(c) for c in columns)}.",
        }
    if not value_col:
        return {
            "status": "clarify",
            "message": f"Which number column should I calculate? Available options: {', '.join(str(c) for c in numeric_columns)}.",
        }

    # "highest"/"lowest" implies we only want the single winning group
    sort = None
    limit = None
    if "highest" in text or "maximum" in text or "max" in text:
        sort, limit = "desc", 1
    elif "lowest" in text or "minimum" in text or "min" in text:
        sort, limit = "asc", 1

    return {
        "status": "ok",
        "function": "group_and_aggregate",
        "params": {
            "group_column": group_col,
            "value_column": value_col,
            "agg": agg,
            "sort": sort,
            "limit": limit,
        },
        "question_text": question,
    }


def _plan_plain_aggregate(text, agg, df, columns, numeric_columns, question):
    value_col = _find_value_column(text, numeric_columns)
    if not value_col:
        return {
            "status": "clarify",
            "message": f"Which number column should I calculate the {agg} of? Available options: {', '.join(str(c) for c in numeric_columns)}.",
        }
    return {
        "status": "ok",
        "function": "aggregate_column",
        "params": {"value_column": value_col, "agg": agg},
        "question_text": question,
    }


def _plan_top_n(text, n, df, columns, numeric_columns, question):
    # WHY THIS PATTERN FIRST: "top 5 products by sales" means "group by
    # Product, sum Sales, take the top 5 groups" — the word right after
    # "top N" (here "products") is the grouping column, and the word after
    # "by" (here "sales") is the value column. This is different from
    # "top 5 rows by sales" (no real grouping word), which falls through
    # to the simpler raw-row sort below.
    grouped_match = re.search(r"top \d+\s+([a-zA-Z0-9_ ]+?)\s+by\s+([a-zA-Z0-9_ ]+)", text)
    if grouped_match:
        group_phrase = grouped_match.group(1)
        value_phrase = grouped_match.group(2)
        group_col = _find_column(group_phrase, columns)
        value_col = _find_column(value_phrase, numeric_columns)
        if group_col and value_col and group_col != value_col:
            return {
                "status": "ok",
                "function": "group_and_aggregate",
                "params": {
                    "group_column": group_col,
                    "value_column": value_col,
                    "agg": "sum",
                    "sort": "desc",
                    "limit": n,
                },
                "question_text": question,
            }

    # Fallback: no clear grouping word found, so just sort raw rows
    value_col = _find_value_column(text, numeric_columns)
    if not value_col:
        return {
            "status": "clarify",
            "message": f"Top {n} rows sorted by which column? Available options: {', '.join(str(c) for c in columns)}.",
        }

    return {
        "status": "ok",
        "function": "top_n_rows",
        "params": {"sort_column": value_col, "n": n, "ascending": False},
        "question_text": question,
    }


def _plan_compare(compare_match, df, columns, numeric_columns, question):
    value_a_text = compare_match.group(1).strip()
    value_b_text = compare_match.group(2).strip()
    value_col = _find_value_column(question.lower(), numeric_columns)

    if not value_col:
        return {
            "status": "clarify",
            "message": f"Comparing on which number column? Available options: {', '.join(str(c) for c in numeric_columns)}.",
        }

    # Try to find which column actually contains these two values
    text_columns = [c for c in columns if c not in numeric_columns]
    filter_col = None
    for column in text_columns:
        unique_values = set(str(v).strip().lower() for v in df[column].dropna().unique())
        if value_a_text in unique_values and value_b_text in unique_values:
            filter_col = column
            break

    if not filter_col:
        return {
            "status": "clarify",
            "message": (
                f"I couldn't find a column containing both '{value_a_text}' and "
                f"'{value_b_text}' exactly. Please check the spelling matches "
                f"your data, or use the manual analysis tool below."
            ),
        }

    return {
        "status": "ok",
        "function": "compare_two_groups",
        "params": {
            "filter_column": filter_col,
            "group_a_value": value_a_text,
            "group_b_value": value_b_text,
            "value_column": value_col,
            "agg": "sum",
        },
        "question_text": question,
    }
