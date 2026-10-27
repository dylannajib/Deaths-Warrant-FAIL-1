"""Offline research data preparation and fitting; never imported by browser inference."""

from math import exp, isfinite; import warnings
import numpy as np; import pandas as pd
from lifelines import WeibullAFTFitter, WeibullFitter
from lifelines.exceptions import ConvergenceError, ConvergenceWarning
from lifelines.utils import concordance_index
from deaths_warrant.nhanes import load_demo, load_lmf
from deaths_warrant.prognosis import FEATURES, predict_prognosis, validate_model

MODEL_VERSION = "nhanes-hf-weibull-0.1.0"
FORMULA = "age_decades_from_60 + previousHeartAttack + previousStroke"
PENALIZER = 0.01

def prepare_cycle(medical_path, demo_path, mortality_path, cycle):
    medical = pd.read_sas(medical_path, format = "xport").rename(columns = {"SEQN": "seqn"})
    required = ["seqn", "MCQ160B", "MCQ160E", "MCQ160F"]
    if not set(required).issubset(medical.columns):
        raise ValueError("Questionnaire is missing required heart-failure history columns")
    medical = medical[required].copy()
    medical["seqn"] = medical["seqn"].astype(int)
    demo = load_demo(demo_path)
    mortality = load_lmf(mortality_path)
    merged = medical.merge(demo, on = "seqn", how = "left", validate = "one_to_one", indicator = True)
    if not merged["_merge"].eq("both").all():
        raise ValueError("Some questionnaire participants lack demographics")
    merged = merged.drop(columns = "_merge").merge(mortality, on = "seqn", how = "left", validate = "one_to_one", indicator = True)
    if not merged["_merge"].eq("both").all():
        raise ValueError("Some questionnaire participants lack a mortality-linkage record")
    heart_failure = merged[merged["MCQ160B"] == 1]
    eligible = heart_failure[(heart_failure["eligstat"] == 1) & heart_failure["age_years"].between(40, 79)].copy()
    # 7 (refused), 9 (unknown) and missing responses are never converted to no.
    eligible["previousHeartAttack"] = eligible["MCQ160E"].map({1: 1, 2: 0})
    eligible["previousStroke"] = eligible["MCQ160F"].map({1: 1, 2: 0})
    complete = eligible.dropna(subset = ["previousHeartAttack", "previousStroke"]).copy()
    if not complete["mortstat"].isin([0, 1]).all():
        raise ValueError("Eligible participants must have binary mortality status")
    if not complete["permth_int"].map(lambda value: isfinite(value) and value > 0).all():
        raise ValueError("Eligible participants must have finite positive follow-up")
    if not complete["age_years"].map(lambda value: isfinite(value) and float(value).is_integer()).all():
        raise ValueError("Participant ages must be finite integers")
    table = pd.DataFrame({
        "ageYears": complete["age_years"].astype(int),
        "age_decades_from_60": (complete["age_years"] - 60) / 10,
        "previousHeartAttack": complete["previousHeartAttack"].astype(int),
        "previousStroke": complete["previousStroke"].astype(int),
        "follow_up_years": complete["permth_int"] / 12,
        "death": complete["mortstat"].astype(int)
    }).reset_index(drop = True)
    report = {
        "cycle": cycle, "questionnaireParticipants": len(medical), "heartFailureReports": len(heart_failure),
        "eligibleAge40To79": len(eligible), "excludedUnknownHistory": len(eligible) - len(complete),
        "modelParticipants": len(table), "deaths": int(table["death"].sum())
    }
    return table, report

def fit_parameters(table):
    if len(table) == 0 or table["death"].sum() == 0:
        raise ValueError("Fitting requires participants and observed deaths")
    model = WeibullAFTFitter(penalizer = PENALIZER)
    model.fit(table, duration_col = "follow_up_years", event_col = "death", formula = FORMULA)
    parameters = {
        "coefficients": [float(model.params_.loc[("lambda_", name)]) for name in ["Intercept"] + FEATURES],
        "shape": exp(float(model.params_.loc[("rho_", "Intercept")]))
    }
    return parameters

def fit_research_model(table, bootstrap_samples = 100, seed = 20261027):
    if not isinstance(bootstrap_samples, int) or isinstance(bootstrap_samples, bool) or bootstrap_samples < 30:
        raise ValueError("At least 30 bootstrap fits are required")
    model = {
        "schemaVersion": 1, "modelVersion": MODEL_VERSION, "status": "experimental",
        "features": list(FEATURES), "ageRange": [40, 79], "ageReference": 60,
        "parameters": fit_parameters(table), "bootstrapSamples": [],
        "training": {"participants": len(table), "deaths": int(table["death"].sum()),
            "penalizer": PENALIZER, "weighted": False, "seed": seed, "bootstrapRequested": bootstrap_samples}
    }
    random = np.random.default_rng(seed)
    for _ in range(bootstrap_samples):
        sample = table.iloc[random.integers(0, len(table), len(table))].reset_index(drop = True)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", ConvergenceWarning)
                parameters = fit_parameters(sample)
            candidate = dict(model, parameters = parameters, bootstrapSamples = [])
            validate_model(candidate)
            # Reject numerical overflow even at the supported age/history boundaries.
            for age in [40, 79]:
                for attack in [False, True]:
                    for stroke in [False, True]:
                        predict_prognosis({"asOf": "2026-01-01", "ageYears": age, "heartFailure": True,
                            "previousHeartAttack": attack, "previousStroke": stroke}, candidate, research_mode = True)
            model["bootstrapSamples"].append(parameters)
        except (ConvergenceError, ConvergenceWarning, ValueError, ArithmeticError):
            continue
    successful = len(model["bootstrapSamples"])
    if successful < max(30, bootstrap_samples * 0.9):
        raise ValueError("Too many bootstrap fits failed; do not publish this research model")
    model["training"]["bootstrapSuccessful"] = successful
    return validate_model(model)

def evaluate_model(model, training, checking):
    if checking.empty or training.empty:
        raise ValueError("Model checks require nonempty training and checking samples")
    if ((checking["death"] == 0) & (checking["follow_up_years"] < 5)).any():
        raise ValueError("Five-year Brier checks require complete five-year outcomes")
    bare_model = dict(model, bootstrapSamples = [])
    predictions = []
    means = []
    for row in checking.itertuples(index = False):
        result = predict_prognosis({"asOf": "2026-01-01", "ageYears": int(row.ageYears), "heartFailure": True,
            "previousHeartAttack": bool(row.previousHeartAttack), "previousStroke": bool(row.previousStroke)}, bare_model, research_mode = True)
        predictions.append(result["survivalByYear"]["5"])
        means.append(result["remainingYears"])
    actual = 1 - ((checking["death"] == 1) & (checking["follow_up_years"] <= 5)).astype(int).to_numpy()
    baseline = WeibullFitter().fit(training["follow_up_years"], event_observed = training["death"])
    baseline_prediction = float(baseline.survival_function_at_times([5]).iloc[0])
    return {
        "participants": len(checking), "deathsByFiveYears": int((1 - actual).sum()),
        "meanPredictedFiveYearSurvival": float(np.mean(predictions)), "observedFiveYearSurvival": float(actual.mean()),
        "brier": float(np.mean((np.array(predictions) - actual) ** 2)),
        "baselineBrier": float(np.mean((baseline_prediction - actual) ** 2)),
        "concordance": float(concordance_index(checking["follow_up_years"], means, checking["death"])),
        "assessment": "Development comparison only; not independent clinical or lifetime validation."
    }
