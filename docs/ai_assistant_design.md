# Ask the Data: design and limits

## What it answers

Manager questions about **one selected synthetic status snapshot** and its
Received_Date reporting period, procedure categories, and request types.
Overview request-list Status selections and ID searches do not affect answers.
The original file's status snapshot date is **Not recorded**, never inferred
from Received_Date. Every answer labels its snapshot date and received period.
Changing snapshot or reporting scope removes stale answers.

## Python calculations and LangChain tools

`src/assistant_tools.py` defines typed, allowlisted LangChain tools:

| Tool | Arguments | Result |
| --- | --- | --- |
| `status_totals` | None | Total, Pending, Approved, Denied counts, denominators and percentages |
| `category_pending` | Typed view; optional exact category name | Category totals, Pending counts/rates, Approved/Denied counts, or count/rate/total leaders |
| `report_limitation` | Typed limitation reason | A predefined explanation of an unsupported request |

Extra arguments and unknown tools are rejected by explicit Pydantic validation
before execution (not merely by the provider schema). Tools close over the already
filtered cohort; the model cannot pass its own dataframe, SQL, code, paths,
snapshot IDs, reporting periods, or filters. Existing `status_summary`,
`category_summary`, `largest_pending_workload`, and `highest_pending_rate`
functions remain the numerical source of truth. Exact rate ties are retained;
ranking does not use rounded percentages.

Pending rate = Pending count ÷ category total × 100. Status share = status count
÷ Total Requests × 100. Largest Pending count and highest Pending rate are
different signals, not a combined score. All visible evidence is computed by
Python. Empty scopes are not assigned fabricated rates or findings.

## Bounded LangGraph flow

1. **Understand:** one model call receives the question and tool schemas, then
   chooses exactly one allowed typed tool. It does not receive CSV rows, request
   identifiers from the dataset, or calculated aggregate results.
   Obvious prohibited questions are declined before contacting the provider.
2. **Calculate:** execute that tool against the selected reporting cohort.
3. **Check:** Python repeats the selected calculation and requires an exact
   match with the evidence produced in the calculate step. This checks evidence
   consistency; it does **not** independently prove that the model interpreted
   the question correctly or selected the semantically best allowed tool.
4. **Present:** Python builds an approved descriptive explanation and evidence table.

There is no tool loop, retry loop, arbitrary code execution, or autonomous agent.
The graph has a recursion limit of six. OpenAI requests time out after 20 seconds
with SDK retries disabled and model output limited to 256 tokens.
Provider failures, malformed tool calls, and
verification failures produce a sanitized error, never an invented answer.
Free-form model answers are not displayed.

**Deliberate safety choice:** OpenAI interprets the question and selects a
tool; Python calculates the result and constructs the displayed explanation.
The verification step checks that Python's evidence is consistent, but does not
validate the model's interpretation. No second model call is used to narrate
numerical facts.

## Provider setup

Set `OPENAI_API_KEY` using **Replit Secrets**, not source files or the question
box. The app reads only this environment variable for the key. It never
prints it, renders it, or includes raw provider errors in the interface.
When absent, the screen displays setup instructions and disables submission.

The default is **`gpt-4.1-mini`**, a currently documented OpenAI model supporting
tool calling: <https://developers.openai.com/api/docs/models/gpt-4.1-mini>.
Set `OPENAI_MODEL` to change it to a compatible Chat Completions tool-calling
model. The current settings include temperature zero; use a model that supports
that setting. API usage is billed by your OpenAI account.

Locally in VS Code, set these environment variables before running
`uv run streamlit run app.py`. There is no Replit SDK, proxy, or service required.
Never commit credentials; no dotenv file is required or loaded.

## Data boundaries

The model receives a system description, the user's question, and typed tool
schemas—not request rows, request identifiers, CSV content, or dataframes.
Calculated aggregate results are **not sent to the model**; Python builds the
explanation locally. Anything entered in the question is user-supplied text
that may be sent to OpenAI, not an app-attached dataset.
Do not enter sensitive information in the question box; this is synthetic-only.
LangSmith tracing is explicitly disabled during graph execution.

The question, tool outputs, and most recent answer live only in the active
Streamlit session. There is no saved question history, graph checkpointer,
vector database, RAG, multiple agents, or persistent assistant memory.
SQLite snapshot history remains separate and unchanged.

## Limitations

- No explanations of causes, clinical guidance, individual approval/denial
  recommendations, employee rankings, or individual request lookups.
- No turnaround-time or aging/SLA calculations, or other tools beyond the allowlist.
- No cross-snapshot AI comparisons, answering about another snapshot/period,
  or historical month-end statuses.
  The existing received-cohort comparison UI remains separate.
- A file's coverage does not prove completeness.
- Intent routing is model-assisted and can misunderstand a question. Users
  should check the displayed scope, calculation chosen, and evidence; rephrase
  an ambiguous question. No model-generated numerical facts are trusted.
- The denial rate is descriptive, not a quality score.

## Verification

Run `uv run python -m unittest discover -s tests -q`.
New tests use mocked tool selections and temporary snapshot databases, never
API calls. They cover existing calculation parity, distinct leaders, scoped
answers, selected snapshots, ignored request-list filters, stale-answer removal,
unsupported questions, empty results, missing keys, malformed tool calls,
verification failures, and sanitized model errors.
