import pytest
from pydantic import ValidationError

from src.models import Scenario, get_scenario
from src.validation import check_capacity_envelope, check_critical_service_level, run_checks


def _find(findings, finding_id):
    return next(f for f in findings if f.id == finding_id)


def test_normal_scenario_passes_capacity_and_service_checks():
    scenario = get_scenario("normal_operations")
    findings = run_checks(scenario)
    assert _find(findings, "capacity_envelope").status == "PASS"
    assert _find(findings, "critical_service_level").status == "PASS"
    assert _find(findings, "unit_compatibility").status == "PASS"


def test_dust_storm_capacity_check_blocked_by_unit_mismatch():
    scenario = get_scenario("dust_storm_72h")
    findings = run_checks(scenario)
    capacity = _find(findings, "capacity_envelope")
    assert capacity.status == "BLOCKED"
    assert capacity.severity == "HIGH"
    assert "difference_mw" not in capacity.details
    assert capacity.details["reported_unit"] == "kW"


def test_capacity_check_fails_once_unit_is_corrected():
    scenario = get_scenario("dust_storm_72h")
    corrected = scenario.model_copy(deep=True)
    corrected.exchanged_variables[0].unit = "MW"
    result = check_capacity_envelope(corrected)
    assert result.status == "FAIL"
    assert result.severity == "HIGH"
    assert result.details["difference_mw"] == pytest.approx(2.6)


def test_dust_storm_flags_interface_unit_mismatch():
    scenario = get_scenario("dust_storm_72h")
    findings = run_checks(scenario)
    unit_finding = _find(findings, "unit_compatibility")
    assert unit_finding.status == "WARNING"
    assert unit_finding.details["reported_unit"] == "kW"


def test_critical_service_requirement_boundary():
    scenario = get_scenario("normal_operations")

    passing = scenario.model_copy(deep=True)
    passing.tharsis.critical_load_served_pct = passing.meridian.required_critical_service_pct
    assert check_critical_service_level(passing).status == "PASS"

    failing = scenario.model_copy(deep=True)
    failing.tharsis.critical_load_served_pct = failing.meridian.required_critical_service_pct - 0.1
    assert check_critical_service_level(failing).status == "FAIL"


def test_malformed_scenario_raises_validation_error_before_scientific_checks():
    bad_data = {
        "scenario_id": "broken",
        "label": "Broken",
        "solis": {"solar_capacity_mw": 10, "battery_capacity_mw": 5},  # missing operating_reserve_pct
        "tharsis": {"peak_demand_mw": 10, "critical_load_served_pct": 90, "unmet_demand_mwh": 0},
        "meridian": {"required_critical_service_pct": 90, "stress_event": False, "duration_hours": 0},
        "exchanged_variables": [],
    }
    with pytest.raises(ValidationError):
        Scenario(**bad_data)
