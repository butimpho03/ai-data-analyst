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
    returns either (dataframe, None) on success or (None, error_message)
    on failure — the caller checks which one it got instead of the app
    crashing on a bad file.

    WHY THIS SHAPE (returning a tuple instead of raising an error):
    A manager might upload a corrupted file, an empty file, or a .txt file
    by mistake. We want to show them a clear message instead of letting
    the whole app crash. Returning (result, error) is a common pattern for
    "this might fail in an expected way."

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
            return None, f"Unsupported file type: .{extension}. Please upload a .csv or .xlsx file."
    except Exception as e:
        return None, f"Could not read this file. It may be corrupted or not a valid {extension.upper()} file. (Details: {e})"

    if df.empty:
        return None, "The file was read successfully, but it contains no data (0 rows)."

    if len(df.columns) == 0:
        return None, "The file was read successfully, but it contains no columns."

    return df, None    try:
        if extension == "csv":
            df = pd.read_csv(uploaded_file)
        elif extension == "xlsx":
            df = pd.read_excel(uploaded_file)
        else:
            return None, f"Unsupported file type: .{extension}. Please upload a .csv or .xlsx file."
    except Exception as e:
        return None, f"Could not read this file. It may be corrupted or not a valid {extension.upper()} file. (Details: {e})"

    if df.empty:
        return None, "The file was read successfully, but it contains no data (0 rows)."

    if len(df.columns) == 0:
        return None, "The file was read successfully, but it contains no columns."

    return df, None
