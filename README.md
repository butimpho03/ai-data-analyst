# AI Data Analyst Assistant

A phone-first, cloud-hosted tool that analyses uploaded Excel/CSV data.
Upload a file, ask a question in plain English, and get a real calculated
answer — with the method shown, data-quality issues flagged, and an
optional AI-written explanation.

**Live app:** `https://[your-app-name].streamlit.app`

## Why this project

Built while learning data analytics (Excel → SQL → Power BI), as a way to
demonstrate the core analyst skill this project is built around:

> **AI never calculates. Pandas calculates. AI only explains.**

Every number in this app comes from a deterministic pandas function that
can be independently verified by hand — the same way you'd check a
spreadsheet formula. The AI's only job is understanding a typed question
and writing a plain-English explanation of a result that was already
computed.

## What it does

- Upload a `.csv` or `.xlsx` file
- Automatic data-quality inspection: missing values, duplicates, empty
  columns, inconsistent categories (e.g. "USA" vs "usa"), invalid dates,
  stray whitespace, and statistical outliers — reported, never silently
  fixed
- Ask a question in plain English ("total sales by store", "top 5
  products by revenue", "which store had the highest average sales?")
- Every answer shown with **Question → Data Used → Method → Result** —
  so the calculation is never a black box
- Automatic charts (bar/line/pie/scatter) when a result is chart-shaped,
  never forced onto a result that wouldn't benefit from one
- Optional AI-written explanations and a full business summary, both
  built strictly from already-computed results
- A manual "build the analysis yourself" tool as a fallback/learning aid,
  using the exact same calculation engine as the question box

## Architecture

```
Phone browser
   |
Streamlit app (UI + orchestration)
   |
   |-- data_loader.py       reads CSV/XLSX, auto-detects delimiters,
   |                        recovers common file-export mistakes
   |-- data_quality.py      7 independent data-quality checks
   |-- analysis_engine.py   deterministic pandas calculations (the
   |                        only place any number is ever computed)
   |-- nl_planner.py        rule-based question -> calculation plan
   |                        (keeps working even if the AI is down)
   |-- chart_builder.py     decides if/how a result should be charted
   |-- ai_provider.py       swappable AI interface (currently Groq)
   |-- business_summary.py  written report built only from real,
                            already-computed results
```

**Why Streamlit, not a separate React/FastAPI split:** a single Python
app removes the need for a second language, a separate build step, and
CORS configuration — appropriate for a phone-first, no-local-install
workflow, and Streamlit is itself a tool real data analysts use.

**Why a rule-based planner exists alongside AI:** the brief required the
app to keep doing real analysis even if the AI service is unavailable.
`nl_planner.py` handles common question phrasings with keyword and
pattern matching — no AI call, no API cost, no dependency on an external
service being up.

**The AIProvider interface:** `ai_provider.py` defines an abstract base
class. Today it has one implementation (Groq, free tier, OpenAI-compatible
API). Swapping providers later means writing one new class — nothing else
in the app changes.

## Tech stack

- **App framework:** Streamlit
- **Data analysis:** pandas, openpyxl
- **Charts:** Plotly
- **AI:** Groq (Llama 3.3 70B), free tier, no credit card required
- **Hosting:** Streamlit Community Cloud (free tier)
- **Dev environment:** GitHub web UI + Streamlit Community Cloud, entirely
  from a phone browser — no local Python/Node install required

## Security & data handling

- Uploaded files exist only in memory for the browser session — never
  written to a database or disk
- API keys are never in code — read from Streamlit Cloud's encrypted
  secrets manager
- Only small, minimal summaries (numbers already shown in the app) are
  ever sent to the AI provider — never the raw uploaded dataset
- Internal error details are never shown in the UI, since this is a
  public deployment

## Known limitations (by design, for a v1)

- Trend/decline detection over time isn't built yet — the app says so
  honestly rather than guessing
- The rule-based question parser handles common phrasings well but isn't
  a full natural-language understanding system — messier phrasing may
  need the manual analysis tool instead
- No database — everything is session-based, which keeps the
  architecture simple but means results don't persist between visits

## What I learned building this

- Deterministic vs. AI-generated output, and why the boundary matters for
  trustworthy analysis
- Streamlit's rerun model, and the specific bug class it causes with
  nested buttons (fixed using `session_state`)
- Why regex-based text matching needs word boundaries, not substring
  checks (found and fixed 3 real bugs this way during testing)
- Designing for graceful degradation — every AI-dependent feature has a
  defined, tested fallback behaviour
- Cloud-native development entirely from a phone browser: GitHub's web
  editor, Streamlit Community Cloud deployment, and managing secrets
  without a local terminal
