"""
data_loader.py — turns an uploaded file into a pandas DataFrame.

WHY THIS IS A SEPARATE FILE:
app.py is about to grow a lot over the next phases (data quality checks,
analysis, charts, AI calls). Keeping "how do we read a file" in its own
small file means app.py stays readable, and we can test this logic on its
own without needing Streamlit running at all.
"""

import pandas as pd


def load_dataset(uploaded_file):
    """
    Read an uploaded .csv or .xlsx file into a pandas DataFrame.

    WHAT IT DOES:
    Looks at the file's extension, picks the right pandas reader, and
    returns a 3-part result: (dataframe, error_message, notice_message).
    - On failure: (None, "what went wrong", None)
    - On success: (dataframe, None, None)
    - On success but with an automatic fix applied: (dataframe, None, "what we changed")
    The caller checks which of these it got instead of the app crashing on
    a bad file, and can tell the difference between "this failed" and
    "this worked, but here's something you should know."

    WHY THIS SHAPE:
    A manager might upload a corrupted file, an empty file, or a file where
    the data didn't split into columns properly. We want clear, distinct
    messages for real failures vs. "it worked, but double-check this."

    HOW TO MODIFY LATER:
    To support another file type (e.g. .tsv), add another `elif` branch
    below that calls the matching pandas reader function.
    """
    filename = uploaded_file.name
    extension = filename.lower().rsplit(".", 1)[-1]

    try:
        if extension == "csv":
            # WHY sep=None, engine="python":
            # Not all CSV files actually use commas — some spreadsheet apps
            # (depending on regional settings) export using semicolons
            # instead. Setting sep=None tells pandas to detect the real
            # delimiter automatically instead of assuming a comma, which
            # avoids the whole file being read as one giant column.
            df = pd.read_csv(uploaded_file, sep=None, engine="python")
        elif extension == "xlsx":
            df = pd.read_excel(uploaded_file)
        else:
            return None, f"Unsupported file type: .{extension}. Please upload a .csv or .xlsx file.", None
    except Exception as e:
        return None, f"Could not read this file. It may be corrupted or not a valid {extension.upper()} file. (Details: {e})", None

    if df.empty:
        return None, "The file was read successfully, but it contains no data (0 rows).", None

    if len(df.columns) == 0:
        return None, "The file was read successfully, but it contains no columns.", None

    # WHY THIS CHECK:
    # Sometimes a file loads "successfully" but ends up as one single column
    # of text, because the real column separator (e.g. a semicolon) is
    # sitting inside the data rather than being recognised as a delimiter.
    # This is common when someone builds an Excel file by pasting raw CSV
    # text into a single cell/column instead of properly splitting it.
    # We detect this and try to recover it automatically, but we always
    # tell the user it happened rather than silently changing their data.
    if df.shape[1] == 1:
        recovered_df, was_recovered = _try_recover_single_column(df)
        if was_recovered:
            notice = (
                "This file loaded as a single column, so it was automatically "
                "re-split using the delimiter found in the column header. "
                "Please check the preview below carefully to confirm the "
                "columns look correct."
            )
            return recovered_df, None, notice

    return df, None, None


def _try_recover_single_column(df):
    """
    If a file ends up as exactly 1 column, check whether the column header
    itself contains a delimiter character (;, tab, or |). If so, that's a
    strong sign the real data is delimiter-separated text that got read as
    one blob. We rebuild it as raw text and re-parse it with that delimiter.

    Returns (dataframe, was_recovered) — was_recovered is False if nothing
    useful was found, in which case the original single-column df is kept.
    """
    import io

    column_name = str(df.columns[0])
    for delimiter in [";", "\t", "|"]:
        if delimiter in column_name:
            header = column_name
            rows = df[column_name].astype(str).tolist()
            text = header + "\n" + "\n".join(rows)
            try:
                recovered = pd.read_csv(io.StringIO(text), sep=delimiter)
                if recovered.shape[1] > 1:
                    return recovered, True
            except Exception:
                continue
    return df, False
