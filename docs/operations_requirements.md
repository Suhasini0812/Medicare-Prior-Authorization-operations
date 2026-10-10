# Medicare Advantage PA Operations Intelligence: agreed requirements

## 1. Product purpose and boundaries

The app is a **synthetic-data dashboard for a prior authorization (PA)
operations manager**. It helps the manager see workload patterns, identify
categories worth investigating, and understand possible manager follow-ups.
It does **not** make approval or denial decisions for individual requests.

Use synthetic data only in this demo. Findings must distinguish observed
patterns from possible explanations; do not claim a cause without evidence.

This document distinguishes current implementation from later prototype
possibilities and separate production requirements. The section headings state
which capabilities are implemented and which are not.

## 2. Existing project and data inspected

The portable Python project is in `medicare-pa-operations/`. The existing app
uses Streamlit and Pandas and reads
`medicare-pa-operations/data/synthetic_ma_pa_requests.csv`.

### What currently works

- Load the single supplied CSV and check that its expected columns exist.
- Show a clear error if the file or expected columns are missing.
- Display a synthetic-data notice, record count, received-date range, status
  counts, and the request table.
- The Overview now supports received-date month, quarter, year, and custom
  reporting periods, plus procedure-category and request-type summary filters.
- Table-only status filtering and PA Request ID search leave the summary's
  status mix unchanged. All filters can be reset.
- Workload cards show prominent counts with plain percentages aligned to the right,
  plus equal-height slim share bars below. No descriptive text appears in the cards;
  the descriptive-denial-rate caveat lives in About this data.
  Cards are ordered Total Requests, Pending, Approved, Denied. Total shows 100%; status
  percentages use all requests in the summary scope. Do not display denominator
  phrases inside the cards. The application title is centered in a full-width
  header above both columns, using bold 30px navy text. PA Operations and Prior
  Authorization Workload Review align below it and share the bold 21px teal
  style used for section headings. Do not add a page subtitle.
  Previous received
  cohorts can be compared when both date windows are within observed coverage
  and contain selected records. Completeness is not inferred from coverage.

- Workload Overview now provides synthetic full-snapshot CSV upload review, a required
  user-entered status as-of date, validation, and atomic local SQLite saves.
- Same-date identical contents are recognized; different contents require
  explicit new-revision confirmation, preserving earlier revisions.
- Snapshot history and the sidebar Snapshot to view dropdown keep each snapshot separate. The
  newest status date/highest revision is the default; the undated original remains selectable.
- Missing previously Pending requests are flagged for review, without invented resolutions.
- Workload Overview, Priority Review, and Ask the Data are functional screens,
  sharing one snapshot selector and the same received-date/category/request-type
  scope. Ask the Data uses that filtered cohort, but not the request-list-only
  Status and PA Request ID filters.
  Overview's layout is upload control, Current data
  snapshot, request-received date range, then workload results. The upload
  CSV control is always visible, with the status as-of date directly below.
  Show concise full-file validation, not a raw preview or separate review panel.
  Keep consent and revision confirmation; show save success only after persistence.
  Current data snapshot shows status date, row count and received-date coverage,
  without filenames, uploader/revision notes or a repeated synthetic banner.
  Snapshot to view is a separate sidebar dropdown, including all saved
  dates/revisions and the original; no large history list appears on the main page.
- Received-date reporting period filters requests within the selected snapshot;
  All available data, Month, Quarter, Year and Custom never switch snapshots.
  Missing-Pending warnings remain in upload review and a compact affected-snapshot review.
- The request list shows 25 rows per page by default, with 50/100 choices,
  page selection and Previous/Next controls below the table. Status and ID
  search remain directly above it under Prior Authorization Data. Matching counts and summary
  denominators use all matching records, not just the displayed page.
- A successful upload selects the newly saved snapshot, including backdated
  snapshots. New sessions still default to the newest status date/highest revision.
- Priority Review shows two separate category-level signals, not a score:
  Largest Pending Workload uses the highest Pending count; Highest Pending Rate
  uses Pending divided by all requests in that category's selected cohort.
  Show every exact tie, counts and category totals, with a low-volume caution.
  The category table shows total, Pending, Pending rate, Approved and Denied,
  sorted by Pending count descending. Empty scopes have no signals; zero-Pending
  ties are clearly labeled as not priority leads. Table-only Status and ID
  filters never affect these calculations.
- Ask the Data uses LangChain's typed, allowlisted tools and a bounded LangGraph
  flow: understand → calculate → check → present. OpenAI interprets the question
  and selects one allowed tool; Python calculates and builds the explanation.
  The model receives system instructions, the question and tool schemas—not
  CSV rows, dataset request identifiers or calculated aggregate results.
  The check step repeats the calculation, not an independent check of the
  model's interpretation.
- The current package includes only the supplied original 500-row CSV. It does
  not include the saved 501-row follow-up snapshot or the local SQLite history.
- Overview comparisons compare received-date cohorts using statuses from one
  selected snapshot. They are not historical month-end status trends. Dated
  uploads do not retroactively assign a capture date to the original CSV.

