"""Prepare broad cardiovascular development data without fitting a model or opening the final cycle."""

from hashlib import sha256; from pathlib import Path
from urllib.parse import urlparse; from urllib.request import urlopen
import numpy as np; import pandas as pd
from deaths_warrant.nhanes import load_lmf

DEVELOPMENT_CYCLES = {"2007-2008": "E", "2011-2012": "G", "2013-2014": "H"}
PLAN_VERSION = "cardiovascular-data-v1"
FINAL_CYCLE = "2009-2010"
SPLIT_SEED = 20261027
CONDITIONS = {"MCQ160B": "heartFailure", "MCQ160C": "coronaryHeartDisease", "MCQ160D": "angina",
    "MCQ160E": "previousHeartAttack", "MCQ160F": "previousStroke"}
FEATURES = ["ageYears", "recordedSex"] + list(CONDITIONS.values()) + [
    "diabetes", "currentSmoker", "bmi", "systolicBloodPressure", "creatinine"]
SOURCE_COLUMNS = {
    "DEMO": ["SEQN", "RIDAGEYR", "RIAGENDR", "RIDSTATR", "WTMEC2YR", "SDMVPSU", "SDMVSTRA"],
    "MCQ": ["SEQN"] + list(CONDITIONS), "BMX": ["SEQN", "BMXBMI"],
    "BIOPRO": ["SEQN", "LBXSCR"], "BPX": ["SEQN", "BPXSY1", "BPXSY2", "BPXSY3", "BPXSY4"],
    "DIQ": ["SEQN", "DIQ010"], "SMQ": ["SEQN", "SMQ020", "SMQ040"]
}
ALLOWED_HOSTS = {"wwwn.cdc.gov", "ftp.cdc.gov"}
MAX_SOURCE_BYTES = 32 * 1024 * 1024

# List official source URLs for an allowed development cycle.
def development_sources(cycle):
    if cycle not in DEVELOPMENT_CYCLES:
        raise ValueError("Only development cycles can be prepared; the final checking cycle remains reserved")
    suffix = DEVELOPMENT_CYCLES[cycle]
    year = cycle[:4]
    sources = {name + "_" + suffix + ".xpt":
        f"https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{year}/DataFiles/{name}_{suffix}.xpt"
        for name in SOURCE_COLUMNS}
    mortality = "NHANES_" + cycle.replace("-", "_") + "_MORT_2019_PUBLIC.dat"
    sources[mortality] = "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/datalinkage/linked_mortality/" + mortality
    return sources

