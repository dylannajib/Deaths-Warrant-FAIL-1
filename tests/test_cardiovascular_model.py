from copy import deepcopy; from math import exp, log
from pathlib import Path
import importlib.util; import json; import sys
import numpy as np; import pandas as pd; import pytest
from deaths_warrant.cardiovascular_prognosis import FEATURES, MODEL_VERSION, load_model, model_fingerprint, predict_prognosis, validate_model, validate_profile
from deaths_warrant.cardiovascular_training import brier_score, fit_candidate, parameters, validate_development_split

# Supply explicit supported inputs independently of the clinical-file readers.
@pytest.fixture
def profile():
    return {"asOf": "2026-01-01", "ageYears": 60, "recordedSex": 1, "heartFailure": True,
        "coronaryHeartDisease": False, "angina": False, "previousHeartAttack": False,
        "previousStroke": False, "diabetes": False, "currentSmoker": False,
        "bmi": 25, "systolicBloodPressure": 120, "creatinine": 1}

# Use an exact exponential example whose mean is ten years for every profile.
@pytest.fixture
def model():
    parameters = {"coefficients": [log(10)] + [0] * 12, "shape": 1}
    return {"schemaVersion": 1, "modelVersion": MODEL_VERSION, "status": "experimental", "features": list(FEATURES),
        "parameters": parameters, "bootstrapSamples": [deepcopy(parameters) for _ in range(30)],
        "measurementRanges": {"bmi": [15, 65], "systolicBloodPressure": [70, 220], "creatinine": [0.4, 10]}}

# Check the analytic mean, survival probabilities and identical-bootstrap interval.
def test_exact_exponential(profile, model):
    result = predict_prognosis(profile, model, research_mode = True)
    assert result["remainingYears"] == pytest.approx(10)
    assert result["survivalByYear"] == pytest.approx({"1": exp(-0.1), "3": exp(-0.3), "5": exp(-0.5)})
    assert result["meanUncertainty"]["lower"] == pytest.approx(10)
    assert result["meanUncertainty"]["upper"] == pytest.approx(10)
    assert result["clinicallyValidated"] is False
    assert result["supportsConditionAttribution"] is False

# Ensure broad cardiovascular histories do not still require heart failure specifically.
def test_coronary_only_profile(profile, model):
    profile.update(heartFailure = False, coronaryHeartDisease = True)
    assert predict_prognosis(profile, model, research_mode = True)["remainingYears"] == pytest.approx(10)

# Reject missing, non-finite, incorrectly typed and unsupported profile values.
@pytest.mark.parametrize("name,value", [("ageYears", True), ("ageYears", 80), ("ageYears", 40.5),
    ("recordedSex", "male"), ("recordedSex", True), ("heartFailure", 1), ("diabetes", None),
    ("bmi", float("nan")), ("bmi", 10**1000), ("creatinine", float("inf")), ("systolicBloodPressure", -1),
    ("asOf", "2026-02-30"), ("asOf", "20260101")])
def test_invalid_profile(profile, name, value):
    profile[name] = value
    with pytest.raises(ValueError):
        validate_profile(profile)

# Prevent defaults from turning absent histories into negative answers.
def test_missing_and_extra_fields(profile):
    with pytest.raises(ValueError):
        validate_profile(dict(profile, unknown = True))
    profile.pop("diabetes")
    with pytest.raises(ValueError):
        validate_profile(profile)

# Require at least one of the five histories used to define the training population.
def test_no_cardiovascular_history(profile):
    profile["heartFailure"] = False
    with pytest.raises(ValueError, match = "history"):
        validate_profile(profile)

# Keep research acknowledgement and measured training support mandatory.
def test_research_and_range_guards(profile, model):
    with pytest.raises(ValueError, match = "research_mode"):
        predict_prognosis(profile, model)
    profile["creatinine"] = 11
    with pytest.raises(ValueError, match = "training measurement range"):
        predict_prognosis(profile, model, research_mode = True)

