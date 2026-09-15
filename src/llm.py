"""Anthropic client and Claude-assisted interpretation of validation findings.

Claude only ever receives ValidationFinding objects (already computed
deterministically by src/validation.py) plus minimal scenario context, and
only ever returns AIInterpretation objects. It has no path to modify a
ValidationFinding's status, severity, or evidence.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

from anthropic import Anthropic
from dotenv import load_dotenv

from src.models import AIInterpretation, ValidationFinding

load_dotenv()

client = Anthropic()

MODEL_NAME = "claude-sonnet-4-5"

_SYSTEM_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "interpretation_system_prompt.md"
SYSTEM_PROMPT = _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines)
    return text


def generate_interpretations(
    findings: List[ValidationFinding], scenario_context: Dict[str, Any]
) -> List[AIInterpretation]:
    """Sends deterministic findings to Claude and returns structured interpretations.

    Raises on API or parsing failure; callers should catch and surface the
    error rather than silently retrying, since interpretation is explicitly
    non-deterministic and best-effort.
    """
    if not findings:
        return []

    payload = {
        "scenario": scenario_context,
        "findings": [f.model_dump() for f in findings],
    }

    user_message = (
        "Interpret the following deterministic validation findings for a "
        "board-level audience. Respond only with the JSON array described in "
        "the system prompt.\n\n" + json.dumps(payload, indent=2)
    )

    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = _strip_code_fence(response.content[0].text)
    data = json.loads(raw_text)
    return [AIInterpretation(**item) for item in data]