# Require an official CDC HTTPS source URL.
def _check_url(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or parsed.username or parsed.password:
        raise ValueError("Source downloads must use the supported official CDC HTTPS hosts")

# Load or safely cache a source and record its provenance.
def fetch_source(path, url):
    path = Path(path)
    _check_url(url)
    if path.exists():
        if path.is_symlink():
            raise ValueError("Source cache must not contain symbolic links")
        if path.stat().st_size > MAX_SOURCE_BYTES:
            raise ValueError("Source file exceeds the supported size limit")
        contents = path.read_bytes()
    else:
        with urlopen(url, timeout = 60) as response:
            _check_url(response.geturl())
            contents = response.read(MAX_SOURCE_BYTES + 1)
        if not contents or len(contents) > MAX_SOURCE_BYTES:
            raise ValueError("CDC source was empty or exceeded the supported size limit")
        if path.suffix == ".xpt" and not contents.startswith(b"HEADER RECORD*******LIBRARY HEADER RECORD!!!!!!!"):
            raise ValueError("CDC response is not an XPORT file; refusing to cache it")
        if path.suffix == ".dat" and (b"<html" in contents[:200].lower() or b"<!doctype" in contents[:200].lower()):
            raise ValueError("CDC response is HTML rather than mortality data")
        path.parent.mkdir(parents = True, exist_ok = True)
        # Exclusive creation avoids overwriting an existing source, including after a concurrent download.
        with path.open("xb") as output:
            output.write(contents)
    return {"file": path.name, "url": url, "bytes": len(contents), "sha256": sha256(contents).hexdigest()}

# Validate and normalize unique participant IDs.
def _validate_ids(table, name):
    if "SEQN" not in table:
        raise ValueError(name + " has no participant ID column")
    identifiers = pd.to_numeric(table["SEQN"], errors = "raise")
    if identifiers.isna().any() or not np.isfinite(identifiers).all() or (identifiers <= 0).any() or (identifiers % 1 != 0).any():
        raise ValueError(name + " IDs must be finite positive integers")
    if identifiers.duplicated().any():
        raise ValueError(name + " contains duplicate participant IDs")
    result = table.copy()
    result["SEQN"] = identifiers.astype(int)
    return result

# Validate measurements and treat zero as missing.
def _positive(values):
    numeric = pd.to_numeric(values, errors = "raise")
    if np.isinf(numeric).any() or (numeric.dropna() < 0).any():
        raise ValueError("Clinical measurements must not contain negative or infinite values")
    return numeric.where(numeric > 0)

# Build the eligible complete-case cohort and exclusion report.
def make_cardiovascular_table(frames, mortality, cycle):
    merged = None
    for name, columns in SOURCE_COLUMNS.items():
        table = frames[name]
        if not set(columns).issubset(table.columns):
            raise ValueError(name + " is missing required columns")
        table = _validate_ids(table[columns], name)
        merged = table if merged is None else merged.merge(table, on = "SEQN", how = "left", validate = "one_to_one")
    mortality = _validate_ids(mortality.rename(columns = {"seqn": "SEQN"}), "Mortality")
    merged = merged.merge(mortality[["SEQN", "eligstat", "mortstat", "permth_exm"]],
        on = "SEQN", how = "left", validate = "one_to_one", indicator = True)
    if not merged["_merge"].eq("both").all():
        raise ValueError("Some demographic participants lack a mortality-linkage record")
    examined = merged[merged["RIDAGEYR"].between(40, 79) & merged["RIDSTATR"].eq(2)].copy()
    linked = examined[examined["eligstat"].eq(1)].copy()
    cohort = linked[linked[list(CONDITIONS)].eq(1).any(axis = 1)].copy()
    for question, field in CONDITIONS.items():
        if not cohort[question].dropna().isin([1, 2, 7, 9]).all():
            raise ValueError("Unsupported cardiovascular questionnaire answer: " + question)
        cohort[field] = cohort[question].map({1: 1, 2: 0})
    cohort["ageYears"] = cohort["RIDAGEYR"]
    cohort["recordedSex"] = cohort["RIAGENDR"].where(cohort["RIAGENDR"].isin([1, 2]))
    if not cohort["DIQ010"].dropna().isin([1, 2, 3, 7, 9]).all():
        raise ValueError("Unsupported diabetes questionnaire answer")
    cohort["diabetes"] = cohort["DIQ010"].map({1: 1, 2: 0})
    if not cohort["SMQ020"].dropna().isin([1, 2, 7, 9]).all() or not cohort["SMQ040"].dropna().isin([1, 2, 3, 7, 9]).all():
        raise ValueError("Unsupported smoking questionnaire answer")
    if (cohort["SMQ020"].eq(2) & cohort["SMQ040"].isin([1, 2])).any():
        raise ValueError("Contradictory lifetime/current smoking answers")
    cohort["currentSmoker"] = np.nan
    cohort.loc[cohort["SMQ020"].eq(2), "currentSmoker"] = 0
    ever_smoked = cohort["SMQ020"].eq(1)
    cohort.loc[ever_smoked, "currentSmoker"] = cohort.loc[ever_smoked, "SMQ040"].map({1: 1, 2: 1, 3: 0})
    cohort["bmi"] = _positive(cohort["BMXBMI"])
    cohort["creatinine"] = _positive(cohort["LBXSCR"])
    readings = pd.concat([_positive(cohort["BPXSY" + str(number)]) for number in [1, 2, 3, 4]], axis = 1)
    cohort["systolicBloodPressure"] = readings.mean(axis = 1)
    if not cohort["mortstat"].isin([0, 1]).all():
        raise ValueError("Mortality-eligible participants need binary death indicators")
    follow_up = pd.to_numeric(cohort["permth_exm"], errors = "raise")
    if follow_up.isna().any() or not np.isfinite(follow_up).all() or (follow_up < 0).any():
        raise ValueError("Exam-based follow-up must be finite and nonnegative")
    missing = cohort[FEATURES].isna().sum().astype(int).to_dict()
    positive_follow_up = cohort[follow_up > 0].copy()
    complete = positive_follow_up.dropna(subset = FEATURES).copy()
    if not complete["ageYears"].mod(1).eq(0).all():
        raise ValueError("Age must contain completed integer years")
    weights = _positive(complete["WTMEC2YR"])
    if weights.isna().any() or complete[["SDMVPSU", "SDMVSTRA"]].isna().any().any():
        raise ValueError("Complete examined records need valid examination weights and survey design fields")
    result = complete[FEATURES].copy()
    for field in ["ageYears", "recordedSex"] + list(CONDITIONS.values()) + ["diabetes", "currentSmoker"]:
        result[field] = result[field].astype(int)
    result.insert(0, "seqn", complete["SEQN"].astype(int))
    result.insert(0, "cycle", cycle)
    result["follow_up_years"] = complete["permth_exm"] / 12
    result["death"] = complete["mortstat"].astype(int)
    result["examWeight2yr"] = weights
    result["psu"] = complete["SDMVPSU"].astype(int)
    result["stratum"] = complete["SDMVSTRA"].astype(int)
    report = {"cycle": cycle, "demographicParticipants": len(merged), "examinedAge40To79": len(examined),
        "mortalityEligible": len(linked), "reportedCardiovascularHistory": len(cohort),
        "missingByFeatureBeforeExclusions": missing, "excludedZeroFollowUp": int(follow_up.eq(0).sum()),
        "excludedMissingPredictorsAfterZeroFollowUp": len(positive_follow_up) - len(complete),
        "included": len(result), "deaths": int(result["death"].sum())}
    return result.reset_index(drop = True), report

# Fetch and assemble one development cycle with provenance.
def prepare_development_cycle(data_dir, cycle):
    sources = development_sources(cycle)
    records = []
    for filename, url in sources.items():
        records.append(fetch_source(Path(data_dir) / filename, url))
    suffix = DEVELOPMENT_CYCLES[cycle]
    frames = {name: pd.read_sas(Path(data_dir) / f"{name}_{suffix}.xpt", format = "xport") for name in SOURCE_COLUMNS}
    mortality_name = "NHANES_" + cycle.replace("-", "_") + "_MORT_2019_PUBLIC.dat"
    table, report = make_cardiovascular_table(frames, load_lmf(Path(data_dir) / mortality_name), cycle)
    return table, report, records

# Assign participants to reproducible development splits.
def split_development(table, seed = SPLIT_SEED):
    if table.empty or table["seqn"].duplicated().any():
        raise ValueError("Development data must be nonempty with unique participant IDs")
    if not table["cycle"].isin(DEVELOPMENT_CYCLES).all():
        raise ValueError("Reserved or unsupported cycles must not enter development")
    # Hash participant identity into a fixed split assignment.
    def group(row):
        key = f"{seed}:{row.cycle}:{row.seqn}".encode("utf-8")
        return "training" if int.from_bytes(sha256(key).digest()[:8], "big") % 100 < 80 else "validation"
    roles = pd.Series([group(row) for row in table.itertuples(index = False)], index = table.index)
    training = table[roles.eq("training")].copy()
    validation = table[roles.eq("validation")].copy()
    if training.empty or validation.empty:
        raise ValueError("Development split must contain training and validation participants")
    return training.reset_index(drop = True), validation.reset_index(drop = True)
