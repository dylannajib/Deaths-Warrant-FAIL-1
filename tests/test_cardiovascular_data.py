from pathlib import Path
import numpy as np; import pandas as pd; import pytest
from deaths_warrant import cardiovascular_data as data

# Provide synthetic source tables covering cohort exclusions.
@pytest.fixture
def sources():
    ids = [1., 2., 3., 4., 5., 6.]
    frames = {
        "DEMO": pd.DataFrame({"SEQN": ids, "RIDAGEYR": [60, 70, 80, 50, 55, 65], "RIAGENDR": [1, 2, 1, 2, 1, 2],
            "RIDSTATR": [2] * 6, "WTMEC2YR": [100.] * 6, "SDMVPSU": [1] * 6, "SDMVSTRA": [2] * 6}),
        "MCQ": pd.DataFrame({"SEQN": ids, "MCQ160B": [1, 2, 1, 2, 1, 1], "MCQ160C": [2, 1, 2, 2, 2, 2],
            "MCQ160D": [2, 2, 2, 2, 2, 2], "MCQ160E": [1, 2, 2, 2, 9, 2], "MCQ160F": [2] * 6}),
        "BMX": pd.DataFrame({"SEQN": ids, "BMXBMI": [25.] * 6}),
        "BIOPRO": pd.DataFrame({"SEQN": ids, "LBXSCR": [1.] * 6}),
        "BPX": pd.DataFrame({"SEQN": ids, "BPXSY1": [120.] * 6, "BPXSY2": [130.] * 6,
            "BPXSY3": [np.nan] * 6, "BPXSY4": [0.] * 6}),
        "DIQ": pd.DataFrame({"SEQN": ids, "DIQ010": [2, 1, 2, 2, 2, 3]}),
        "SMQ": pd.DataFrame({"SEQN": ids, "SMQ020": [2, 1, 2, 2, 2, 2], "SMQ040": [np.nan, 2, np.nan, np.nan, np.nan, np.nan]})
    }
    mortality = pd.DataFrame({"seqn": ids, "eligstat": [1] * 6, "mortstat": [1, 0, 0, 1, 0, 0],
        "permth_exm": [12., 84., 60., 24., 60., 72.], "permth_int": [24.] * 6})
    return frames, mortality

# Check condition features, exam follow-up, and exclusion counts.
def test_prepares_multiple_conditions_using_exam_time(sources):
    frames, mortality = sources
    table, report = data.make_cardiovascular_table(frames, mortality, "2007-2008")
    assert table["seqn"].tolist() == [1, 2]
    assert table["follow_up_years"].tolist() == [1., 7.]
    assert table["heartFailure"].tolist() == [1, 0]
    assert table["coronaryHeartDisease"].tolist() == [0, 1]
    assert table["previousHeartAttack"].tolist() == [1, 0]
    assert table["systolicBloodPressure"].tolist() == [125., 125.]
    assert table["currentSmoker"].tolist() == [0, 1]
    assert report["reportedCardiovascularHistory"] == 4
    assert report["excludedMissingPredictorsAfterZeroFollowUp"] == 2
    assert report["missingByFeatureBeforeExclusions"]["previousHeartAttack"] == 1
    assert report["missingByFeatureBeforeExclusions"]["diabetes"] == 1
    assert set(data.FEATURES).issubset(table.columns)
    assert "mortstat" not in data.FEATURES and "follow_up_years" not in data.FEATURES

# Check unknown cardiovascular history excludes incomplete records.
@pytest.mark.parametrize("code", [7, 9, np.nan])
def test_unknown_cvd_history_is_not_no(sources, code):
    frames, mortality = sources
    frames["MCQ"].loc[0, "MCQ160F"] = code
    table, _ = data.make_cardiovascular_table(frames, mortality, "2007-2008")
    assert 1 not in table["seqn"].tolist()

# Check missing measurements remain missing and exclude records.
def test_missing_measurements_are_not_imputed_from_other_people(sources):
    frames, mortality = sources
    frames["BIOPRO"].loc[0, "LBXSCR"] = np.nan
    table, report = data.make_cardiovascular_table(frames, mortality, "2007-2008")
    assert table["seqn"].tolist() == [2]
    assert report["missingByFeatureBeforeExclusions"]["creatinine"] == 1

# Check zero follow-up is excluded and counted.
def test_zero_follow_up_is_reported_not_replaced_with_an_invented_time(sources):
    frames, mortality = sources
    mortality.loc[0, "permth_exm"] = 0
    table, report = data.make_cardiovascular_table(frames, mortality, "2007-2008")
    assert 1 not in table["seqn"].tolist()
    assert report["excludedZeroFollowUp"] == 1

