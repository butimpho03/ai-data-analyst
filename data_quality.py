"""
data_quality.py — inspects a DataFrame and reports problems, without ever
changing the data.

WHY THIS IS A SEPARATE FILE:
Same reasoning as data_loader.py — this logic is testable on its own, and
keeps app.py focused on layout rather than analysis logic.

CORE RULE THIS FILE FOLLOWS (per the project brief):
Never silently delete or modify data. Every function here only reads the
DataFrame and reports what it finds — it never changes uploaded data.
"""

import pandas as pd


def inspect_dataset(df):
    """
    Run all data-quality checks on a DataFrame and return a list of
    findings.

    WHAT IT RETURNS:
    A list of dictionaries, one per issue found. Each looks like:
        {
            "severity": "warning" or "info",
            "column": "Store" or None (None = affects the whole dataset),
            "title": "47 missing values",
            "detail": "This may affect any analysis grouped by Store...",
        }
    "warning" = likely to affect analysis results, worth checking.
    "info" = worth knowing about, less likely to break an analysis.

    HOW TO MODIFY LATER:
    Each check below is its own small function. To add a new type of
    check, write a new _check_xxx(df) function that returns a list of
    finding dicts (or an empty list if nothing found), then add a call to
    it in the `checks` list at the bottom of this function.
    """
    checks = [
        _check_missing_values(df),
        _check_duplicate_rows(df),
        _check_empty_columns(df),
        _check_whitespace(df),
        _check_inconsistent_categories(df),
        _check_invalid_dates(df),
        _check_numeric_outliers(df),
    ]
    # Flatten the list of lists into one list of findings
    findings = [finding for check_result in checks for finding in check_result]
    return findings


def _check_missing_values(df):
    findings = []
    missing_counts = df.isna().sum()
    total_rows = len(df)
    for column, count in missing_counts.items():
        if count > 0:
            pct = round(100 * count / total_rows, 1)
            findings.append({
                "severity": "warning",
                "column": column,
                "title": f"{count} missing value{'s' if count != 1 else ''} in '{column}' ({pct}% of rows)",
                "detail": (
                    f"Rows with a missing '{column}' value will be excluded from "
                    f"any calculation that groups or filters by this column "
                    f"(e.g. totals or averages by {column})."
                ),
            })
    return findings


def _check_duplicate_rows(df):
    findings = []
    duplicate_count = df.duplicated().sum()
    if duplicate_count > 0:
        findings.append({
            "severity": "warning",
            "column": None,
            "title": f"{duplicate_count} duplicate row{'s' if duplicate_count != 1 else ''} found",
            "detail": (
                "These rows are exact copies of other rows. If this data "
                "represents individual transactions, duplicates could "
                "inflate totals like SUM or COUNT. If it's expected (e.g. "
                "two identical sales really did happen), this can be ignored."
            ),
        })
    return findings


def _check_empty_columns(df):
    findings = []
    for column in df.columns:
        if df[column].isna().all():
            findings.append({
                "severity": "warning",
                "column": column,
                "title": f"'{column}' is completely empty",
                "detail": f"Every value in '{column}' is missing. This column can't be used in any analysis.",
            })
    return findings


def _check_whitespace(df):
    findings = []
    text_columns = df.select_dtypes(include="object").columns
    for column in text_columns:
        # Compare each value to its stripped version; count where they differ
        stripped = df[column].astype(str).str.strip()
        original = df[column].astype(str)
        affected = (stripped != original) & df[column].notna()
        count = affected.sum()
        if count > 0:
            findings.append({
                "severity": "info",
                "column": column,
                "title": f"{count} value{'s' if count != 1 else ''} in '{column}' have extra spaces",
                "detail": (
                    f"Some values in '{column}' have leading or trailing spaces "
                    f"(e.g. ' Widget ' instead of 'Widget'). This can cause "
                    f"identical-looking values to be treated as different "
                    f"categories when grouping."
                ),
            })
    return findings


def _check_inconsistent_categories(df):
    """
    Looks for text columns where different values are probably meant to be
    the same category, but differ in case or spacing (e.g. 'USA', 'usa',
    'U.S.A.'). We only flag this for columns with relatively few unique
    values, since that's the signature of a categorical column rather than
    free text (like product names or descriptions).
    """
    findings = []
    text_columns = df.select_dtypes(include="object").columns
    for column in text_columns:
        values = df[column].dropna().astype(str).str.strip()
        unique_values = values.unique()
        # Only check columns that look categorical (not free text)
        if len(unique_values) == 0 or len(unique_values) > 30:
            continue
        # Group values by a "normalised" version (lowercase, no punctuation/spaces)
        normalised_groups = {}
        for value in unique_values:
            key = "".join(ch.lower() for ch in value if ch.isalnum())
            normalised_groups.setdefault(key, []).append(value)
        # Any group with more than 1 distinct original spelling is suspicious
        for key, variants in normalised_groups.items():
            if len(variants) > 1:
                variant_list = ", ".join(f"'{v}'" for v in variants)
                findings.append({
                    "severity": "warning",
                    "column": column,
                    "title": f"Possible inconsistent category in '{column}': {variant_list}",
                    "detail": (
                        f"These values look like they might be meant to be the "
                        f"same category, but are spelled or capitalised "
                        f"differently. If they're meant to be the same, "
                        f"grouping by '{column}' will currently split them "
                        f"into separate groups."
                    ),
                })
    return findings


def _check_invalid_dates(df):
    """
    For columns whose name suggests they contain dates (e.g. 'Date',
    'Order Date'), tries to parse every value as a date and reports how
    many failed. We only check columns with 'date' in the name to avoid
    false alarms on unrelated text columns.
    """
    findings = []
    date_like_columns = [c for c in df.columns if "date" in str(c).lower()]
    for column in date_like_columns:
        parsed = pd.to_datetime(df[column], errors="coerce")
        # A value "fails" if it was non-missing originally but became NaT (Not a Time)
        failed = parsed.isna() & df[column].notna()
        count = failed.sum()
        if count > 0:
            findings.append({
                "severity": "warning",
                "column": column,
                "title": f"{count} value{'s' if count != 1 else ''} in '{column}' don't look like valid dates",
                "detail": (
                    f"These values couldn't be understood as dates. Any "
                    f"trend or time-based analysis using '{column}' will "
                    f"skip these rows."
                ),
            })
    return findings


def _check_numeric_outliers(df):
    """
    For each numeric column, uses the IQR (interquartile range) method to
    flag unusually extreme values — a standard, simple statistical
    approach: anything more than 1.5x the IQR beyond the 25th/75th
    percentile is flagged as a possible outlier.
    """
    findings = []
    numeric_columns = df.select_dtypes(include="number").columns
    for column in numeric_columns:
        series = df[column].dropna()
        if len(series) < 4:
            continue  # not enough data to judge outliers meaningfully
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue  # all values identical or nearly so; skip
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        outliers = series[(series < lower_bound) | (series > upper_bound)]
        if len(outliers) > 0:
            example_values = ", ".join(str(v) for v in outliers.head(3).tolist())
            findings.append({
                "severity": "info",
                "column": column,
                "title": f"{len(outliers)} possible outlier{'s' if len(outliers) != 1 else ''} in '{column}' (e.g. {example_values})",
                "detail": (
                    f"These values are unusually high or low compared to the "
                    f"rest of '{column}'. They might be genuine, or they "
                    f"might be data-entry errors — worth a quick check "
                    f"before trusting averages or totals involving this column."
                ),
            })
    return findings
