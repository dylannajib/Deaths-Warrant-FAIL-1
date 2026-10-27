from pathlib import Path; import pandas as pd; import pytest
from deaths_warrant.nhanes import load_lmf, load_demo, to_standard
from deaths_warrant.schema import validate

LMF_PATH = Path("data/raw/NHANES_2013_2014_MORT_2019_PUBLIC.dat")
DEMO_PATH = Path("data/raw/DEMO_H.xpt")

# Skip, don't fail if data isn't downloaded (e.g. on another device)
needs_data = pytest.mark.skipif(
    not (LMF_PATH.exists() and DEMO_PATH.exists()),
    reason="LMF file not downloaded"
    )

@needs_data
# Check the local 2013-2014 mortality file contains the expected participant count.
def test_row_count():
    df = load_lmf(LMF_PATH)
    assert len(df) == 10175
@needs_data
# Check mortality outcomes account for exactly the linkage-eligible participants.
def test_alive_plus_dead_equals_eligible():
    df = load_lmf(LMF_PATH)
    alive = (df["mortstat"] == 0).sum()
    dead = (df["mortstat"] == 1).sum()
    eligible = (df["eligstat"] == 1).sum()
    assert alive + dead == eligible
@needs_data
# Check cause codes appear exactly on records marked as deaths.
def test_every_death_needs_a_cause():
    df = load_lmf(LMF_PATH)
    has_cause = df["ucod_leading"].notna()
    is_dead = df["mortstat"].eq(1)
    assert (has_cause == is_dead).all()
@needs_data
# Check mortality status is missing exactly when linkage eligibility is absent.
def test_mortstat_blank_if_not_eligible():
    df = load_lmf(LMF_PATH)
    is_blank = df["mortstat"].isna()
    not_eligible = (df["eligstat"] != 1)
    assert (is_blank == not_eligible).all()
@needs_data
# Ensure joining local mortality and demographic files preserves every participant.
def test_merge_keeps_everyone():
    lmf = load_lmf(LMF_PATH)
    demo = load_demo(DEMO_PATH)
    df = lmf.merge(demo, on="seqn", how="inner", validate="one_to_one")
    assert len(df) == 10175
@needs_data
# Check linkage eligibility code two identifies precisely the under-18 participants.
def test_children_are_exactly_eligstat_2():
    lmf = load_lmf(LMF_PATH)
    demo = load_demo(DEMO_PATH)
    df = lmf.merge(demo, on="seqn", how="inner", validate="one_to_one")
    is_child = df["age_years"] < 18
    is_eligstat_2 = df["eligstat"] == 2
    assert (is_child == is_eligstat_2).all()

# Check age conversion, eligibility filtering and cause mapping on a small synthetic cohort.
def test_to_standard_small_example():
    merged = pd.DataFrame({
        "seqn": [1, 2, 3],
        "eligstat": [1, 1, 2],
        "mortstat": [0, 1, None],
        "ucod_leading": [None, "002", None],
        "permth_int": [24, 6, None],
        "age_years": [40, 70, 10],
    })
    out = to_standard(merged)
    assert list(out["id"]) == [1, 2]
    assert list(out["entry_age"]) == [40.5, 70.5]
    assert list(out["exit_age"]) == [42.5, 71]
    assert list(out["status"]) == [0, 1]
    assert pd.isna(out["cause"].iloc[0])
    assert out["cause"].iloc[1] == "cancer"
    assert list(out["age_topcoded"]) == [False, False]

@needs_data
# Check the converted local cohort meets the patient schema and expected death counts.
def test_real_data_passes_validation():
    lmf = load_lmf(LMF_PATH)
    demo = load_demo(DEMO_PATH)
    df = lmf.merge(demo, on="seqn", how="inner", validate="one_to_one")
    out = to_standard(df)
    validate(out)
    assert len(out) == 6100
    assert (out["status"] == 1).sum() == 467

# Ensure optional weights, strata and PSU identifiers survive eligibility filtering.
def test_to_standard_preserves_survey_fields():
    merged = pd.DataFrame({
        "seqn": [1, 2, 3],
        "eligstat": [1, 1, 2],
        "mortstat": [0, 1, None],
        "ucod_leading": [None, "002", None],
        "permth_int": [24, 6, None],
        "age_years": [40, 70, 10],
        "weight_interview": [2.0, 3.0, 4.0],
        "psu": [1, 2, 1],
        "stratum": [10, 10, 10]
        })
    out = to_standard(merged)
    assert list(out["weight"]) == [2.0, 3.0]
    assert list(out["psu"]) == [1, 2]
    assert list(out["stratum"]) == [10, 10]