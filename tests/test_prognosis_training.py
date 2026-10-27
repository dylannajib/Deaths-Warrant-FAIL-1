from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from deaths_warrant import prognosis_training as training
from deaths_warrant.prognosis import validate_model

def test_recovers_known_simulated_effects_with_censoring():
    random = np.random.default_rng(412)
    count = 1200
    age = random.integers(40, 80, count)
    attack = random.integers(0, 2, count)
    stroke = random.integers(0, 2, count)
    scale = np.exp(2.3 - 0.3 * ((age - 60) / 10) - 0.25 * attack - 0.4 * stroke)
    lifetime = scale * random.weibull(1.4, count)
    censoring = random.uniform(3, 9, count)
    table = pd.DataFrame({"age_decades_from_60": (age - 60) / 10, "previousHeartAttack": attack,
        "previousStroke": stroke, "follow_up_years": np.minimum(lifetime, censoring), "death": (lifetime <= censoring).astype(int)})
    parameters = training.fit_parameters(table)
    assert parameters["shape"] == pytest.approx(1.4, abs = 0.15)
    assert parameters["coefficients"] == pytest.approx([2.3, -0.3, -0.25, -0.4], abs = 0.15)

@pytest.fixture
def cycle_sources(monkeypatch):
    medical = pd.DataFrame({"SEQN": [1., 2., 3., 4., 5.], "MCQ160B": [1, 1, 1, 1, 2],
        "MCQ160E": [1, 9, 2, 2, 2], "MCQ160F": [2, 2, 2, 7, 2]})
    demo = pd.DataFrame({"seqn": [1, 2, 3, 4, 5], "age_years": [60, 60, 80, 45, 50]})
    mortality = pd.DataFrame({"seqn": [1, 2, 3, 4, 5], "eligstat": [1] * 5,
        "mortstat": [1, 0, 0, 0, 0], "permth_int": [12, 60, 60, 60, 60]})
    monkeypatch.setattr(training.pd, "read_sas", lambda *args, **kwargs: medical.copy())
    monkeypatch.setattr(training, "load_demo", lambda path: demo.copy())
    monkeypatch.setattr(training, "load_lmf", lambda path: mortality.copy())
    return medical, demo, mortality

def test_preparation_excludes_unknown_histories_and_topcoded_ages(cycle_sources):
    table, report = training.prepare_cycle("medical", "demo", "mortality", "fictional")
    assert len(table) == 1
    assert table.iloc[0]["previousHeartAttack"] == 1
    assert table.iloc[0]["previousStroke"] == 0
    assert table.iloc[0]["follow_up_years"] == 1
    assert report["excludedUnknownHistory"] == 2
    assert report["eligibleAge40To79"] == 3

def test_preparation_detects_missing_linkage(cycle_sources):
    cycle_sources[2].drop(index = 0, inplace = True)
    with pytest.raises(ValueError, match = "lack a mortality"):
        training.prepare_cycle("medical", "demo", "mortality", "fictional")

def test_preparation_rejects_duplicate_ids(cycle_sources):
    cycle_sources[0].loc[1, "SEQN"] = 1
    with pytest.raises(pd.errors.MergeError):
        training.prepare_cycle("medical", "demo", "mortality", "fictional")

def test_preparation_rejects_invalid_follow_up(cycle_sources):
    cycle_sources[2]["permth_int"] = cycle_sources[2]["permth_int"].astype(float)
    cycle_sources[2].loc[0, "permth_int"] = float("inf")
    with pytest.raises(ValueError, match = "positive follow-up"):
        training.prepare_cycle("medical", "demo", "mortality", "fictional")

def test_bootstrap_is_reproducible_and_records_settings(monkeypatch):
    table = pd.DataFrame({"death": [0, 1, 1, 0]})
    monkeypatch.setattr(training, "fit_parameters", lambda frame: {"coefficients": [2., 0., 0., 0.], "shape": 1.})
    first = training.fit_research_model(table, bootstrap_samples = 30, seed = 12)
    assert first == training.fit_research_model(table, bootstrap_samples = 30, seed = 12)
    assert len(first["bootstrapSamples"]) == 30
    assert first["training"]["weighted"] is False
    assert validate_model(first) == first

def test_fitting_rejects_too_few_bootstraps_or_no_deaths():
    with pytest.raises(ValueError, match = "30"):
        training.fit_research_model(pd.DataFrame(), bootstrap_samples = 3)
    with pytest.raises(ValueError, match = "observed deaths"):
        training.fit_parameters(pd.DataFrame({"death": [0]}))

def test_evaluation_rejects_incomplete_five_year_outcomes():
    table = pd.DataFrame({"death": [0], "follow_up_years": [2]})
    with pytest.raises(ValueError, match = "complete five-year"):
        training.evaluate_model({}, table, table)


DATA = Path("data/raw")
LOCAL_FILES = ["MCQ_G.xpt", "DEMO_G.xpt", "NHANES_2011_2012_MORT_2019_PUBLIC.dat",
    "MCQ_H.xpt", "DEMO_H.xpt", "NHANES_2013_2014_MORT_2019_PUBLIC.dat"]

@pytest.mark.skipif(not all((DATA / name).exists() for name in LOCAL_FILES), reason = "Local NHANES research files not downloaded")
def test_local_cycle_preparation_counts():
    first, report = training.prepare_cycle(*(DATA / name for name in LOCAL_FILES[:3]), "2011-2012")
    second, checking_report = training.prepare_cycle(*(DATA / name for name in LOCAL_FILES[3:]), "2013-2014")
    assert report["modelParticipants"] == len(first) == 128
    assert report["excludedUnknownHistory"] == 1
    assert checking_report["modelParticipants"] == len(second) == 128
    assert report["deaths"] == 54
    assert checking_report["deaths"] == 38
