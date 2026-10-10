# PA Operations Dashboard — Test Results

## Manual checks

### User-reported passes in Replit Preview on October 10, 2026

The following Preview checks were reported as passing by the user. They are
recorded here as user-reported results; they were not independently repeated
for this documentation update.

| Scope | Question/action | Expected result | Reported result |
|---|---|---|---|
| October 8, 2026 · Revision 1 · All available data | Review status totals. | 501 total: 403 Approved, 64 Denied, 34 Pending. | Pass, user-reported. |
| Same snapshot and scope | Review Largest Pending Workload. | Advanced Imaging: 16 Pending / 191 total, approximately 8.4%. | Pass, user-reported. |
| Same snapshot and scope | Review Highest Pending Rate. | Advanced Imaging: 16 / 191, approximately 8.4%. | Pass, user-reported. |
| Same snapshot · Custom July 1–September 30, 2026 | Review Highest Pending Rate. | Physical Therapy: 8 / 23, approximately 34.8%. | Pass, user-reported. |
| Same July–September scope | Review Largest Pending Workload. | Advanced Imaging: 16 / 50, 32.0%; the count and rate leaders can differ. | Pass, user-reported. |
| Original CSV · All available data | Review status totals. | 500 total: 402 Approved, 63 Denied, 35 Pending. | Pass, user-reported. |
| October 8 snapshot · All available data | Set Overview's table-only Status filter to Pending, then ask for status totals in Ask the Data. | Summary remains 501 total: 403 Approved, 64 Denied, 34 Pending. | Pass, user-reported. |
| October 8 snapshot | Ask: “Why are these requests Pending?” | Explain the available-data limitation without inventing causes. | Pass, user-reported. |
| October 8 snapshot · Custom January 1–31, 2027 | Ask for the highest Pending rate. | Report no matching requests; provide no category winner or fabricated percentage. | Pass, user-reported. |

## Automated checks

Run on **October 10, 2026**, from the `medicare-pa-operations` project
directory:

```bash
uv run --no-sync --frozen --offline python -m unittest discover -s tests -v
```

**Result: 63 tests passed; 0 failed.** Assistant behavior was tested with
mocked models. The test run made no live API calls. Streamlit emitted
`ScriptRunContext` warnings in its bare test harness; the affected tests passed.

An initial invocation from the workspace's parent directory could not locate
the project's `tests` directory. Running the command from the project directory
above completed successfully.

## What these checks establish

Automated tests verify the tested application paths using controlled inputs and
mocked models; they do not verify live model responses. The Preview checks above
are user-reported and sample real model interpretation. Neither set of checks
proves that every possible question will be interpreted correctly. These
results do not establish period completeness, historical month-end statuses,
or production readiness.
