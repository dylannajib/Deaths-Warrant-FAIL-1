import json; import subprocess; import sys; import pytest

# Check weighted year totals, method metadata and uncertainty warning in CLI JSON.
def test_cli_weighted_json(tmp_path):
    csv_path = tmp_path/"patient.csv"
    csv_path.write_text(
        "id,entry_age,exit_age,status,cause,weight\nA,0,1,1,heart,2\nB,0,2,1,cancer,1\nC,0,3,0,,3", encoding = "utf-8"
    ) # CSV data from data/cli_example.csv
    completed = subprocess.run(
        [sys.executable, "-m", "deaths_warrant", str(csv_path), "--start", "0", "--tau", "3"], capture_output = True, text = True
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary["years_lived"] == pytest.approx(13/6)
    assert summary["years_lost_by_cause"]["cancer"] == pytest.approx(1/6)
    assert summary["years_lost_by_cause"]["heart"] == pytest.approx(2/3)
    assert summary["method"] == "aalen_johansen"
    assert summary["weighted"] is True
    assert summary["warnings"] == ["Point estimates only. Survey-design uncertainty is not calculated."]

# Ensure a missing CSV produces a readable CLI error without a traceback.
def test_cli_missing_file(tmp_path):
    csv_path = tmp_path/"missing.csv"
    completed = subprocess.run(
        [sys.executable, "-m", "deaths_warrant", str(csv_path), "--start", "0", "--tau", "3"], capture_output = True, text = True
    )
    assert completed.returncode == 2, completed.stderr
    assert completed.stdout == "", completed.stderr
    assert csv_path.name in completed.stderr
    assert "Traceback" not in completed.stderr

# Ensure incomplete CSV schemas fail without emitting summary JSON.
def test_cli_missing_columns(tmp_path):
    csv_path = tmp_path/"patient.csv"
    csv_path.write_text("id\nA")
    completed = subprocess.run(
        [sys.executable, "-m", "deaths_warrant", str(csv_path), "--start", "0", "--tau", "3"], capture_output = True, text = True
    )
    assert completed.returncode == 2, completed.stderr
    assert completed.stdout == "", completed.stderr
    assert "Missing required columns" in completed.stderr
    assert "Traceback" not in completed.stderr

# Ensure the CLI rejects analysis beyond the final observed time.
def test_cli_rejects_extrapolation(tmp_path):
    csv_path = tmp_path/"patient.csv"
    csv_path.write_text(
        "id,entry_age,exit_age,status,cause,weight\nA,0,1,1,heart,2\nB,0,2,1,cancer,1\nC,0,3,0,,3", encoding = "utf-8"
    )
    completed = subprocess.run(
        [sys.executable, "-m", "deaths_warrant", str(csv_path), "--start", "0", "--tau", "4"], capture_output = True, text = True
    )
    assert completed.returncode == 2, completed.stderr
    assert completed.stdout == "", completed.stderr
    assert "final recorded time" in completed.stderr
    assert "Traceback" not in completed.stderr

# Ensure a header-only CSV fails with an empty-input error.
def test_cli_empty_input(tmp_path):
    csv_path = tmp_path/"patient.csv"
    csv_path.write_text("id,entry_age,exit_age,status,cause,weight", encoding = "utf-8")
    completed = subprocess.run(
        [sys.executable, "-m", "deaths_warrant", str(csv_path), "--start", "0", "--end", "3"], capture_output = True, text = True
    )
    assert completed.returncode == 2, completed.stderr
    assert "CSV cannot be empty" in completed.stderr
    assert completed.stdout == "", completed.stderr
    assert "Traceback" not in completed.stderr

# Ensure NaN and infinite analysis bounds produce clean CLI errors.
def test_cli_nonfinite_limits(tmp_path):
    csv_path = tmp_path/"patient.csv"
    csv_path.write_text(
        "id,entry_age,exit_age,status,cause,weight\nA,0,1,1,heart,2\nB,0,2,1,cancer,1\nC,0,3,0,,3", encoding = "utf-8"
    )
    completed_A = subprocess.run(
        [sys.executable, "-m", "deaths_warrant", str(csv_path), "--start", "nan", "--end", "3"], capture_output = True, text = True
    )
    completed_B = subprocess.run(
        [sys.executable, "-m", "deaths_warrant", str(csv_path), "--start", "0", "--end", "inf"], capture_output = True, text = True
    )
    assert "finite" in completed_A.stderr and completed_A.returncode == 2, completed_A.stderr
    assert "finite" in completed_B.stderr and completed_B.returncode == 2, completed_B.stderr
    assert completed_A.stdout == "", completed_A.stderr
    assert completed_B.stdout == "", completed_B.stderr
    assert "Traceback" not in completed_A.stderr and "Traceback" not in completed_B.stderr

# Ensure the analysis window cannot begin before the earliest participant entry.
def test_cli_start_before_observation(tmp_path):
    csv_path = tmp_path/"patient.csv"
    csv_path.write_text(
        "id,entry_age,exit_age,status,cause,weight\nA,0,1,1,heart,2\nB,0,2,1,cancer,1\nC,0,3,0,,3", encoding = "utf-8"
    )
    completed = subprocess.run(
        [sys.executable, "-m", "deaths_warrant", str(csv_path), "--start", "-1", "--end", "3"], capture_output = True, text = True
    )
    assert completed.returncode == 2, completed.stderr
    assert "earliest observed entry" in completed.stderr
    assert completed.stdout == "", completed.stderr
    assert "Traceback" not in completed.stderr

# Check the CLI's cause-removal year gain and assumption warning.
def test_cli_remove_cause_scenario(tmp_path):
    csv_path = tmp_path/"patient.csv"
    csv_path.write_text(
        "id,entry_age,exit_age,status,cause,weight\nA,0,1,1,heart,2\nB,0,2,1,cancer,1\nC,0,3,0,,3", encoding = "utf-8"
    )
    completed = subprocess.run(
        [sys.executable, "-m", "deaths_warrant", str(csv_path), "--remove-cause", "heart", "--start", "0", "--end", "3"],
        capture_output = True, text = True
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    scenario = summary["scenario"]
    assert scenario["years_lived"] == pytest.approx(11/4)
    assert scenario["years_gained"] == pytest.approx(7/12)
    assert scenario["assumption_dependent"] is True
    assert "Not a causal prediction" in scenario["warning"]
    assert scenario["removed_cause"] == "heart"
    assert "Traceback" not in completed.stderr

# Ensure an unrecognised cause label fails without a summary or traceback.
def test_cli_rejects_unknown_cause(tmp_path):
    csv_path = tmp_path/"patient.csv"
    csv_path.write_text(
        "id,entry_age,exit_age,status,cause,weight\nA,0,1,1,heart,2\nB,0,2,1,cancer,1\nC,0,3,0,,3", encoding = "utf-8"
    )
    completed = subprocess.run(
        [sys.executable, "-m", "deaths_warrant", str(csv_path), "--remove-cause", "unknown", "--start", "0", "--end", "3"],
        capture_output = True, text = True
    )
    assert completed.returncode == 2, completed.stderr
    assert "Unknown cause label" in completed.stderr
    assert completed.stdout == "", completed.stderr
    assert "Traceback" not in completed.stderr