"""Pydantic data contracts for the ARES Integration Evidence Checker.

Three layers are kept deliberately separate:
- Scenario / ExchangedVariable: schema for authoritative model inputs and the
  metadata attached to variables exchanged across model boundaries.
- ValidationFinding: deterministic output of src/validation.py. Claude never
  writes to this model.
- AIInterpretation: Claude's output, kept as a distinct model so an LLM
  response can never overwrite a deterministic verdict.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "scenarios.json"


class SolisData(BaseModel):
    solar_capacity_mw: float
    battery_capacity_mw: float
    operating_reserve_pct: float


class TharsisData(BaseModel):
    peak_demand_mw: float
    critical_load_served_pct: float
    unmet_demand_mwh: float


class MeridianData(BaseModel):
    required_critical_service_pct: float
    stress_event: bool
    duration_hours: float


class ExchangedVariable(BaseModel):
    """Minimal interface-contract envelope for a variable exchanged between models."""

    scenario_id: str
    variable_name: str
    value: float
    unit: str
    source_model: str
    source_version: str
    time_resolution: str
    assumption_id: Optional[str] = None
    confidence: Optional[str] = None


class Scenario(BaseModel):
    scenario_id: str
    label: str
    solis: SolisData
    tharsis: TharsisData
    meridian: MeridianData
    exchanged_variables: List[ExchangedVariable] = Field(default_factory=list)


class ValidationFinding(BaseModel):
    """Deterministic scientific/interface validation result. AI must never populate this."""

    id: str
    variable: str
    status: Literal["PASS", "FAIL", "WARNING", "BLOCKED"]
    severity: Literal["NONE", "LOW", "MEDIUM", "HIGH"]
    evidence: str
    source_models: List[str]
    owner: str
    details: Dict[str, Any] = Field(default_factory=dict)


class AIInterpretation(BaseModel):
    """Claude's board-level interpretation of one ValidationFinding. Never a verdict."""

    finding_id: str
    why_it_matters: str
    recommended_investigation: str
    evidence_gap: str
    limitation: str


def load_raw_scenarios() -> List[Dict[str, Any]]:
    """Data loading/parsing layer. May raise OSError / json.JSONDecodeError."""
    with DATA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def list_scenario_options() -> List[Dict[str, str]]:
    raw = load_raw_scenarios()
    return [{"scenario_id": s["scenario_id"], "label": s.get("label", s["scenario_id"])} for s in raw]


def get_scenario(scenario_id: str) -> Scenario:
    """Loads and schema-validates one scenario.

    Raises pydantic.ValidationError if the stored data does not match the
    Scenario schema. Callers must catch that separately from scientific
    validation errors, which never occur in src/validation.py because it only
    ever receives an already schema-valid Scenario.
    """
    raw = load_raw_scenarios()
    match = next((s for s in raw if s.get("scenario_id") == scenario_id), None)
    if match is None:
        raise ValueError(f"Unknown scenario_id: {scenario_id}")
    return Scenario(**match)