# Reject malformed artifacts before coefficients are used in prediction.
@pytest.mark.parametrize("change", ["version", "coefficients", "shape", "samples", "range", "feature_order"])
def test_invalid_model(model, change):
    if change == "version": model["schemaVersion"] = True
    if change == "coefficients": model["parameters"]["coefficients"].pop()
    if change == "shape": model["parameters"]["shape"] = 0
    if change == "samples": model["bootstrapSamples"] = []
    if change == "range": model["measurementRanges"]["bmi"] = [65, 15]
    if change == "feature_order": model["features"] = list(reversed(FEATURES))
    with pytest.raises(ValueError):
        validate_model(model)

# Convert extreme fitted values to a readable error instead of infinity or a traceback.
def test_prediction_overflow(profile, model):
    model["parameters"]["coefficients"][0] = 1000
    with pytest.raises(ValueError, match = "numerical"):
        predict_prognosis(profile, model, research_mode = True)

# Verify canonical hashes ignore dictionary order but detect changed coefficients.
def test_model_fingerprint(model):
    assert model_fingerprint(model) == model_fingerprint(dict(reversed(list(model.items()))))
    changed = deepcopy(model); changed["parameters"]["coefficients"][0] += 0.1
    assert model_fingerprint(model) != model_fingerprint(changed)

# Reduce IPCW error to ordinary squared error when everyone has an observed outcome.
def test_brier_without_censoring():
    training = pd.DataFrame({"follow_up_years": [2, 7, 8], "death": [1, 1, 0]})
    checking = pd.DataFrame({"follow_up_years": [1, 6], "death": [1, 0]})
    assert brier_score(training, checking, [0.2, 0.8], 5) == pytest.approx(0.04)

# Give early-censored participants zero contribution and compensate through censoring weights.
def test_brier_with_early_censoring():
    training = pd.DataFrame({"follow_up_years": [1, 3, 8, 9], "death": [0, 1, 1, 0]})
    checking = pd.DataFrame({"follow_up_years": [1, 3, 8, 9], "death": [0, 1, 1, 0]})
    # G(3-)=G(5)=3/4; contributions 0, 1/3, 1/3, 1/3 divided by four.
    assert brier_score(training, checking, [0.5] * 4, 5) == pytest.approx(0.25)

# Use censoring survival before a tied death rather than after the tied censoring.
def test_brier_tied_death_and_censor():
    table = pd.DataFrame({"follow_up_years": [2, 2, 8, 9], "death": [1, 0, 1, 0]})
    # G(2-)=1; G(5)=3/4; one death and two survivors contribute.
    assert brier_score(table, table, [0.5] * 4, 5) == pytest.approx((0.25 + 2 * 0.25 / 0.75) / 4)

# Never report a horizon after all training censoring support has ended.
def test_brier_no_censoring_support():
    table = pd.DataFrame({"follow_up_years": [1, 2], "death": [0, 0]})
    with pytest.raises(ValueError, match = "support"):
        brier_score(table, table, [0.5, 0.5], 5)

# Build varied reproducible synthetic records without depending on ignored NHANES files.
def synthetic_table(profile):
    random = np.random.default_rng(42)
    table = pd.DataFrame([profile] * 160).drop(columns = "asOf")
    table["ageYears"] = random.integers(40, 80, len(table))
    table["recordedSex"] = random.integers(1, 3, len(table))
    for name in ["coronaryHeartDisease", "angina", "previousHeartAttack", "previousStroke", "diabetes", "currentSmoker"]:
        table[name] = random.integers(0, 2, len(table))
    for name, low, high in [("bmi", 20, 40), ("systolicBloodPressure", 100, 180), ("creatinine", 0.6, 2)]:
        table[name] = random.uniform(low, high, len(table))
    # Vary heart failure without removing every qualifying history.
    table.loc[table["coronaryHeartDisease"].eq(1), "heartFailure"] = False
    table["follow_up_years"] = random.weibull(1.5, len(table)) * 8 + 0.1
    table["death"] = random.integers(0, 2, len(table))
    table["examWeight2yr"] = 1.0; table["seqn"] = np.arange(1, len(table) + 1); table["cycle"] = "2011-2012"
    return table

