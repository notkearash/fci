# Vision One Million Scorecard

Automated data collection for the Waterloo Region's Vision One Million Scorecard using a LangGraph multi-agent pipeline.

This project was built for the **FCI x GKWCC Winter 2026 Hackathon** at the University of Waterloo. The goal is to replace a manual, twice-yearly research workflow with an agent system that can discover public data sources, extract the right metric, validate the result, assess initiative status, and produce an updated scorecard JSON.

## Why This Exists

The Vision One Million Scorecard tracks regional readiness across five sectors:

- Housing
- Transportation
- Healthcare
- Employment
- Placemaking

Each initiative has a metric, a target, and a status:

- `ACHIEVED`
- `ON_TRACK`
- `IN_PROGRESS`
- `NEEDS_ATTENTION`
- `NO_ASSESSMENT`

Historically, updating the scorecard meant manually visiting websites, reading reports, downloading spreadsheets, and copying values into a summary document. This codebase turns that workflow into a repeatable pipeline.

## What The Pipeline Does

For each initiative, the system:

1. Finds the best public data source.
2. Fetches and extracts the metric from HTML, CSV, XLSX, PDF, or API-style sources.
3. Validates that the extracted value is usable.
4. Compares the metric against the initiative target.
5. Produces a machine-readable result with status and reasoning.

The graph flow is:

```text
discovery -> extraction -> validation --(pass)--> mapper -> reporter -> END
                                      \--(fail, retry<3)--> discovery
                                      \--(exhausted)------> exhausted -> END
```

## Architecture

### Agents

- `agents/discovery.py`
  Finds candidate sources using predefined mappings first, then web search.
- `agents/extraction.py`
  Pulls source content and extracts the metric value and context.
- `agents/validation.py`
  Deterministic validation with retry handling.
- `agents/mapper.py`
  Assigns a scorecard status based on extracted data and target value.
- `agents/reporter.py`
  Produces the final narrative summary for the run.
- `agents/orchestrator.py`
  Wires the full LangGraph pipeline together.
- `agents/llm.py`
  Central OpenAI model configuration.

### Tools

- `tools/search.py`
  Tavily search and extract helpers.
- `tools/crawler.py`
  URL checks, page fetches, and table scraping.
- `tools/download.py`
  File download helpers for structured sources.
- `tools/parser.py`
  Numeric parsing and target comparison utilities.

### Schema

- `schema/state.py`
  Pydantic models for initiatives, sources, extracted values, and results.
- `schema/graph.py`
  The LangGraph pipeline state definition.

### Prompts

- `prompts/discovery.py`
- `prompts/extraction.py`
- `prompts/mapper.py`
- `prompts/reporter.py`

## Repository Layout

```text
.
├── agents/
├── prompts/
├── schema/
├── tools/
├── .env.example
├── pyproject.toml
├── run.py
├── run.sh
├── README.md
└── uv.lock
```

## Tech Stack

- Python 3.12+
- `uv` for dependency management
- LangGraph + LangChain
- OpenAI models for agent reasoning
- Tavily for web discovery
- `httpx` + Beautiful Soup for scraping
- `openpyxl` for spreadsheet parsing
- Pydantic for structured state

## Environment Variables

Create `.env` from `.env.example` and fill in:

```env
OPENAI_API_KEY=...
TAVILY_API_KEY=...
LANGSMITH_API_KEY=...
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=vision-1m-scorecard
```

Notes:

- `OPENAI_API_KEY` is required.
- `TAVILY_API_KEY` is required for discovery via web search.
- LangSmith variables are optional unless you want tracing.

## Quick Start

### 1. Install dependencies

```bash
uv sync
```

### 2. Create local env file

```bash
cp .env.example .env
```

### 3. Run one initiative

```bash
./run.sh --single housing-4
```

### 4. Run the full pipeline

```bash
./run.sh
```

Equivalent direct command:

```bash
uv run python run.py --single housing-4
```

## Shell Runner

This repo includes a small wrapper script:

```bash
./run.sh [args]
```

Examples:

```bash
./run.sh --single housing-4
./run.sh
```

## Output

- Single-initiative runs print the final pipeline state to stdout.
- Full runs write `scorecard_output.json` in the project root.

## Current Status

This implementation is designed around the hackathon flow and has already been proven on at least one end-to-end initiative flow: `housing-4` using a CMHC XLSX source and mapping the result to `ACHIEVED`.

## Important Repo Snapshot Notes

This checked-in repo is not fully self-contained yet.

- `run.py` expects an `output.json` file in the project root, but that file is not present in this snapshot.
- `agents/discovery.py` imports `data.sources`, but the `data/` package is not present in this snapshot.
- The original project description references assets like `BestWR.pdf`, `system-design.html`, and `fci.docx`, but they are not present here.

That means the documented pipeline architecture is in place, but a fresh clone of this exact snapshot will still need those missing project files restored before the full pipeline can run successfully.

## Design Choices

- Predefined sources are intended to be checked before live search.
- Validation is deterministic and can trigger up to three retries.
- Failed retries degrade to `NO_ASSESSMENT` instead of crashing the whole scorecard build.
- Agent responsibilities are separated cleanly so each stage can be tested in isolation.
- The project uses `uv`, not `pip`, as the default package workflow.

## Known Limitations

- Some scorecard metrics are easier to automate than others.
- Qualitative milestones may still require manual review or more specialized scraping.
- Running all initiatives can create a high number of HTTP requests and LLM calls.
- Source quality matters: landing pages are less reliable than direct CSV/XLSX/API endpoints.

## What To Build Next

- Restore or recreate `data/sources.py` with initiative-to-source mappings.
- Add the missing `output.json` input file to the repository.
- Expand predefined coverage for more initiatives.
- Replace landing pages with direct machine-readable source URLs where possible.
- Add historical snapshots and diff-based alerting.
- Add a dashboard layer on top of the generated scorecard output.

## Run Commands

Single initiative:

```bash
./run.sh --single housing-4
```

All initiatives:

```bash
./run.sh
```