# Check malformed source records are rejected.
@pytest.mark.parametrize("problem", ["duplicate_id", "fractional_id", "missing_link", "invalid_outcome", "negative_time", "infinite_measurement", "bad_question_code", "contradictory_smoking"])
def test_invalid_inputs_fail_closed(sources, problem):
    frames, mortality = sources
    if problem == "duplicate_id": frames["MCQ"].loc[1, "SEQN"] = 1
    if problem == "fractional_id": frames["MCQ"].loc[0, "SEQN"] = 1.5
    if problem == "missing_link": mortality.drop(index = 0, inplace = True)
    if problem == "invalid_outcome": mortality.loc[0, "mortstat"] = 9
    if problem == "negative_time": mortality.loc[0, "permth_exm"] = -1
    if problem == "infinite_measurement": frames["BMX"].loc[0, "BMXBMI"] = np.inf
    if problem == "bad_question_code": frames["MCQ"].loc[0, "MCQ160E"] = 4
    if problem == "contradictory_smoking": frames["SMQ"].loc[0, "SMQ040"] = 1
    with pytest.raises(ValueError):
        data.make_cardiovascular_table(frames, mortality, "2007-2008")

# Check reserved data is rejected before any source access.
def test_reserved_cycle_is_rejected_before_network_or_filesystem_access(monkeypatch):
    monkeypatch.setattr(data, "fetch_source", lambda *args: pytest.fail("Final checking data must not be downloaded"))
    with pytest.raises(ValueError, match = "reserved"):
        data.prepare_development_cycle(Path("does-not-exist"), data.FINAL_CYCLE)

# Check splits stay stable across row order and outcome changes.
def test_stable_splits_do_not_depend_on_order_or_outcomes():
    table = pd.DataFrame({"seqn": range(1, 101), "cycle": ["2007-2008"] * 100, "death": [0, 1] * 50})
    training, validation = data.split_development(table)
    changed = table.sample(frac = 1, random_state = 4).copy()
    changed["death"] = 1 - changed["death"]
    second_training, second_validation = data.split_development(changed)
    assert set(training["seqn"]) == set(second_training["seqn"])
    assert set(validation["seqn"]) == set(second_validation["seqn"])
    assert set(training["seqn"]).isdisjoint(validation["seqn"])
    assert len(training) + len(validation) == len(table)

# Check splits reject duplicate IDs and reserved cycles.
def test_split_rejects_reserved_records_and_duplicate_participants():
    table = pd.DataFrame({"seqn": [1, 1], "cycle": ["2007-2008"] * 2})
    with pytest.raises(ValueError, match = "unique"):
        data.split_development(table)
    table = pd.DataFrame({"seqn": [1, 2], "cycle": [data.FINAL_CYCLE] * 2})
    with pytest.raises(ValueError, match = "Reserved"):
        data.split_development(table)

# Check cached provenance and official source restrictions.
def test_cache_provenance_and_source_restrictions(tmp_path, monkeypatch):
    path = tmp_path / "DEMO_E.xpt"
    path.write_bytes(b"fictional data for a cache-only checksum test")
    monkeypatch.setattr(data, "urlopen", lambda *args, **kwargs: pytest.fail("Cached files must not be fetched"))
    record = data.fetch_source(path, "https://wwwn.cdc.gov/fictional")
    assert record["bytes"] == path.stat().st_size
    assert len(record["sha256"]) == 64
    for url in ["http://wwwn.cdc.gov/file", "https://example.com/file", "https://user:password@wwwn.cdc.gov/file"]:
        with pytest.raises(ValueError, match = "official"):
            data.fetch_source(path, url)

# Check HTML responses cannot enter the source cache.
def test_html_download_is_not_written_to_cache(tmp_path, monkeypatch):
    class Response:
        # Return the fake download response for context management.
        def __enter__(self): return self
        # Allow download errors to propagate from the fake response.
        def __exit__(self, *args): return False
        # Provide an allowed URL for the fake response.
        def geturl(self): return "https://wwwn.cdc.gov/file.xpt"
        # Return an HTML error body for download validation.
        def read(self, limit): return b"<html>error</html>"
    monkeypatch.setattr(data, "urlopen", lambda *args, **kwargs: Response())
    path = tmp_path / "file.xpt"
    with pytest.raises(ValueError, match = "XPORT"):
        data.fetch_source(path, "https://wwwn.cdc.gov/file.xpt")
    assert not path.exists()
