from copy import deepcopy
import json
from pathlib import Path
import pytest
from deaths_warrant.prognosis_training import assess_feasibility, model_fingerprint

MODELS = Path(__file__).resolve().parents[1] / "models" / "heart_failure"

@pytest.fixture
# Load the saved heart-failure candidate and its evaluation report for feasibility checks.
def artifacts():
    model = json.loads((MODELS / "model.json").read_text())
    report = json.loads((MODELS / "evaluation.json").read_text())
    return model, report

# Check the candidate records all failed evidence checks and denies patient prognosis.
def test_current_candidate_has_explicit_research_only_decision(artifacts):
    model, report = artifacts
    result = assess_feasibility(model, report)
    assert result["assessmentComplete"] is True
    assert result["patientPrognosisSupported"] is False
    assert result["decision"] == "research_only"
    assert set(result["failedChecks"]) == {"five_year_error", "survival_ranking", "independent_validation",
        "lifetime_validation", "clinical_record_validation"}

# Ensure improved development scores still require independent clinical evidence.
def test_good_development_metrics_cannot_approve_clinical_use(artifacts):
    model, report = artifacts
    report["evaluation"].update(brier = 0.1, baselineBrier = 0.2, concordance = 0.9)
    result = assess_feasibility(model, report)
    assert result["patientPrognosisSupported"] is False
    assert "five_year_error" not in result["failedChecks"]
    assert "independent_validation" in result["failedChecks"]

# Ensure feasibility evidence cannot be reused for modified parameters or another version.
def test_changed_model_or_report_version_is_rejected(artifacts):
    model, report = artifacts
    changed = deepcopy(model)
    changed["parameters"]["coefficients"][0] += 0.01
    with pytest.raises(ValueError, match = "saved model"):
        assess_feasibility(changed, report)
    report["modelVersion"] = "different"
    with pytest.raises(ValueError, match = "same model"):
        assess_feasibility(model, report)

@pytest.mark.parametrize("value", [None, "0.1", True, -0.1, 1.1, float("nan"), float("inf")])
# Ensure missing, nonnumeric or out-of-range evaluation scores reject feasibility assessment.
def test_invalid_metrics_fail_closed(artifacts, value):
    model, report = artifacts
    report["evaluation"]["brier"] = value
    with pytest.raises(ValueError, match = "metric"):
        assess_feasibility(model, report)

# Check that JSON key reordering preserves the model fingerprint.
def test_fingerprint_ignores_json_layout_not_model_contents(artifacts):
    model, _ = artifacts
    reordered = json.loads(json.dumps(model, sort_keys = True))
    assert model_fingerprint(model) == model_fingerprint(reordered)
