"""Deterministic scientific / interface validation rules.

No LLM calls happen in this module. Every function receives an already
schema-validated Scenario (see src/models.get_scenario) and returns
ValidationFinding objects. Claude is never involved in producing these
results and cannot change them.
"""

from typing import List, Optional

from src.models import ExchangedVariable, Scenario, ValidationFinding

EXPECTED_POWER_UNIT = "MW"


def _finding(
    finding_id: str,
    variable: str,
    status: str,
    severity: str,
    evidence: str,
    source_models: List[str],
    owner: str,
    details: Optional[dict] = None,
) -> ValidationFinding:
    return ValidationFinding(
        id=finding_id,
        variable=variable,
        status=status,
        severity=severity,
        evidence=evidence,
        source_models=source_models,
        owner=owner,
        details=details or {},
    )


def _get_exchanged(scenario: Scenario, variable_name: str) -> Optional[ExchangedVariable]:
    for v in scenario.exchanged_variables:
        if v.variable_name == variable_name:
            return v
    return None


def check_scenario_id_consistency(scenario: Scenario) -> ValidationFinding:
    mismatched = [
        v.variable_name for v in scenario.exchanged_variables if v.scenario_id != scenario.scenario_id
    ]
    if mismatched:
        return _finding(
            "scenario_id_consistency",
            "scenario_id",
            "FAIL",
            "HIGH",
            f"Exchanged variable(s) {mismatched} reference a different scenario_id "
            f"than the active scenario '{scenario.scenario_id}'.",
            ["Helix"],
            "Helix",
            {"mismatched_variables": mismatched},
        )
    return _finding(
        "scenario_id_consistency",
        "scenario_id",
        "PASS",
        "NONE",
        "All exchanged variables reference the active scenario_id.",
        ["Helix"],
        "Helix",
    )


def check_unit_compatibility(scenario: Scenario) -> ValidationFinding:
    ev = _get_exchanged(scenario, "available_power_mw")
    if ev is None:
        return _finding(
            "unit_compatibility",
            "available_power_mw",
            "FAIL",
            "HIGH",
            "No interface record found for available_power_mw.",
            ["Solis", "Helix"],
            "Helix",
        )
    if ev.unit != EXPECTED_POWER_UNIT:
        return _finding(
            "unit_compatibility",
            "available_power_mw",
            "WARNING",
            "MEDIUM",
            f"Solis reported available_power_mw in '{ev.unit}', but the interface "
            f"contract expects '{EXPECTED_POWER_UNIT}'. Downstream checks compared "
            "the raw numeric value without unit conversion.",
            ["Solis", "Helix"],
            "Helix",
            {"reported_unit": ev.unit, "expected_unit": EXPECTED_POWER_UNIT, "source_version": ev.source_version},
        )
    return _finding(
        "unit_compatibility",
        "available_power_mw",
        "PASS",
        "NONE",
        f"available_power_mw unit '{ev.unit}' matches the expected interface unit.",
        ["Solis", "Helix"],
        "Helix",
    )


def check_capacity_envelope(scenario: Scenario) -> ValidationFinding:
    """Compares available power against peak demand.

    This check depends on available_power_mw's interface contract being
    valid. If the unit does not match the expected contract, the numeric
    value is untrusted for this comparison: it is not converted or assumed
    correct, and the check returns BLOCKED instead of PASS/FAIL.
    """
    ev = _get_exchanged(scenario, "available_power_mw")
    demand = scenario.tharsis.peak_demand_mw
    if ev is None:
        return _finding(
            "capacity_envelope",
            "available_power_mw",
            "FAIL",
            "HIGH",
            "No available_power_mw value to compare against peak demand.",
            ["Solis", "Tharsis"],
            "Solis + Tharsis",
        )
    if ev.unit != EXPECTED_POWER_UNIT:
        return _finding(
            "capacity_envelope",
            "available_power_mw",
            "BLOCKED",
            "HIGH",
            f"Capacity comparison cannot be established: available_power_mw was reported "
            f"in '{ev.unit}', not the expected '{EXPECTED_POWER_UNIT}'. The value is "
            "untrusted for this comparison until the upstream interface discrepancy is "
            "resolved. The reported value has not been converted or assumed correct, "
            "since it is unknown whether the unit label or the numeric value is wrong.",
            ["Solis", "Helix"],
            "Solis + Helix",
            {"reported_unit": ev.unit, "expected_unit": EXPECTED_POWER_UNIT, "peak_demand_mw": demand},
        )
    available = ev.value
    if available < demand:
        diff = round(demand - available, 2)
        return _finding(
            "capacity_envelope",
            "available_power_mw",
            "FAIL",
            "HIGH",
            f"Available power ({available} MW) is below peak demand ({demand} MW).",
            ["Solis", "Tharsis"],
            "Solis + Tharsis",
            {"available_power_mw": available, "peak_demand_mw": demand, "difference_mw": diff},
        )
    margin = round(available - demand, 2)
    return _finding(
        "capacity_envelope",
        "available_power_mw",
        "PASS",
        "NONE",
        f"Available power ({available} MW) covers peak demand ({demand} MW).",
        ["Solis", "Tharsis"],
        "Solis + Tharsis",
        {"available_power_mw": available, "peak_demand_mw": demand, "margin_mw": margin},
    )


def check_critical_service_level(scenario: Scenario) -> ValidationFinding:
    served = scenario.tharsis.critical_load_served_pct
    required = scenario.meridian.required_critical_service_pct
    if served < required:
        return _finding(
            "critical_service_level",
            "critical_load_served_pct",
            "FAIL",
            "HIGH",
            f"Critical load served ({served}%) is below Meridian's required level ({required}%).",
            ["Tharsis", "Meridian"],
            "Tharsis + Meridian",
            {"critical_load_served_pct": served, "required_critical_service_pct": required},
        )
    return _finding(
        "critical_service_level",
        "critical_load_served_pct",
        "PASS",
        "NONE",
        f"Critical load served ({served}%) meets Meridian's required level ({required}%).",
        ["Tharsis", "Meridian"],
        "Tharsis + Meridian",
        {"critical_load_served_pct": served, "required_critical_service_pct": required},
    )


def check_stress_metadata(scenario: Scenario) -> ValidationFinding:
    m = scenario.meridian
    if m.stress_event and m.duration_hours <= 0:
        return _finding(
            "stress_metadata",
            "duration_hours",
            "FAIL",
            "HIGH",
            "stress_event is flagged but no valid stress duration was provided by Meridian.",
            ["Meridian", "Helix"],
            "Meridian + Helix",
        )
    evidence = (
        "Stress event metadata is complete and consistent."
        if m.stress_event
        else "No stress event declared for this scenario."
    )
    return _finding(
        "stress_metadata",
        "duration_hours",
        "PASS",
        "NONE",
        evidence,
        ["Meridian"],
        "Meridian + Helix",
    )


def run_checks(scenario: Scenario) -> List[ValidationFinding]:
    return [
        check_scenario_id_consistency(scenario),
        check_unit_compatibility(scenario),
        check_capacity_envelope(scenario),
        check_critical_service_level(scenario),
        check_stress_metadata(scenario),
    ]
