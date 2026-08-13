"""
business_summary.py — builds a professional written summary from results
that have ALREADY been calculated by pandas, never inventing new numbers.

WHY THIS FILE EXISTS:
This is the "generate a professional summary" requirement from the brief.
It's the one part of the app that's genuinely AI-only — there's no
deterministic way to write natural-language prose. To keep this safe:
- It only ever summarizes results already shown to you elsewhere in the
  app (from results_history) — it cannot compute anything new itself.
- If you haven't run any analyses yet, it says so plainly instead of
  generating a summary out of nothing.
- It sends only a small, compact description of your results and data
  quality findings to the AI — never the raw uploaded dataset.
"""


def record_result(question_text, result):
    """
    Turns a single analysis_engine.py result into a small, compact
    dictionary safe to keep in a growing history and later send to the AI.
    Returns None if the result was an error (errors aren't useful to
    summarize as findings).
    """
    if result.get("error"):
        return None

    if result.get("result_value") is not None:
        value = result["result_value"]
        summary = f"Result: {round(float(value), 2) if isinstance(value, float) else value}"
    elif result.get("result_table") is not None:
        # Only the first 5 rows, kept small and readable for the AI prompt
        preview = result["result_table"].head(5).to_string(index=False)
        summary = f"Result table (up to 5 rows):\n{preview}"
    else:
        summary = "No result."

    return {
        "question": question_text,
        "method": result["method"],
        "summary": summary,
    }


def build_summary_prompt(df_shape, quality_findings, results_history):
    """
    Builds the prompt sent to the AI for the business summary. Deliberately
    small and specific — dataset shape (not the data itself), the top few
    data-quality findings, and the results already computed elsewhere in
    the app.
    """
    lines = [
        f"Dataset: {df_shape[0]} rows, {df_shape[1]} columns.",
        "",
        "Data quality findings (top issues only):",
    ]

    warnings = [f for f in quality_findings if f["severity"] == "warning"]
    if warnings:
        for finding in warnings[:5]:
            lines.append(f"- {finding['title']}")
    else:
        lines.append("- No significant data-quality issues were found.")

    lines.append("")
    lines.append("Analyses already run, with their real calculated results:")
    for i, entry in enumerate(results_history, start=1):
        lines.append(f"{i}. Question: {entry['question']}")
        lines.append(f"   Method: {entry['method']}")
        lines.append(f"   {entry['summary']}")

    lines.append("")
    lines.append(
        "Write a professional business summary for a manager who is not a "
        "data analyst, using ONLY the information above. Never invent or "
        "estimate any number that isn't given above. Structure it with "
        "these short sections: Key Finding, Supporting Numbers, Business "
        "Implications, Data Quality Warnings (if any), and Suggested Next "
        "Questions. If there isn't enough information for a section, say "
        "so briefly rather than making something up. Keep it concise."
    )

    return "\n".join(lines)
