from copy import deepcopy
import json
from math import exp, log
from pathlib import Path
import pytest
from deaths_warrant.prognosis import FEATURES, load_model, predict_prognosis, validate_model, validate_profile

FIXTURES = Path(__file__).parent / "fixtures" / "prognosis"

@pytest.fixture
# Load the patient profile shared with browser validation tests.
def profile():
    return json.loads((FIXTURES / "patient-profile.json").read_text())

@pytest.fixture
# Build an exponential special-case model with a known ten-year mean for analytic checks.
def model():
    return {
        "schemaVersion": 1, "modelVersion": "fictional-analytic-example", "status": "experimental",
        "features": list(FEATURES), "ageRange": [40, 79], "ageReference": 60,
        "parameters": {"coefficients": [log(10), 0, 0, 0], "shape": 1}, "bootstrapSamples": []
    }

# Ensure Python accepts the same patient input fixture used by the browser.
def test_shared_browser_python_profile(profile):
    assert validate_profile(profile) == profile

# Check analytic survival, mean lifetime and research limitations for an exponential model.
def test_exact_exponential_special_case(profile, model):
    result = predict_prognosis(profile, model, research_mode = True)
    assert result["remainingYears"] == pytest.approx(10)
    assert result["survivalByYear"]["5"] == pytest.approx(exp(-0.5))
    assert result["meanUncertainty"] is None
    assert result["clinicallyValidated"] is False
    assert result["supportsTreatmentEffects"] is False
    assert result["supportsConditionAttribution"] is False
    assert result["warnings"]
    json.dumps(result, allow_nan = False)

# Check age and prior-event coefficients multiply the predicted lifetime scale as expected.
def test_age_and_history_change_log_scale_correctly(profile, model):
    model["parameters"]["coefficients"] = [log(10), -log(2), -log(2), -log(2)]
    assert predict_prognosis(profile, model, True)["remainingYears"] == pytest.approx(5)
    older = dict(profile, ageYears = 70)
    assert predict_prognosis(older, model, True)["remainingYears"] == pytest.approx(2.5)
    assert predict_prognosis(dict(older, previousStroke = True), model, True)["remainingYears"] == pytest.approx(1.25)

# Check the mean includes the Weibull shape correction rather than just its scale.
def test_weibull_mean_uses_shape(profile, model):
    model["parameters"]["shape"] = 2
    assert predict_prognosis(profile, model, True)["remainingYears"] == pytest.approx(8.86226925452758)

# Check interpolated bootstrap bounds and their population-mean interpretation.
def test_bootstrap_interval_is_for_mean_not_individual_lifetime(profile, model):
    model["bootstrapSamples"] = [{"coefficients": [log(value), 0, 0, 0], "shape": 1} for value in range(1, 41)]
    interval = predict_prognosis(profile, model, True)["meanUncertainty"]
    assert interval["lower"] == pytest.approx(1.975)
    assert interval["upper"] == pytest.approx(39.025)
    assert interval["samples"] == 40
    assert "not an individual's" in interval["meaning"]

# Ensure only an explicit true research flag enables prognosis calculations.
def test_research_opt_in_is_required(profile, model):
    for mode in [False, None, 1, "true"]:
        with pytest.raises(ValueError, match = "research_mode"):
            predict_prognosis(profile, model, mode)

@pytest.mark.parametrize("age", [None, True, 39, 80, 60.5, float("nan"), float("inf"), "60"])
# Ensure unknown, noninteger and out-of-range ages cannot enter the model.
def test_rejects_unsupported_ages(profile, age):
    with pytest.raises(ValueError):
        validate_profile(dict(profile, ageYears = age))

@pytest.mark.parametrize("field", ["heartFailure", "previousHeartAttack", "previousStroke"])
@pytest.mark.parametrize("value", [None, 0, 1, "false"])
# Ensure history inputs require explicit booleans rather than coercible values.
def test_rejects_missing_or_ambiguous_histories(profile, field, value):
    with pytest.raises(ValueError):
        validate_profile(dict(profile, **{field: value}))

@pytest.mark.parametrize("as_of", ["2025-02-29", "20260101", "2026-1-01", None, "2026-01-01T00:00:00Z"])
# Ensure assessment dates are complete valid calendar dates without time components.
def test_rejects_bad_dates(profile, as_of):
    with pytest.raises(ValueError):
        validate_profile(dict(profile, asOf = as_of))

# Ensure profiles require heart failure and contain no unsupported extra inputs.
def test_rejects_absent_heart_failure_and_unexpected_fields(profile):
    with pytest.raises(ValueError):
        validate_profile(dict(profile, heartFailure = False))
    with pytest.raises(ValueError):
        validate_profile(dict(profile, treatment = "cured"))

@pytest.mark.parametrize("parameters", [
    {"coefficients": [0, 0, 0, 0], "shape": 0},
    {"coefficients": [0, 0, 0, 0], "shape": float("nan")},
    {"coefficients": [0, 0, 0, float("inf")], "shape": 1},
    {"coefficients": [0, 0, 0], "shape": 1},
    {"coefficients": [True, 0, 0, 0], "shape": 1}
])
# Ensure invalid shapes, coefficient counts and nonfinite values fail model validation.
def test_rejects_corrupt_parameters(model, parameters):
    model["parameters"] = parameters
    with pytest.raises(ValueError):
        validate_model(model)

# Ensure reordered features and overflowing predictions fail instead of yielding misleading results.
def test_rejects_overflow_and_feature_order_changes(profile, model):
    broken = deepcopy(model)
    broken["features"] = list(reversed(FEATURES))
    with pytest.raises(ValueError):
        predict_prognosis(profile, broken, True)
    model["parameters"]["coefficients"][0] = 1000
    with pytest.raises(ValueError, match = "numerical"):
        predict_prognosis(profile, model, True)

# Ensure a boolean cannot masquerade as integer model schema version one.
def test_rejects_boolean_schema_version(model):
    model["schemaVersion"] = True
    with pytest.raises(ValueError):
        validate_model(model)

# Check missing and malformed model files fail while valid JSON reloads unchanged.
def test_model_file_errors_and_round_trip(tmp_path, model):
    path = tmp_path / "model.json"
    with pytest.raises(ValueError, match = "Could not read"):
        load_model(path)
    path.write_text("{", encoding = "utf-8")
    with pytest.raises(ValueError, match = "Could not read"):
        load_model(path)
    path.write_text(json.dumps(model), encoding = "utf-8")
    assert load_model(path) == model
