import streamlit as st
from pydantic import ValidationError

from src.llm import generate_interpretations
from src.models import get_scenario, list_scenario_options
from src.traceability import build_trace_graph, render_trace_figure
from src.validation import run_checks

st.set_page_config(page_title="ARES Integration Evidence Checker", page_icon="🛰️", layout="wide")

st.title("ARES Integration Evidence Checker")
st.caption("Traceable cross-model validation with AI-assisted interpretation")

with st.sidebar:
    st.subheader("Guardrails")
    st.markdown(
        "- Domain models remain authoritative\n"
        "- Deterministic checks precede AI\n"
        "- Missing/invalid evidence blocks unsupported conclusions\n"
        "- AI interprets evidence; humans/domain owners make scientific decisions"
    )

# --- Data loading (separate from schema validation, separate from scientific validation) ---
try:
    options = list_scenario_options()
except Exception as exc:
    st.error(f"Could not load scenario data file: {exc}")
    st.stop()

labels = [o["label"] for o in options]
ids_by_label = {o["label"]: o["scenario_id"] for o in options}

top_col1, top_col2 = st.columns([3, 1])
with top_col1:
    selected_label = st.selectbox("Scenario", labels, index=0)
selected_id = ids_by_label[selected_label]
with top_col2:
    st.write("")
    run_clicked = st.button("Run checks", type="primary")

# --- Schema validation layer ---
try:
    scenario = get_scenario(selected_id)
except ValidationError as exc:
    st.error("Scenario data failed schema validation and cannot proceed to scientific checks.")
    with st.expander("Schema validation details"):
        st.code(str(exc))
    st.stop()
except Exception as exc:
    st.error(f"Could not load scenario '{selected_id}': {exc}")
    st.stop()

# --- A. Scenario Summary ---
st.header("A. Scenario Summary")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("**Solis** — infrastructure")
    st.metric("Solar capacity", f"{scenario.solis.solar_capacity_mw} MW")
    st.metric("Battery capacity", f"{scenario.solis.battery_capacity_mw} MW")
    st.metric("Operating reserve", f"{scenario.solis.operating_reserve_pct}%")
with col2:
    st.markdown("**Tharsis** — operations")
    st.metric("Peak demand", f"{scenario.tharsis.peak_demand_mw} MW")
    st.metric("Critical load served", f"{scenario.tharsis.critical_load_served_pct}%")
    st.metric("Unmet demand", f"{scenario.tharsis.unmet_demand_mwh} MWh")
with col3:
    st.markdown("**Meridian** — resilience")
    st.metric("Required critical service", f"{scenario.meridian.required_critical_service_pct}%")
    st.metric("Stress event", "Yes" if scenario.meridian.stress_event else "No")
    st.metric("Duration", f"{scenario.meridian.duration_hours} h")

if scenario.exchanged_variables:
    with st.expander("Interface / exchanged variable metadata"):
        st.json([v.model_dump() for v in scenario.exchanged_variables])

findings_key = f"findings::{selected_id}"
interp_key = f"interpretations::{selected_id}"

if run_clicked:
    st.session_state[findings_key] = run_checks(scenario)
    st.session_state.pop(interp_key, None)

if findings_key not in st.session_state:
    st.info("Click **Run checks** to execute deterministic validation for this scenario.")
    st.stop()

findings = st.session_state[findings_key]

# --- B. Validation Results ---
st.header("B. Validation Results")
pass_count = sum(1 for f in findings if f.status == "PASS")
warn_count = sum(1 for f in findings if f.status == "WARNING")
fail_count = sum(1 for f in findings if f.status == "FAIL")
blocked_count = sum(1 for f in findings if f.status == "BLOCKED")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Pass", pass_count)
c2.metric("Warning", warn_count)
c3.metric("Fail", fail_count)
c4.metric("Blocked", blocked_count)

STATUS_ICON = {"PASS": "✅", "WARNING": "⚠️", "FAIL": "❌", "BLOCKED": "🚧"}


def _severity_display(f):
    return "—" if f.status == "PASS" else f.severity


for f in findings:
    st.write(f"{STATUS_ICON[f.status]} **{f.variable}** — {f.status} ({_severity_display(f)}): {f.evidence}")

# --- C. Evidence Trace ---
st.header("C. Evidence Trace")
st.caption("Solis → interface variable → Tharsis → Meridian: provenance for the checks above.")
graph = build_trace_graph(scenario)
st.plotly_chart(render_trace_figure(graph), use_container_width=True)

# --- D. Findings & Ownership ---
st.header("D. Findings & Ownership")
STATUS_LABEL = {"PASS": "Verified", "WARNING": "Open", "FAIL": "Open", "BLOCKED": "Awaiting evidence"}
table_rows = [
    {
        "Finding": f.evidence,
        "Severity": _severity_display(f),
        "Evidence": " → ".join(f.source_models),
        "Owner": f.owner,
        "Status": STATUS_LABEL[f.status],
    }
    for f in findings
]
st.dataframe(table_rows, use_container_width=True, hide_index=True)

# --- E. AI Interpretation ---
st.header("E. AI Interpretation")
st.caption(
    "Claude receives only the deterministic findings above. It cannot change "
    "PASS/FAIL outcomes, severities, or evidence — it only interprets them."
)

notable = [f for f in findings if f.status != "PASS"]

if not notable:
    st.success("No non-passing findings for this scenario — nothing to interpret.")
else:
    if st.button("Generate board-level interpretation"):
        with st.spinner("Claude is interpreting the findings..."):
            try:
                st.session_state[interp_key] = generate_interpretations(
                    notable, {"scenario_id": scenario.scenario_id, "label": scenario.label}
                )
            except Exception as exc:
                st.error(f"Could not generate a structured interpretation: {exc}")

    interpretations = st.session_state.get(interp_key)
    if interpretations:
        findings_by_id = {f.id: f for f in findings}
        for interp in interpretations:
            source = findings_by_id.get(interp.finding_id)
            title = source.variable if source else interp.finding_id
            with st.container(border=True):
                st.markdown(f"**{title}**")
                st.write(f"**Why it matters:** {interp.why_it_matters}")
                st.write(f"**Recommended investigation:** {interp.recommended_investigation}")
                st.write(f"**Evidence gap:** {interp.evidence_gap}")
                st.write(f"**Limitation:** {interp.limitation}")

st.divider()
st.caption(
    "This demonstration is scenario-specific and uses synthetic data. It does not "
    "establish overall settlement resilience, and does not replace partner "
    "validation, physical testing, or human review."
)
