# ARES Integration Evidence Checker

A lightweight interview prototype built for the ARES / NEST Energy Systems &
AI Research Lead case study. **It uses synthetic data only** and is designed
for a 3–5 minute demonstration, not production use.

## Problem

ARES is a consortium of four independent modelling teams (Solis, Tharsis,
Meridian, Helix). None of them is subordinate to ARES, and ARES owns no core
model itself. Ahead of a foundation review, the consortium needs one
repeatable demonstration showing how a proposed settlement configuration
performs under a normal case and a stress case — with results that are
traceable across models, and with validation, uncertainty, and evidence gaps
made explicit rather than hidden.

## What this artifact demonstrates

A small, ordered pipeline:

```
Authoritative model outputs (Solis / Tharsis / Meridian, synthetic)
        ↓
Structured interfaces (Pydantic schema + interface metadata)
        ↓
Deterministic validation (plain Python, no LLM)
        ↓
Traceable evidence chain (provenance diagram)
        ↓
Claude-assisted interpretation (structured input/output only)
        ↓
Human / partner review
```

Claude never decides whether the scientific system is valid. It only
interprets findings that deterministic Python logic has already produced.

## Architecture

- `data/scenarios.json` — two synthetic scenarios: Normal Operations and a
  72-hour Dust Storm, covering ~10 core variables across the three domain
  models plus one interface-metadata record.
- `src/models.py` — Pydantic schema. Three separate model families:
  - `Scenario` / `SolisData` / `TharsisData` / `MeridianData` /
    `ExchangedVariable` — the data contract for scenario inputs and for a
    variable exchanged across a model boundary (value, unit, source model,
    source version, time resolution, assumption id, confidence).
  - `ValidationFinding` — deterministic output only. Claude never writes to
    this model.
  - `AIInterpretation` — Claude's output, kept as a separate model so an LLM
    response can never overwrite a deterministic verdict.
- `src/validation.py` — five deterministic checks, pure Python, no LLM
  involved: scenario-id consistency, interface unit compatibility, capacity
  vs. peak demand, critical-load-served vs. Meridian's requirement, and
  stress-event metadata completeness.
- `src/traceability.py` — builds a small directed graph following the actual
  interface flow (Solis → interface variable → Tharsis → Meridian) and
  renders it with Plotly, showing variable names and interface metadata
  rather than a generic network layout.
- `src/llm.py` — Anthropic client, the system prompt (loaded from
  `prompts/interpretation_system_prompt.md`), and
  `generate_interpretations()`, which sends only `ValidationFinding` objects
  and minimal scenario context to Claude and parses the response into
  `AIInterpretation` objects.
- `app.py` — Streamlit UI and orchestration only; no business logic lives
  here.
- `tests/test_validation.py` — unit tests for the deterministic layer.

### Pipeline layering (data loading → schema → science)

These three steps are deliberately kept separate, both in code and in how
errors are surfaced:

1. **Data loading** (`models.load_raw_scenarios`) — plain `json.load`. A
   missing or corrupt file surfaces as a data-loading error in the UI.
2. **Schema validation** (`models.get_scenario`, via Pydantic) — malformed or
   missing fields raise `pydantic.ValidationError`, which the UI catches and
   displays explicitly. Execution stops before any scientific check runs.
3. **Scientific / interface validation** (`validation.run_checks`) — only
   ever receives an already schema-valid `Scenario`. It has no responsibility
   for, and never needs to handle, malformed input.

## How to run

```
pip install -r requirements.txt   # already satisfied in this project's venv
python -m pytest tests/ -v        # deterministic checks
streamlit run app.py
```

`ANTHROPIC_API_KEY` must be set in `.env` (already configured in this
project). The app only calls the Anthropic API when you click **Generate
board-level interpretation** — never automatically on rerun.

### Demo flow

1. Select **Normal Operations**, click **Run checks** — all five checks pass.
2. Switch to **72-hour Dust Storm**, click **Run checks** — a HIGH-severity
   capacity-envelope failure, a HIGH-severity critical-service-level failure,
   and a MEDIUM interface unit-mismatch warning appear.
3. Open the **Evidence Trace** section to see where `available_power_mw`
   comes from and how it propagates to Tharsis and Meridian.
4. Click **Generate board-level interpretation** to have Claude explain the
   non-passing findings.
5. Point out the **Findings & Ownership** table and the limitation statement
   at the bottom of the page.

## Role of AI

Claude receives only structured `ValidationFinding` objects (id, status,
severity, evidence, source models, owner — already computed by deterministic
Python) plus the scenario id/label. For each non-passing finding it returns:
why it matters, which partner(s) should investigate, what evidence is
missing, and what the finding does not establish.

## What AI does NOT do

Enforced by the system prompt in `prompts/interpretation_system_prompt.md`:

- Does not validate physics or recompute scientific outputs — authoritative
  models remain authoritative.
- Cannot override, soften, or change a deterministic PASS/FAIL/WARNING
  status or severity.
- Does not invent numeric values or evidence not given to it.
- Must distinguish observed evidence from its own inference.
- Must surface uncertainty and missing evidence rather than smoothing it
  over.
- Never claims or implies overall settlement resilience from one
  scenario-specific result.
- Recommends investigation; it does not make scientific decisions or close
  findings.

## Synthetic assumptions

- ~10 core variables across Solis (solar/battery capacity, operating
  reserve), Tharsis (peak demand, critical load served, unmet demand), and
  Meridian (required critical service level, stress event flag, duration).
- One interface-crossing variable, `available_power_mw` (Solis → Tharsis),
  carries a minimal metadata envelope: unit, source model, source version,
  time resolution, assumption id, confidence.
- The Dust Storm scenario deliberately mislabels that variable's unit as
  `kW` instead of `MW`, to demonstrate a semantic/interface validation
  failure distinct from a numeric capacity shortfall.
- All values are illustrative and not derived from real engineering models.

## Limitations

- Synthetic data only; no connection to any partner's real model output.
- Two scenarios, five checks — enough to demonstrate the pattern, not a
  complete validation suite.
- Claude's interpretation is non-deterministic by design and is not
  unit-tested for semantic content — only the deterministic layer is.
- A scenario passing its checks establishes only that scenario's internal
  consistency, not overall settlement resilience.
- No persistence, authentication, or multi-user support — this is a
  single-session local prototype.

## Future extensions

- Real (or partner-provided sample) data ingestion instead of bundled JSON.
- More interface-crossing variables carrying the full metadata envelope.
- A richer set of stress scenarios and deterministic checks per partner.
- Structured export of findings + interpretations for programme review
  records.
