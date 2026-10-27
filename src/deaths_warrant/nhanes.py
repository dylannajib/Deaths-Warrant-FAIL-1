import pandas as pd

# Positions from NHS R_ReadInProgramAllSurveys.R, converted to 0-based, end-exclusive
LMF_COLSPECS = [(0, 6), (14, 15), (15, 16), (16, 19), (19, 20), (20, 21), (42, 45), (45, 48)]
LMF_NAMES = ["seqn", "eligstat", "mortstat", "ucod_leading", "diabetes", "hyperten", "permth_int", "permth_exm"]

# Read fixed-width NHANES mortality records while preserving leading zeroes in cause codes.
def load_lmf(path):
    """Read an NHANES public-use linked mortality dat. file."""
    return pd.read_fwf(path, colspecs=LMF_COLSPECS, names=LMF_NAMES,
        na_values=["", "."], dtype={"ucod_leading": "string"}) # Keep leading zeroes: "001", not "1"

DEMO_COLUMNS = {
    "SEQN": "seqn",
    "RIAGENDR": "sex",
    "RIDAGEYR": "age_years",
    "WTINT2YR": "weight_interview",
    "SDMVPSU": "psu",
    "SDMVSTRA": "stratum",
}

# Select and rename NHANES demographic and survey-design columns from XPORT data.
def load_demo(path):
    """Read an NHANES demographics .xpt file, keeping only the columns we use."""
    df = pd.read_sas(path, format="xport")
    df = df[list(DEMO_COLUMNS)].rename(columns=DEMO_COLUMNS)
    df["seqn"] = df["seqn"].astype(int) # .xpt stores IDs as decimals
    return df


CAUSE_NAMES = {
    "001": "heart", "002": "cancer", "003": "chronic_lower_respiratory", "004": "accidents",
    "005": "cerebrovascular", "006": "alzheimers", "007": "diabetes", "008": "influenza_pneumonia",
    "009": "kidney", "010": "other"
}

# Convert eligible NHANES records to entry/exit ages, death causes and optional survey fields.
def to_standard(merged):
    """Convert merged NHANES (LMF + DEMO) into the standard format"""
    df = merged[merged["eligstat"] == 1]
    entry = df["age_years"] + 0.5
    out = pd.DataFrame({
        "id": df["seqn"],
        "entry_age": entry,
        "exit_age": entry + df["permth_int"] / 12,
        "status": df["mortstat"].astype(int),
        "cause": df["ucod_leading"].map(CAUSE_NAMES),
        "age_topcoded": df["age_years"] == 80
    })
    if "weight_interview" in df.columns:
        out["weight"] = df["weight_interview"]
    if "psu" in df.columns:
        out["psu"] = df["psu"]
    if "stratum" in df.columns:
        out["stratum"] = df["stratum"]
    return out