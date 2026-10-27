"""Standard-library inference for the broad cardiovascular research model."""

from datetime import date; from math import exp, isfinite, lgamma, log
from hashlib import sha256; from pathlib import Path; import json

HISTORIES = ["heartFailure", "coronaryHeartDisease", "angina", "previousHeartAttack", "previousStroke"]
FLAGS = HISTORIES + ["diabetes", "currentSmoker"]
MEASUREMENTS = ["bmi", "systolicBloodPressure", "creatinine"]
FEATURES = ["ageYears", "recordedSex"] + FLAGS + MEASUREMENTS
MODEL_VERSION = "nhanes-cardiovascular-weibull-0.1.0"
WARNINGS = ["Unvalidated research estimate; not suitable for clinical decisions or end-of-life planning.",
    "Mean remaining years extrapolate beyond observed follow-up using a Weibull assumption.",
    "Historical survey histories and examination measurements are not validated equivalents of clinical-record inputs.",
    "Unweighted complete-case model; selection bias and survey-design uncertainty are not resolved.",
    "Does not estimate treatment effects or years attributable to individual conditions."]

# Reject booleans, missing values and non-finite numbers before any calculation.
def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(name + " must be a finite number")
    try:
        numeric = float(value)
    except OverflowError:
        raise ValueError(name + " must be a finite number") from None
    if not isfinite(numeric):
        raise ValueError(name + " must be a finite number")
    return numeric

# Require the exact dated assessment and every supported cardiovascular input.
def validate_profile(profile):
    if not isinstance(profile, dict) or set(profile) != {"asOf", *FEATURES}:
        raise ValueError("Profile must contain exactly the assessment date and all broad cardiovascular inputs")
    try:
        if not isinstance(profile["asOf"], str) or date.fromisoformat(profile["asOf"]).isoformat() != profile["asOf"]:
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError("Assessment date must be a complete valid YYYY-MM-DD date") from None
    age = _number(profile["ageYears"], "Age")
    if not age.is_integer() or not 40 <= age <= 79:
        raise ValueError("Model requires completed age 40–79")
    if type(profile["recordedSex"]) is not int or profile["recordedSex"] not in [1, 2]:
        raise ValueError("Recorded sex requires the supported source code 1 or 2; do not infer it from gender")
    for name in FLAGS:
        if type(profile[name]) is not bool:
            raise ValueError(name + " requires explicit true or false; missing does not mean no")
    if not any(profile[name] for name in HISTORIES):
        raise ValueError("At least one supported cardiovascular history is required")
    for name in MEASUREMENTS:
        if _number(profile[name], name) <= 0:
            raise ValueError(name + " must be positive in the documented model units")
    return dict(profile, ageYears = int(age))

# Check the fixed coefficient order and positive Weibull shape in each saved fit.
def _parameters(parameters):
    if not isinstance(parameters, dict) or set(parameters) != {"coefficients", "shape"}:
        raise ValueError("Model parameters require coefficients and shape")
    coefficients = parameters["coefficients"]
    if not isinstance(coefficients, list) or len(coefficients) != len(FEATURES) + 1:
        raise ValueError("Model requires the intercept and twelve ordered coefficients")
    for value in coefficients:
        _number(value, "Coefficient")
    if _number(parameters["shape"], "Shape") <= 0:
        raise ValueError("Weibull shape must be positive")

# Reject incompatible model schemas, input ranges and bootstrap settings.
def validate_model(model):
    if not isinstance(model, dict) or type(model.get("schemaVersion")) is not int or model["schemaVersion"] != 1:
        raise ValueError("Unsupported broad cardiovascular model schema")
    if model.get("modelVersion") != MODEL_VERSION or model.get("features") != FEATURES or model.get("status") != "experimental":
        raise ValueError("Unsupported broad cardiovascular model version, features or status")
    _parameters(model.get("parameters"))
    ranges = model.get("measurementRanges")
    if not isinstance(ranges, dict) or set(ranges) != set(MEASUREMENTS):
        raise ValueError("Model requires measurement support ranges")
    for name, limits in ranges.items():
        if not isinstance(limits, list) or len(limits) != 2 or not 0 < _number(limits[0], name) < _number(limits[1], name):
            raise ValueError("Invalid model measurement range: " + name)
    samples = model.get("bootstrapSamples")
    if not isinstance(samples, list) or len(samples) < 30:
        raise ValueError("Model requires at least thirty bootstrap fits")
    for sample in samples:
        _parameters(sample)
    return model

# Calculate a Weibull mean and survival probabilities using the saved coefficient order.
def _estimate(profile, parameters):
    values = [1, profile["ageYears"], int(profile["recordedSex"] == 2)] + [int(profile[name]) for name in FLAGS] + [profile[name] for name in MEASUREMENTS]
    scale = sum(coef * value for coef, value in zip(parameters["coefficients"], values))
    shape = parameters["shape"]
    try:
        mean = exp(scale + lgamma(1 + 1 / shape))
        survival = {}
        for year in [1, 3, 5]:
            hazard = shape * (log(year) - scale)
            survival[str(year)] = 0.0 if hazard > 709 else exp(-exp(hazard))
    except (OverflowError, ValueError, ZeroDivisionError):
        raise ValueError("Model produced an unsupported numerical estimate") from None
    if not isfinite(mean) or mean <= 0:
        raise ValueError("Model produced an unsupported remaining-years estimate")
    return mean, survival

# Interpolate a percentile between sorted bootstrap estimates.
def _percentile(values, fraction):
    position = (len(values) - 1) * fraction
    lower = int(position)
    return values[lower] + (values[min(lower + 1, len(values) - 1)] - values[lower]) * (position - lower)

# Produce research-only remaining years, survival checks and uncertainty in the fitted mean.
def predict_prognosis(profile, model, research_mode = False):
    if research_mode is not True:
        raise ValueError("This unvalidated model requires research_mode=True")
    profile = validate_profile(profile)
    validate_model(model)
    for name, (low, high) in model["measurementRanges"].items():
        if not low <= profile[name] <= high:
            raise ValueError(name + " is outside the training measurement range")
    mean, survival = _estimate(profile, model["parameters"])
    means = sorted(_estimate(profile, sample)[0] for sample in model["bootstrapSamples"])
    return {"modelVersion": model["modelVersion"], "status": "experimental", "clinicallyValidated": False,
        "asOf": profile["asOf"], "remainingYears": mean, "survivalByYear": survival,
        "meanUncertainty": {"lower": _percentile(means, 0.025), "upper": _percentile(means, 0.975),
            "level": 0.95, "samples": len(means), "method": "ordinary_bootstrap_percentile",
            "meaning": "Uncertainty in the fitted mean, not an individual's remaining-life range; excludes survey design and extrapolation uncertainty."},
        "supportsTreatmentEffects": False, "supportsConditionAttribution": False, "warnings": list(WARNINGS)}

# Read a JSON model without loading training libraries or executable serialised objects.
def load_model(path):
    return validate_model(json.loads(Path(path).read_text(encoding = "utf-8")))

# Identify the exact saved model independently of JSON indentation or key order.
def model_fingerprint(model):
    validate_model(model)
    return sha256(json.dumps(model, sort_keys = True, separators = (",", ":"), allow_nan = False).encode("utf-8")).hexdigest()
