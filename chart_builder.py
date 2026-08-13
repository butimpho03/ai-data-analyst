"""
chart_builder.py — decides whether a result can be usefully charted, and
builds the right chart type if so.

WHY THIS IS A SEPARATE FILE:
Same reasoning as the other engine files — keeps chart logic testable on
its own and out of app.py's layout code.

WHY WE DON'T ALWAYS SHOW A CHART:
Per the project brief: "Do not automatically generate a chart when it
doesn't improve understanding." A single number, or a statistics table,
doesn't become clearer as a chart. This file only suggests a chart when
the result is genuinely chart-shaped (a category/label column paired with
a number column).
"""

import pandas as pd
import warnings


def feasible_chart_types(table):
    """
    Looks at a result table's shape and returns a list of chart types that
    would make sense for it — could be an empty list if no chart type fits.

    THE RULES (deliberately simple and explainable):
    - Needs at least one text/category column and one numeric column.
    - Bar chart: always offered when that basic shape is present — it's
      the safest, most readable default for categories vs numbers.
    - Pie chart: only offered when there are 8 or fewer categories, since
      pie charts become unreadable with many slices.
    - Line chart: only offered when the category column's values actually
      parse as real dates, since a line chart implies a trend over time.
    - Scatter chart: only offered when there are two or more numeric
      columns and no text column, comparing two numeric measures directly.
    """
    if table is None or table.empty or table.shape[1] < 2:
        return []

    numeric_columns = list(table.select_dtypes(include="number").columns)
    text_columns = [c for c in table.columns if c not in numeric_columns]

    types = []

    if numeric_columns and text_columns:
        types.append("bar")

        if len(table) <= 8:
            types.append("pie")

        # Check whether the category column looks like real dates
        category_column = text_columns[0]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            parsed_dates = pd.to_datetime(table[category_column], errors="coerce")
        if parsed_dates.notna().mean() > 0.8:  # over 80% parsed as valid dates
            types.append("line")

    if len(numeric_columns) >= 2 and not text_columns:
        types.append("scatter")

    return types


def suggest_chart_type(table):
    """
    Picks the single best default chart type from feasible_chart_types(),
    preferring line (if it's genuinely a time trend) over pie over bar,
    since a time-based view is usually the most informative when it
    applies. Returns None if nothing is chartable.
    """
    feasible = feasible_chart_types(table)
    if not feasible:
        return None
    for preferred in ["line", "pie", "bar", "scatter"]:
        if preferred in feasible:
            return preferred
    return feasible[0]


def build_chart(table, chart_type):
    """
    Builds and returns a Plotly Figure for the given table and chart type.
    Raises ValueError for a chart type that doesn't fit the table's shape
    (the caller should only pass types returned by feasible_chart_types()).
    """
    import plotly.express as px

    numeric_columns = list(table.select_dtypes(include="number").columns)
    text_columns = [c for c in table.columns if c not in numeric_columns]

    if chart_type in ("bar", "line", "pie"):
        if not numeric_columns or not text_columns:
            raise ValueError("This table doesn't have both a category and a number column.")
        category_column = text_columns[0]
        value_column = numeric_columns[0]

        if chart_type == "bar":
            fig = px.bar(table, x=category_column, y=value_column)
        elif chart_type == "line":
            # Sort by the (parsed) date so the line reads left-to-right in
            # chronological order rather than in whatever order the table
            # happened to be in.
            sorted_table = table.copy()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                sorted_table["_parsed_date"] = pd.to_datetime(sorted_table[category_column], errors="coerce")
            sorted_table = sorted_table.sort_values("_parsed_date")
            fig = px.line(sorted_table, x=category_column, y=value_column, markers=True)
        else:  # pie
            fig = px.pie(table, names=category_column, values=value_column)

    elif chart_type == "scatter":
        if len(numeric_columns) < 2:
            raise ValueError("Scatter charts need at least two numeric columns.")
        fig = px.scatter(table, x=numeric_columns[0], y=numeric_columns[1])

    else:
        raise ValueError(f"Unknown chart type: {chart_type}")

    fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
    return fig
