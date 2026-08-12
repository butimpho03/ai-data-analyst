"""
analysis_engine.py — deterministic calculations using pandas.

WHY THIS FILE EXISTS (the most important file in the whole project):
This is the "do not let the AI calculate" rule made real. Every function
here takes a DataFrame and plain parameters (column names, an operation),
and returns a real, verifiable number or table using pandas — the same
library Excel/SQL-trained eyes can double-check by hand. In later phases,
the AI's only job will be picking WHICH of these functions to call based
on a natural-language question, and explaining the RESULT in words. It
will never invent the number itself.

WHAT EACH FUNCTION RETURNS:
Every function returns a dictionary with a consistent shape, matching the
"Show Your Work" format from the project brief:
    {
        "method": "plain-English description of what was calculated",
        "result_table": a pandas DataFrame (small tables) or None,
        "result_value": a single number, if the answer is one number
        "columns_used": list of column names involved
    }
This makes it easy for app.py to display "Question -> Data Used -> Method
-> Result" consistently, no matter which operation ran.
"""

import pandas as pd

# WHY THIS DICTIONARY:
# Maps a friendly operation name to the actual pandas aggregation function.
# Centralising this means every function below can just say
# AGG_FUNCTIONS["average"] instead of repeating if/elif chains for each
# operation, and it's the one place to look if you want to add a new
# aggregation type later (e.g. "median").
AGG_FUNCTIONS = {
    "sum": "sum",
    "average": "mean",
    "count": "count",
    "min": "min",
    "max": "max",
}


def aggregate_column(df, value_column, agg):
    """
    SUM / AVERAGE / COUNT / MIN / MAX over one column, whole dataset.
    Equivalent to an Excel =SUM(range) or =AVERAGE(range).
    """
    agg_func = AGG_FUNCTIONS[agg]
    series = df[value_column].dropna()
    result = getattr(series, agg_func)()
    return {
        "method": f"Calculated the {agg} of all values in '{value_column}' ({len(series)} non-missing rows used).",
        "result_table": None,
        "result_value": result,
        "columns_used": [value_column],
    }


def group_and_aggregate(df, group_column, value_column, agg, sort=None, limit=None):
    """
    Groups by one column and aggregates another. Equivalent to Excel's
    pivot table "group by X, calculate Y", or SQL's GROUP BY.

    sort: "asc", "desc", or None
    limit: number of groups to keep after sorting (e.g. top 5), or None for all
    """
    agg_func = AGG_FUNCTIONS[agg]
    grouped = df.groupby(group_column)[value_column].agg(agg_func).reset_index()
    grouped.columns = [group_column, f"{agg}_{value_column}"]

    if sort == "desc":
        grouped = grouped.sort_values(by=f"{agg}_{value_column}", ascending=False)
    elif sort == "asc":
        grouped = grouped.sort_values(by=f"{agg}_{value_column}", ascending=True)

    if limit:
        grouped = grouped.head(limit)

    grouped = grouped.reset_index(drop=True)

    method = f"Grouped by '{group_column}' and calculated the {agg} of '{value_column}' for each group."
    if sort:
        method += f" Sorted {'highest to lowest' if sort == 'desc' else 'lowest to highest'}."
    if limit:
        method += f" Limited to the top {limit}."

    return {
        "method": method,
        "result_table": grouped,
        "result_value": None,
        "columns_used": [group_column, value_column],
    }


def filter_aggregate(df, filter_column, filter_value, value_column, agg):
    """
    COUNTIF / SUMIF / AVERAGEIF style: filter rows where filter_column
    matches filter_value, then aggregate value_column over just those rows.
    Matching is case-insensitive and ignores extra spaces, since that's
    how a manager would expect "usa" and "USA" to behave when asking a
    plain-English question (the Data Quality section already warns them
    separately if this inconsistency might affect other results).
    """
    agg_func = AGG_FUNCTIONS[agg]
    normalised_filter_col = df[filter_column].astype(str).str.strip().str.lower()
    normalised_value = str(filter_value).strip().lower()
    matching_rows = df[normalised_filter_col == normalised_value]

    if matching_rows.empty:
        return {
            "method": f"Looked for rows where '{filter_column}' equals '{filter_value}'.",
            "result_table": None,
            "result_value": None,
            "columns_used": [filter_column, value_column],
            "error": f"No rows found where '{filter_column}' equals '{filter_value}'.",
        }

    series = matching_rows[value_column].dropna()
    result = getattr(series, agg_func)()
    return {
        "method": (
            f"Filtered to rows where '{filter_column}' equals '{filter_value}' "
            f"({len(matching_rows)} matching rows), then calculated the {agg} "
            f"of '{value_column}'."
        ),
        "result_table": None,
        "result_value": result,
        "columns_used": [filter_column, value_column],
    }


