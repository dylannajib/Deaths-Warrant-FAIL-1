"""Small, browser-compatible inference engine for an experimental heart-failure model."""

from datetime import date; import json
from math import exp, isfinite, lgamma, log
from pathlib import Path

FEATURES = ["age_decades_from_60", "previousHeartAttack", "previousStroke"]
WARNINGS = [
    "Unvalidated research estimate; not suitable for clinical decisions or end-of-life planning.",
    "Lifetime estimates extrapolate beyond observed follow-up and depend on the assumed Weibull model.",
    "Based on historical NHANES heart-failure reports, not a confirmed current severity or treatment assessment.",
    "Unweighted exploratory analysis; survey-design uncertainty is not calculated.",
    "Does not estimate treatment effects or years attributable to individual conditions."
]

# Reject booleans and nonfinite values before converting a numeric field to float.
def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(name + " must be a finite number")
    return float(value)

# Require the supported assessment date, age range and explicit heart-failure histories.
def validate_profile(profile):
    if not isinstance(profile, dict):
        raise ValueError("Patient profile must be an object")
    expected = {"asOf", "ageYears", "heartFailure", "previousHeartAttack", "previousStroke"}
    if set(profile) != expected:
        raise ValueError("Patient profile must contain exactly the supported assessment, age and history fields")
    as_of = profile["asOf"]
    if not isinstance(as_of, str):
        raise ValueError("Assessment date must be a complete YYYY-MM-DD date")
    try:
        if date.fromisoformat(as_of).isoformat() != as_of:
            raise ValueError()
    except ValueError:
        raise ValueError("Assessment date must be a valid YYYY-MM-DD date") from None
    age = _number(profile["ageYears"], "Age")
    if not age.is_integer() or not 40 <= age <= 79:
        raise ValueError("The research model requires an age from 40 to 79 years")
    if profile["heartFailure"] is not True:
        raise ValueError("The research model requires documented heart-failure history")
    for field in ["previousHeartAttack", "previousStroke"]:
        if not isinstance(profile[field], bool):
            raise ValueError(field + " requires an explicit boolean history; missing does not mean no")
    return dict(profile, ageYears = int(age))

# Require four finite coefficients and a positive finite Weibull shape.
def _validate_parameters(parameters):
    if not isinstance(parameters, dict) or set(parameters) != {"coefficients", "shape"}:
        raise ValueError("Model parameters must contain coefficients and shape")
    coefficients = parameters["coefficients"]
    if not isinstance(coefficients, list) or len(coefficients) != 4:
        raise ValueError("Model requires an intercept and three coefficients")
    for value in coefficients:
        _number(value, "Model coefficient")
    if _number(parameters["shape"], "Weibull shape") <= 0:
        raise ValueError("Weibull shape must be positive")

# Check the experimental model schema, feature order and all saved parameter sets.
def validate_model(model):
    if not isinstance(model, dict) or type(model.get("schemaVersion")) is not int or model["schemaVersion"] != 1:
        raise ValueError("Unsupported prognosis model schema")
    if model.get("status") != "experimental" or model.get("features") != FEATURES:
        raise ValueError("Unsupported prognosis model status or features")
    if not isinstance(model.get("modelVersion"), str) or not model["modelVersion"].strip():
        raise ValueError("Model version is required")
    if model.get("ageRange") != [40, 79] or model.get("ageReference") != 60:
        raise ValueError("Unsupported model age limits or reference")
    _validate_parameters(model.get("parameters"))
    samples = model.get("bootstrapSamples")
    if not isinstance(samples, list):
        raise ValueError("Model bootstrap samples must be a list")
    for sample in samples:
        _validate_parameters(sample)
    return model

# Read model JSON and reject unreadable files or unsupported model contents.
def load_model(path):
    try:
        model = json.loads(Path(path).read_text(encoding = "utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError("Could not read prognosis model: " + str(error)) from error
    return validate_model(model)

# Calculate Weibull mean remaining years and fixed-horizon survival from age and histories.
def _estimate(profile, parameters):
    values = [1, (profile["ageYears"] - 60) / 10, int(profile["previousHeartAttack"]), int(profile["previousStroke"])]
    log_scale = sum(coefficient * value for coefficient, value in zip(parameters["coefficients"], values))
    shape = parameters["shape"]
    try:
        mean = exp(log_scale + lgamma(1 + 1 / shape))
        survival = {}
        for year in [1, 3, 5]:
            log_hazard = shape * (log(year) - log_scale)
            survival[str(year)] = 0.0 if log_hazard > 709 else exp(-exp(log_hazard))
    except (OverflowError, ValueError, ZeroDivisionError):
        raise ValueError("Model produced an unsupported numerical estimate") from None
    if not isfinite(mean) or mean <= 0:
        raise ValueError("Model produced an unsupported remaining-years estimate")
    return mean, survival

# Interpolate between adjacent sorted samples at the requested quantile.
def _percentile(values, fraction):
    position = (len(values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)

# Return research-only Weibull estimates and optional bootstrap uncertainty for the mean.
def predict_prognosis(profile, model, research_mode = False):
    if research_mode is not True:
        raise ValueError("This unvalidated model can only run with research_mode=True")
    profile = validate_profile(profile)
    validate_model(model)
    mean, survival = _estimate(profile, model["parameters"])
    uncertainty = None
    if len(model["bootstrapSamples"]) >= 30:
        means = sorted(_estimate(profile, sample)[0] for sample in model["bootstrapSamples"])
        uncertainty = {
            "lower": _percentile(means, 0.025), "upper": _percentile(means, 0.975), "level": 0.95,
            "method": "ordinary_bootstrap_percentile", "samples": len(means),
            "meaning": "Uncertainty in the fitted mean under this model; not an individual's remaining-life range. Does not cover survey design or extrapolation assumptions."
        }
    return {
        "modelVersion": model["modelVersion"], "status": "experimental", "clinicallyValidated": False,
        "asOf": profile["asOf"], "remainingYears": mean, "survivalByYear": survival,
        "meanUncertainty": uncertainty, "supportsTreatmentEffects": False, "supportsConditionAttribution": False,
        "warnings": list(WARNINGS)
    }