### Actual CSV columns

| Column | Meaning used by the requirements |
| --- | --- |
| `PA_Request_ID` | Identity of a request across snapshots. |
| `Received_Date` | Date used to assign requests to request-volume periods. |
| `Procedure_Category` | Category used to group workload and investigation leads. |
| `Request_Type` | Recorded request type, currently `Standard` or `Expedited`. |
| `Status` | Request status in the selected snapshot, currently `Approved`, `Denied`, or `Pending`. |
| `Decision_Date` | Date used to assign decisions to decision periods. |
| `Documentation_Status` | Recorded documentation status, currently `Complete` or `Incomplete`. |
| `Additional_Info_Requested` | Recorded additional-information indicator, currently `Yes` or `No`. |
| `Resubmission_Count` | Recorded number of resubmissions. |
| `Denial_Reason` | Recorded denial reason; not, by itself, proof of a category-level cause. |

The inspected file contains **500 records**, with no repeated
`PA_Request_ID` values. Status counts are **402 Approved, 63 Denied, and
35 Pending**. `Received_Date` runs from **2025-10-01 to 2026-09-29**.
Nonblank `Decision_Date` values run from **2025-10-04 to 2026-10-06**;
35 decision dates are blank.

There is **no snapshot as-of date column** in this CSV. The prototype must
capture that date separately as snapshot metadata. Do not invent a CSV
column or infer an as-of date from the file's latest received/decision date.
For the original CSV, display **“Status snapshot date: Not recorded.”**
The date when these statuses were captured is unknown. Do not assign an
assumed month-end date.

## 3. Implemented prototype: monthly full snapshots

### Upload and snapshot selection

- Support manual monthly uploads of **full snapshots**, not incremental
  updates. Each contains one row per in-scope PA request.
- Ask the user to enter the status **as-of date** with each uploaded file,
  store it as separate snapshot metadata, and display the date they entered.
  Do not infer it from `Received_Date`, `Decision_Date`, the upload date,
  or an assumed month-end date.
- Keep the snapshot date separate from the reporting-period filter: the
  snapshot selects the available state of the data; the reporting period
  selects the time window for a particular measure.
- Preserve earlier snapshots and allow the manager to select which
  snapshot is being viewed. Historical views must retain their historical
  statuses rather than showing a later snapshot's values.

### Request identity and counting

- A `PA_Request_ID` appearing in different monthly snapshots is expected.
  It is the same request with a newer recorded state, not a newly received
  request merely because it appears in another upload.
- Display the status recorded in the **selected snapshot**.
- Do not add monthly snapshot row counts together as a new-request total.
  When combining snapshots for request-volume reporting, count each
  `PA_Request_ID` only once for its applicable `Received_Date` period.
- A `PA_Request_ID` repeated **within one snapshot** is an error and must
  block that upload. Do not silently keep one row or deduplicate the file.

### Reuploads and same-date conflicts

- Recognize an identical file reuploaded for the same snapshot date.
  It must not create another copy that changes counts or history.
- A different file submitted for an already accepted snapshot date requires
  explicit **new revision** confirmation before acceptance. Replacement and
  deletion are not implemented. Never silently overwrite accepted data.
- Preserve earlier monthly snapshots. Make the effect of a same-date
  revision clear before the manager confirms it. Replacement is not supported.

### Implemented validation and storage rules

- Use exactly the ten documented columns. Reject unexpected fields, duplicate
  headings, inconsistent row widths, unreadable/non-UTF-8 files, empty snapshots,
  and files exceeding 10 MiB.
- All values are required except `Decision_Date` and `Denial_Reason`. Missing
  approved/denied decision dates are warned about, not replaced with guessed dates.
- Statuses must be Approved/Denied/Pending; request types Standard/Expedited;
  documentation Complete/Incomplete; additional-information flags Yes/No;
  resubmissions a nonnegative whole number.
- Date values must be real YYYY-MM-DD dates supported by Pandas reporting.
  Nonblank decision dates must be on/after their received dates. Neither date
  can be after the entered status as-of date. Metadata is never inferred to
  make an inconsistent file pass.
- Trim surrounding cell whitespace. Duplicate IDs are checked after trimming.
  Identical normalized contents ignore filename and row/column ordering.
- Require synthetic-only acknowledgment before any save. This declaration is
  not an automated PHI detector; real member/clinical data is out of scope.
- Accepted metadata and all request rows are written together to local
  `data/snapshots.sqlite3` using one transaction. Invalid uploads write no
  snapshot or rows. The generated database is not tracked by Git.
- History sorts by status as-of date and revision, not upload arrival time.
  A same-date revision compares with the immediately earlier revision. A
  backdated new date compares with the latest accepted earlier date.
- Reconciliation is recomputed from accepted chronological history on review,
  so adding backdated snapshots can change the previous comparison reference.
- The undated original is not used as a chronological predecessor.
- Selecting another snapshot resets reporting and request-list filters to
  prevent stale dates/categories from carrying into a different full snapshot.

### Missing previously pending requests

