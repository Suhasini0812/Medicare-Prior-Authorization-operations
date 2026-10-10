# Medicare Advantage PA Operations Intelligence — synthetic prototype

A Streamlit Overview for managers exploring the supplied **synthetic** prior
authorization (PA) requests. It shows workload and recorded status mix, with
reporting controls, a searchable paginated request table, and integrated
full-snapshot upload and revision-history controls. It does not use real member
or clinical data or make individual approval/denial decisions.

## Project files

The sidebar includes Workload Overview, Priority Review, and Ask the Data.
Ask the Data uses a bounded LangChain/LangGraph workflow: OpenAI interprets a
question and selects one allowed tool; Python calculates the result and builds
the displayed explanation. The model does not receive request rows or calculated
aggregate results. See [the assistant design](docs/ai_assistant_design.md) for
its tools, limits, and environment-variable setup. `OPENAI_API_KEY` is optional
for using the other screens; without it, Ask the Data shows a setup message.

- `src/assistant_tools.py` exposes only typed aggregate calculations.
- `src/assistant_flow.py` routes, calculates, checks, and explains one question.
- `src/ask_data_page.py` provides the question form, scope labels, and evidence.

- `app.py` starts Streamlit and loads one current snapshot for all three screens.
- `src/data_loader.py` reads the CSV and checks that every required column is
  present. It explains what is missing if the file or its columns are wrong.
- `src/metrics.py` calculates the received-date range and status counts.
- `src/reporting.py` defines reporting periods, previous-period comparisons,
  filtering rules, and summary percentages without changing the data.
- `src/filters.py` provides reporting and table controls, including reset.
- `src/overview.py` displays summary cards and the scrollable, paginated request table.
- `src/pagination.py` calculates page boundaries without changing matching counts.
- `src/overview_page.py` puts those existing controls and calculations together
  for one selected snapshot. Changing snapshots resets filters to its full coverage.
- `src/monthly_data.py` shows upload review, confirmation, history, and missing-Pending warnings.
- `src/snapshot_validation.py` checks the CSV before any data is saved.
- `src/snapshot_store.py` saves complete snapshots and revisions atomically in
  SQLite, using Python's standard library; no database service is needed.
- `src/snapshot_selection.py` loads exactly one uploaded snapshot or the original file.
- `src/styles.py` applies the supplied visual reference's compact heading,
  workload-card accents, and spacing without changing calculations or hiding errors.
- `.streamlit/config.toml` defines the navy/teal presentation colors only.
- `tests/` checks reporting controls, validation, atomic saves, repeated uploads,
  revisions, reconciliation, and selecting different snapshots. Tests use temporary databases.
- `src/__init__.py` marks `src` as a Python package so its helper files can be
  imported by the app.
- `data/synthetic_ma_pa_requests.csv` is the supplied dataset used by the app.
- `examples/snapshots/synthetic_pa_followup_snapshot_2026-10-08.csv` is an
  optional synthetic full-snapshot example for reproducing the October 8, 2026 demo.
- `pyproject.toml` lists the project details and Python dependencies for UV.
- `uv.lock` records the resolved dependency versions after running `uv sync`.
- `.gitignore` keeps the local virtual environment and Python cache files out of
  Git, along with the generated SQLite database and its journal files.

## Run locally with UV

