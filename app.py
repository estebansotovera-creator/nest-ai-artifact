import streamlit as st

from src.llm import ask_claude

st.set_page_config(
    page_title="NEST AI Artifact",
    page_icon="🌍",
    layout="wide",
)

st.title("NEST AI Artifact")

st.write(
    "Prototype for AI-assisted scientific integration, "
    "traceability and validation."
)

prompt = st.text_area(
    "Prompt",
    value=(
        "You are supporting an energy systems modelling team. "
        "Explain in 5 concise bullet points how AI could help validate "
        "consistency between outputs from a national energy model "
        "and a city-scale model."
    ),
    height=180,
)

if st.button("Ask Claude"):
    if not prompt.strip():
        st.warning("Please enter a prompt.")
    else:
        with st.spinner("Claude is analyzing..."):
            try:
                response = ask_claude(prompt)
                st.subheader("Claude response")
                st.write(response)

            except Exception as exc:
                st.error(f"Claude API error: {exc}")