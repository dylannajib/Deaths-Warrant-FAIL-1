REQUIRED_COLUMNS = ["id", "entry_age", "exit_age", "status", "cause"]

# Reject patient tables with missing columns, invalid ages or inconsistent death records.
def validate(df):
    """Check that df follows the standard format. Raise ValueError if not."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    if df["id"].duplicated().any() or df["id"].isna().any():
        raise ValueError(f"Column 'id' must be unique and non-blank")
    if df["entry_age"].lt(0).any() or df["entry_age"].isna().any():
        raise ValueError(f"Column 'entry_age' must be non-negative and non-blank")
    if df["exit_age"].lt(df["entry_age"]).any() or df["exit_age"].isna().any():
        raise ValueError(f"Column 'exit_age' must be at least the value of 'entry_age' and non-blank")
    if not df["status"].isin([0, 1]).all():
        raise ValueError(f"Column 'status' must be 0 or 1 and non-blank")
    has_cause = df["cause"].notna()
    is_dead = df["status"].eq(1)
    if (has_cause != is_dead).any():
        raise ValueError(f"Column 'cause' must be filled in if and only if the value of 'status' is 1")
    return df