1. Install Python 3.10 or newer and [UV](https://docs.astral.sh/uv/).
2. Open a terminal in this project folder (`medicare-pa-operations`).
3. Install the project dependencies and create its local environment:

   ```bash
   uv sync
   ```

4. Start the app:

   ```bash
   uv run streamlit run app.py
   ```

5. Open the local address shown in the terminal (usually
   `http://localhost:8501`).

## Data file

The app reads `data/synthetic_ma_pa_requests.csv`, relative to the project
files. If the file is missing, or any expected column is missing, the app shows
a clear error instead of creating replacement data.

## Overview controls and interpretation

- Select **Original supplied CSV** and **All available data** to see 500 requests: 402 Approved (80.4%),
  63 Denied (12.6%), and 35 Pending (7.0%). Each percentage uses all 500
  requests as its denominator, including pending requests.
- Choose a month, quarter, year, or inclusive custom received-date period.
  Procedure-category and request-type selections update both the summary and
  table. An empty selection means all values.
- Table status selections and case-insensitive, literal PA Request ID search
  affect only the table, not the summary denominator.
- **Reset all filters** returns to the full selected snapshot and clears request list filters.
- Previous comparisons use the previous calendar month/quarter/year, or an
  adjacent custom period with the same number of days. Comparisons are enabled
  only when both windows are inside observed received-date coverage and both
  have records for the selected category/type scope.
- Observed coverage does not prove completeness. Period completeness cannot
  be established from this CSV, and no snapshot as-of date is inferred.
- Status shares and comparisons describe received cohorts in **one selected
  snapshot**, not historical month-end statuses. The denial rate is descriptive,
  not a quality score or a denial rate among decided requests only.
- The request list defaults to 25 rows per page, with 50 or 100 also available.
  Use the controls below the table to change rows per page, use Previous/Next,
  or enter a page number. Search/filter changes and
  snapshot changes reset the page; paging does not change summary counts.
  Scroll horizontally inside the table to reach all ten columns.
- Use **Navigation** to switch among **Workload Overview**, **Priority Review**,
  and **Ask the Data**. All three use the same selected snapshot and
  received-date/category/request-type reporting scope. Ask the Data does not use
  the request-list Status or PA Request ID filters.
- Workload cards are ordered Total Requests, Pending, Approved, Denied.
  Counts have plain percentages aligned to the right and slim share bars below;
  Total Requests shows 100%. The denial-rate caveat is in About this data.
  Status percentages use the full current reporting scope, including Pending.
  Denominator phrases are not displayed on the cards.
  For the original CSV, status snapshot date is **Not recorded**. Uploaded
  snapshots show the user's entered date and revision, separately from received-date coverage.
  Longer data caveats remain available in **About this data**.

## Priority Review

Two independent signals help a manager choose a category for process review:

- **Largest Pending Workload:** the category with the most recorded Pending
  requests in the selected reporting scope.
- **Highest Pending Rate:** Pending requests divided by all requests in that
  category's selected reporting scope, shown as a percentage.

Both show category totals and all exact ties. A high percentage in a small
category is not necessarily a large workload; interpret its displayed count
and denominator carefully. The category table lists every selected category,
ordered by Pending count, with total, Pending, Pending rate, Approved and Denied.
Empty scopes show no findings, and zero-Pending ties are not priority leads.

The sidebar snapshot and reporting filters apply across all three screens.
Overview's request-list Status and PA Request ID controls do not affect Priority
Review or Ask the Data. Changing screens preserves the reporting scope and
request-list selections; changing snapshots resets filters as before. Received
dates select requests; statuses come only from the selected snapshot.

The Priority Review cards explain their separate signals. The app does not
make individual approval/denial recommendations or claim causes.

The small files are organized as follows:

- `src/priority_metrics.py` calculates category counts and the two signals.
  Exact fractions distinguish real rate ties from rounded display ties.
- `src/priority_page.py` presents the two signal cards, category charts and summary table.
- `src/overview_page.py` supplies the shared snapshot and reporting context,
  then renders the selected screen.
- `tests/test_priority_review.py` checks the calculations, edge cases and navigation.

## Upload monthly snapshot

1. Use the always-visible **Upload monthly snapshot** CSV control at the top
   of Workload Overview, then enter the **Status as-of date** directly below.
   Choose a synthetic full-snapshot CSV and enter the
   date when its statuses were captured. The date starts blank and is never
   inferred from received dates, decision dates, the filename, or the upload time.
   Changing the file clears the date. Select a calendar day to confirm it,
   and check the date in the validation result before saving.
2. Check the concise validation result (all rows are checked), entered date,
   and any missing-Pending warning. There is no raw preview or separate review
   panel. Invalid files show useful errors and cannot be saved.
3. Confirm that the file contains synthetic data only. If different contents
   already exist for that date, also confirm creation of a **new revision**.
   Earlier revisions are preserved; nothing is overwritten.
4. Save. A confirmation appears and **the newly saved snapshot is selected**,
   including a backdated upload. New browser sessions default to the newest
   accepted status as-of date and highest revision, or the original CSV if
   no uploads exist.
5. **Current data snapshot** shows the status date, row count and received-date coverage.
   Use **Snapshot to view** in the sidebar to select the newest saved snapshot,
   any older snapshot/revision, or the original CSV. Saved history stays in SQLite;
   no large history list is shown on the main page. Cards and **Prior Authorization Data**
   read only that selection, never combined rows. Missing-Pending warnings remain
   in upload review and a compact expandable review for affected saved snapshots.
6. **Received-date reporting period** selects requests inside the chosen
   snapshot. Changing All available data, Month, Quarter, Year or Custom
   does not select a different snapshot or change its status as-of date.

### Reproduce the October 8, 2026 demo

1. In **Workload Overview**, use **Upload monthly snapshot** to select
   `examples/snapshots/synthetic_pa_followup_snapshot_2026-10-08.csv`.
2. Enter **October 8, 2026** as the **Status as-of date**, confirm the
   synthetic-data declaration, and save the snapshot.
3. After it saves, the dashboard selects it automatically. Set the
   **Received-date reporting period** to **All available data**.
4. The snapshot contains **501 requests**: **403 Approved**, **64 Denied**, and
   **34 Pending**.

The example is not loaded or imported automatically. This is a full snapshot,
not a delta to merge with the original CSV. If identical contents for that date
are already saved, the app's existing duplicate/revision rules apply; the
example does not replace or delete saved history.

### Upload validation

Use exactly the ten column headings listed in `src/data_loader.py`. All
fields need values except `Decision_Date` and `Denial_Reason`, which may be
blank. Missing approved/denied decision dates generate a warning and remain missing.

- UTF-8 CSV (a BOM is accepted), at most 10 MiB, with at least one request.
- No duplicate headings, extra columns, or inconsistent CSV row widths.
- No missing required columns or blank required values.
- `PA_Request_ID` must be unique within the file, after trimming surrounding whitespace.
- `Status`: Approved, Denied, Pending; `Request_Type`: Standard, Expedited.
- `Documentation_Status`: Complete, Incomplete; `Additional_Info_Requested`: Yes, No.
- `Resubmission_Count`: a nonnegative whole number.
- Dates: real `YYYY-MM-DD` calendar dates supported by Pandas reporting.
  Decision dates cannot precede received dates. Received/decision dates cannot
  be later than the user-entered status as-of date; correct the file or entered
  date rather than assigning an inferred date.

Invalid uploads save **nothing**. Valid snapshots are saved in one SQLite
transaction. Identical normalized request contents for the same date are
recognized even if filename, row order, or column order changes; no extra copy
is created. Identical contents on a different date are a separate snapshot.

### History and missing-Pending review

Request IDs may recur across snapshots. Records and statuses remain isolated by
snapshot. Compare against the immediately preceding accepted date/revision in
chronological order, not upload order. For a same-date revision, that means
the earlier revision. A backfilled snapshot can change which snapshot is the
previous chronological comparison when reviewing later history.

A previously Pending request missing from the selected snapshot is a review
warning, **not a resolution**. Earlier records remain available. The original
CSV has no status date and cannot be placed in chronological snapshot history;
it is not treated as a dated predecessor.

### Local persistence and limitations

`data/snapshots.sqlite3` is created automatically on first run and keeps accepted
uploads across app restarts. It is ignored by Git; transferring code and the
original CSV does not transfer saved uploads. Stop the app and copy that database
file separately if you want to transfer or back up prototype history.

This is a local synthetic prototype, not secure clinical storage. The synthetic
acknowledgment is a user declaration, not automated PHI detection. No login,
access controls, production audit trail, retention/deletion workflow, completeness
monitoring, or deployment is provided. A full-snapshot declaration does not prove
the file is complete. Uploaded dates are user-entered metadata, not independently
verified source timestamps.

Turnaround, aging/SLA analysis and cross-snapshot AI comparisons are not
implemented. The code-review package includes the original 500-row CSV and
the separate synthetic 501-row demo example, but not local database history.

## Run the checks

From this project folder:

```bash
uv run python -m unittest discover -s tests -v
```

See [test results](docs/test_results.md) for the current automated run and
user-reported Replit Preview checks, kept as separate kinds of evidence.