def top_n_rows(df, sort_column, n=5, ascending=False, display_columns=None):
    """
    Top/bottom N rows by a column. Equivalent to Excel's sort + take top N,
    or SQL's ORDER BY ... LIMIT N.
    """
    sorted_df = df.sort_values(by=sort_column, ascending=ascending)
    if display_columns:
        sorted_df = sorted_df[display_columns]
    result = sorted_df.head(n).reset_index(drop=True)

    direction = "lowest" if ascending else "highest"
    return {
        "method": f"Sorted all rows by '{sort_column}' ({direction} first) and kept the top {n}.",
        "result_table": result,
        "result_value": None,
        "columns_used": [sort_column] + (display_columns or []),
    }


def percent_of_total(df, group_column, value_column):
    """
    Each group's share of the overall total, as a percentage. Equivalent
    to Excel's =value/SUM(range)*100.
    """
    grouped = df.groupby(group_column)[value_column].sum().reset_index()
    total = grouped[value_column].sum()
    grouped["percent_of_total"] = (grouped[value_column] / total * 100).round(1)
    grouped = grouped.sort_values(by="percent_of_total", ascending=False).reset_index(drop=True)

    return {
        "method": f"Calculated each '{group_column}' group's total '{value_column}', then divided by the overall total to get a percentage share.",
        "result_table": grouped,
        "result_value": None,
        "columns_used": [group_column, value_column],
    }


def compare_two_groups(df, filter_column, group_a_value, group_b_value, value_column, agg="sum"):
    """
    Compares an aggregate between two specific values of a column — e.g.
    "compare January and February", or "compare Store A and Store B".
    Returns both totals and the percentage change from A to B.
    """
    agg_func = AGG_FUNCTIONS[agg]
    normalised_col = df[filter_column].astype(str).str.strip().str.lower()

    a_rows = df[normalised_col == str(group_a_value).strip().lower()]
    b_rows = df[normalised_col == str(group_b_value).strip().lower()]

    if a_rows.empty or b_rows.empty:
        missing = group_a_value if a_rows.empty else group_b_value
        return {
            "method": f"Tried to compare '{group_a_value}' and '{group_b_value}' in '{filter_column}'.",
            "result_table": None,
            "result_value": None,
            "columns_used": [filter_column, value_column],
            "error": f"No rows found where '{filter_column}' equals '{missing}'.",
        }

    a_value = getattr(a_rows[value_column].dropna(), agg_func)()
    b_value = getattr(b_rows[value_column].dropna(), agg_func)()
    change = b_value - a_value
    pct_change = (change / a_value * 100) if a_value != 0 else None

    result_table = pd.DataFrame({
        filter_column: [group_a_value, group_b_value],
        f"{agg}_{value_column}": [a_value, b_value],
    })

    method = (
        f"Filtered rows for '{group_a_value}' and '{group_b_value}' separately, "
        f"then calculated the {agg} of '{value_column}' for each."
    )

    return {
        "method": method,
        "result_table": result_table,
        "result_value": None,
        "columns_used": [filter_column, value_column],
        "change": change,
        "pct_change": pct_change,
    }


def descriptive_stats(df):
    """
    Standard descriptive statistics (count, mean, std, min, quartiles, max)
    for every numeric column — equivalent to Excel's Descriptive Statistics
    tool or pandas' well-known .describe().
    """
    numeric_df = df.select_dtypes(include="number")
    if numeric_df.empty:
        return {
            "method": "Looked for numeric columns to summarise.",
            "result_table": None,
            "result_value": None,
            "columns_used": [],
            "error": "No numeric columns found in this dataset.",
        }
    stats = numeric_df.describe().round(2).reset_index()
    stats = stats.rename(columns={"index": "statistic"})
    return {
        "method": "Calculated standard descriptive statistics (count, mean, std deviation, min, quartiles, max) for each numeric column.",
        "result_table": stats,
        "result_value": None,
        "columns_used": list(numeric_df.columns),
    }
