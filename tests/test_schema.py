from deaths_warrant.schema import validate; import pandas as pd; import pytest

# Build a valid three-patient table for isolated schema mutations.
def valid_df():
    """a small table that follows every rule."""
    return pd.DataFrame({
        "id": [1, 2, 3],
        "entry_age": [40.0, 55.0, 70.0],
        "exit_age": [45.0, 60.0, 72.0],
        "status": [0, 1, 1],
        "cause": [None, "heart", "cancer"],
    })

# Check the unmodified synthetic patient table satisfies the schema.
def test_valid_table_passes():
    validate(valid_df())

# Ensure the cause column is mandatory even when other patient fields exist.
def test_missing_column_fails():
    df = valid_df().drop(columns=["cause"])
    with pytest.raises(ValueError):
        validate(df)

# Ensure two participants cannot share the same identifier.
def test_duplicate_id_fails():
    df = valid_df()
    df.loc[1, "id"] = 1
    with pytest.raises(ValueError):
        validate(df)

# Ensure patient follow-up cannot start at a negative age.
def test_negative_entry_age_fails():
    df = valid_df()
    df.loc[0, "entry_age"] = -5
    with pytest.raises(ValueError):
        validate(df)

# Ensure exit age cannot precede the participant's entry age.
def test_exit_before_entry_fails():
    df = valid_df()
    df.loc[0, "exit_age"] = 30
    with pytest.raises(ValueError):
        validate(df)

# Ensure death status is restricted to the supported binary values.
def test_bad_status_fails():
    df = valid_df()
    df.loc[0, "status"] = 2
    with pytest.raises(ValueError):
        validate(df)

# Ensure every death record specifies its cause.
def test_dead_without_cause_fails():
    df = valid_df()
    df.loc[1, "cause"] = None
    with pytest.raises(ValueError):
        validate(df)

# Ensure censored records do not carry a death cause.
def test_alive_with_cause_fails():
    df = valid_df()
    df.loc[0, "cause"] = "heart"
    with pytest.raises(ValueError):
        validate(df)