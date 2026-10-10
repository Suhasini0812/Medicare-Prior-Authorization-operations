# Code review package guide

This portable package contains the current Streamlit/Pandas application, tests,
UV dependency lock, project documentation, a configuration example, and the
original synthetic CSV. It does not include a database, credentials, virtual
environment, caches, or deployed/Replit-only setup.
Its three implemented screens are Workload Overview, Priority Review, and
Ask the Data.

## Run and test

Use Python 3.10+ and UV. From this folder:

```bash
uv sync
uv run streamlit run app.py
```

Open the local address printed by Streamlit (normally `http://localhost:8501`).
Run tests with:

```bash
uv run python -m unittest discover -s tests -v
```

Ask the Data tests mock the model; they do not call OpenAI. For manual use,
export `OPENAI_API_KEY` in the process environment. `OPENAI_MODEL` is optional
and defaults to `gpt-4.1-mini`. `examples/environment.example` lists variable
names only and is not loaded by the app. Never commit a real key.

## Database and sample snapshots

The SQLite database is deliberately excluded. On first app start,
`SnapshotStore` creates `data/snapshots.sqlite3` and its schema. The original
`data/synthetic_ma_pa_requests.csv` remains selectable as the undated original
dataset; it is not automatically inserted into snapshot history.

The package includes a separate, optional synthetic full-snapshot example at
`examples/snapshots/synthetic_pa_followup_snapshot_2026-10-08.csv`. To reproduce
the tested demo, run the app, go to **Workload Overview**, and use **Upload
monthly snapshot** to select that file. Enter **October 8, 2026** as its
**Status as-of date**, confirm the synthetic-data declaration, and save. The
dashboard selects it after saving. Set the **Received-date reporting period**
to **All available data**. Expected results: **501 requests** — **403
Approved, 64 Denied, and 34 Pending**.

The example is not imported automatically and is a complete snapshot, not a
delta merged with the original CSV. The database starts empty in a fresh
package and does not contain saved snapshot history. If identical contents for
the same date are already saved in a local database, existing duplicate/revision
rules apply; they do not replace or delete prior history. No dataset-generation
script is present. The supplied original CSV remains the 500-row source file.

## Review map

- `app.py` — Streamlit entry point, navigation, database initialization and
  snapshot selection.
- `src/data_loader.py` — loads the supplied CSV and checks required columns.
- `src/snapshot_validation.py` — validates upload schema, values, IDs, dates
  and row contents before persistence.
- `src/snapshot_store.py` — initializes SQLite and atomically stores snapshots
  and revisions.
- `src/snapshot_selection.py` — loads one saved snapshot or the original CSV.
- `src/reporting.py`, `src/filters.py` — reporting periods, category/type
  scope, request-list-only filters, comparisons and UI controls.
- `src/metrics.py`, `src/priority_metrics.py` — status/date summaries and
  category-level counts and rates.
- `src/overview.py`, `src/overview_page.py`, `src/priority_page.py`,
  `src/priority_charts.py`, `src/pagination.py` — screen composition, cards,
  charts, tables and request-list pagination.
- `src/monthly_data.py` — upload, duplicate/revision confirmation and
  missing-Pending review.
- `src/assistant_tools.py`, `src/assistant_flow.py`, `src/ask_data_page.py` —
  typed calculation tools, bounded model-routing flow and Ask the Data screen.
- `src/styles.py`, `.streamlit/config.toml` — presentation styles and theme.
- `tests/` — mocked assistant, app-control, reporting, priority, pagination
  and snapshot validation/storage tests.
- `README.md`, `docs/operations_requirements.md`,
  `docs/ai_assistant_design.md`, `docs/test_results.md` — setup instructions,
  implementation boundaries, product requirements, and a dated verification
  record. Manual Preview results are labeled as user-reported separately from
  the automated test result.

## Ask the Data boundary

LangChain defines the typed, allowlisted tools in `src/assistant_tools.py`.
LangGraph runs the fixed understand → calculate → check → present flow in
`src/assistant_flow.py`. OpenAI interprets the user's question and chooses one
allowed tool. The model receives the system instructions, question, and tool
schemas—not CSV rows, dataset request identifiers, or calculated aggregate
results. Python executes the selected tool and constructs the displayed
explanation.

The check step repeats that same Python calculation and compares its evidence
with the prior calculation. This detects inconsistent calculation output; it
does not independently verify whether the model understood the question or
selected the most semantically appropriate allowed tool.

All three screens use one selected snapshot. Received-date reporting periods,
procedure categories and request types define the summary scope. Overview's
Status and PA Request ID controls narrow only its request list. Priority Review
shows largest Pending count and highest Pending rate separately. Turnaround,
aging/SLA analysis, cross-snapshot AI comparisons and production capabilities
are not implemented.

## Exclusions

No `.env` or Streamlit secrets file, secret value, SQLite/database file, saved
snapshot history, virtual environment, Python cache/bytecode, or deployment
credential is included.