# Compare exported standard-library predictions with lifelines on a genuinely fitted model.
def test_exported_prediction_parity(profile, model):
    table = synthetic_table(profile)
    fitter = fit_candidate(table)
    model["parameters"] = parameters(fitter)
    model["bootstrapSamples"] = [deepcopy(model["parameters"]) for _ in range(30)]
    result = predict_prognosis(profile, model, research_mode = True)
    inputs = pd.DataFrame([profile])
    assert result["remainingYears"] == pytest.approx(float(fitter.predict_expectation(inputs).iloc[0]))
    for year in [1, 3, 5]:
        assert result["survivalByYear"][str(year)] == pytest.approx(float(fitter.predict_survival_function(inputs, times = [year]).iloc[0, 0]))

# Keep overlapping participants and the reserved final cycle out of development.
def test_development_separation(profile):
    table = synthetic_table(profile)
    with pytest.raises(ValueError, match = "distinct"):
        validate_development_split(table, table)
    checking = table.copy(); checking["seqn"] += 1000; checking["cycle"] = "2009-2010"
    with pytest.raises(ValueError, match = "Reserved"):
        validate_development_split(table, checking)

# Load the committed broad artifact without requiring local patient-level data.
def test_saved_model_if_present(profile):
    path = Path("models/cardiovascular/model.json")
    if not path.exists(): pytest.skip("Broad artifact has not yet been generated")
    result = predict_prognosis(profile, load_model(path), research_mode = True)
    assert result["remainingYears"] > 0
    assert 0 <= result["survivalByYear"]["5"] <= result["survivalByYear"]["1"] <= 1

# Verify both clinical readers' shared output also satisfies the Python inference contract.
def test_shared_clinical_profile(model):
    profile = json.loads(Path("tests/fixtures/cardiovascular/patient-profile.json").read_text())
    assert validate_profile(profile) == profile
    assert predict_prognosis(profile, model, research_mode = True)["remainingYears"] == pytest.approx(10)

# Simulate interrupted final access and prove development cannot then replace the candidate.
def test_final_access_locks_candidate_before_reading_reserved_data(tmp_path, monkeypatch, profile, model):
    spec = importlib.util.spec_from_file_location("cardiovascular_script", "scripts/cardiovascular_model.py")
    script = importlib.util.module_from_spec(spec); spec.loader.exec_module(script)
    training = synthetic_table(profile)
    validation = training.copy(); validation["seqn"] += 1000
    for name, table in [("training", training), ("validation", validation)]:
        table.to_csv(tmp_path / (name + ".csv"), index = False)
    freeze = {"modelFingerprint": model_fingerprint(model), "protocol": script.PROTOCOL,
        "preparedDataHashes": {name: script.file_hash(tmp_path / (name + ".csv")) for name in ["training", "validation"]}}
    (tmp_path / "freeze.json").write_text(json.dumps(freeze))
    monkeypatch.setattr(script, "fit_candidate", lambda table: object())
    monkeypatch.setattr(script, "load_model", lambda path: model)
    monkeypatch.setattr(script, "parameters", lambda fitter: model["parameters"])
    # Reserved access must see the durable marker even when downloading fails.
    def interrupted_access(data_dir):
        assert json.loads((tmp_path / "final_started.json").read_text()) == freeze
        raise OSError("Simulated interrupted final download")
    monkeypatch.setattr(script, "prepare_final", interrupted_access)
    arguments = ["cardiovascular_model.py", "--prepared-dir", str(tmp_path), "--output-dir", str(tmp_path)]
    monkeypatch.setattr(sys, "argv", arguments + ["--final-check"])
    with pytest.raises(SystemExit): script.main()
    assert (tmp_path / "final_started.json").exists()
    assert not (tmp_path / ".run.lock").exists()
    monkeypatch.setattr(sys, "argv", arguments)
    with pytest.raises(SystemExit): script.main()
    assert json.loads((tmp_path / "freeze.json").read_text()) == freeze
    assert not (tmp_path / "model.json").exists()

# Refuse a concurrent assessment without deleting the other process's lock.
def test_existing_run_lock_is_retained(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("cardiovascular_script", "scripts/cardiovascular_model.py")
    script = importlib.util.module_from_spec(spec); spec.loader.exec_module(script)
    lock = tmp_path / ".run.lock"; lock.write_text("existing run")
    monkeypatch.setattr(sys, "argv", ["cardiovascular_model.py", "--output-dir", str(tmp_path)])
    with pytest.raises(SystemExit): script.main()
    assert lock.read_text() == "existing run"