- Compare snapshots according to their as-of dates, not merely upload
  order.
- If a request was `Pending` in an earlier snapshot and is absent from a
  later full snapshot, flag its absence for manager review.
- Do not assume absence means approved, denied, otherwise resolved, or
  legitimately removed from scope.
- Keep the earlier record and status available in its historical
  snapshot. An absence is a reconciliation finding, not an invented
  current status or decision.

## 4. Implemented reporting and Priority Review, with later possibilities

### Time and counting rules

| Measure | Time/state basis | Required interpretation |
| --- | --- | --- |
| Request volume | `Received_Date` | Implemented: count requests in the selected snapshot received in the reporting period. |
| Decisions | `Decision_Date` | Not currently displayed as a reporting measure. If added later, use the decision date; do not substitute `Received_Date` or snapshot date for a missing decision date. |
| Backlog | Selected snapshot | Priority Review currently shows Pending counts/rates for the selected received-date cohort, not a complete snapshot backlog. |
| Status counts | Selected snapshot | Implemented: count statuses recorded in that one snapshot, not a mixture of statuses from different snapshots. |

The snapshot as-of date and reporting period must both be visible and
clearly labeled. If a period filter is applied to a snapshot-based status
or backlog view, label it as a filtered request cohort; do not imply it is
the complete snapshot backlog.

Comparisons must state their periods, snapshots, scope, and exclusions.
Use consistent populations for comparisons, and disclose limitations
instead of treating missing data as zero activity.

### Priority findings

The implemented signals are the separate Pending-count and Pending-rate
signals documented above. Received-cohort comparisons in Workload Overview
remain separate from Priority Review. The following requirements concern
possible later comparison-based findings, not current screen outputs.

Priority findings are **category-level investigation leads**, principally
grouped by the actual `Procedure_Category` field. They are not individual
request decisions or proven causal explanations.

For those later findings, consider:

- **High-volume patterns:** categories with substantial workload, not just
  categories with an unusual percentage.
- **Worsening patterns:** categories whose measured pattern has deteriorated
  against a clearly identified comparison.

Each finding must show:

1. The category, measure, selected snapshot, and relevant reporting period.
2. The underlying count and rate, where applicable.
3. The denominator and what population it represents, including exclusions.
4. The comparison values and change, with the comparison period/snapshot
   identified.
5. A suggested **manager follow-up**, phrased as an investigation step.
6. Any evidence limitations; a pattern alone does not establish its cause.

Use the existing fields when investigating documentation, additional
information requests, resubmissions, or recorded denial reasons. For
example, a manager follow-up may ask the manager to review a category's
documentation process. Do not state that documentation caused a worsening
pattern unless supporting evidence establishes that relationship.

Before implementation, agree the exact measures, denominator definitions,
comparison windows, and prioritization thresholds. This document does not
invent ranking weights, service-level targets, or decision policies.

## 5. Implemented prototype scope versus production requirements

### Implemented in the current synthetic prototype

- Manual monthly full-snapshot upload with a separately supplied as-of date.
- Preserved snapshot history and selection of the snapshot being viewed.
- Duplicate-ID blocking, identical-reupload recognition, and explicit
  confirmation of same-date revisions without replacing earlier data.
- Review flags for previously pending requests missing from a later full
  snapshot.
- Reporting-period summaries based on `Received_Date`, within one selected
  snapshot, with status, category, request-type and request-list controls.
- Separate category-level largest-Pending-count and highest-Pending-rate
  signals, charts and a summary table. The app does not implement
  worsening-pattern recommendations, causal findings, or a combined score.
- Ask the Data with typed, allowlisted tools and Python-calculated results;
  see `medicare-pa-operations/docs/ai_assistant_design.md` for its scope and
  limitations.

Turnaround, aging/SLA analysis and cross-snapshot AI comparisons are not
implemented. The future comparison-based findings above are not current
production capabilities.

### Separate production requirements, not implemented or assured by this demo

- Secure access, appropriate authorization, and secure storage.
- Audit history of access, uploads, revisions, replacements, and actions.
- Retention and deletion rules for source files, snapshots, and records.
- Data-feed monitoring for completeness, freshness, failures, and changes
  in format or scope.
- Daily or real-time integrations and their operating controls.

Preserving prototype snapshots is not a claim that production-grade audit
history, secure storage, or retention controls already exist. Introducing
real data would require a separately agreed production design and controls;
this demo remains synthetic-only.

## 6. Remaining decisions for later stages

- The precise definition of an in-scope request in each full snapshot,
  especially whether closed requests remain included in later snapshots.
- Whether replacement/deletion should ever be allowed; this prototype supports
  append-only revisions and selection of every preserved revision.
- The measures, comparison windows, denominators, and thresholds for
  priority findings.
- How to surface conflicting received dates or other identity-related
  changes for the same `PA_Request_ID`, without silently reclassifying it
  as a new request.

These open implementation details do not weaken the agreed rules above.
The original requirements-documentation step did not change app behavior.
The implemented combined Overview workflow is identified in section 2.
The supplied CSV and publishing settings remain unchanged.
