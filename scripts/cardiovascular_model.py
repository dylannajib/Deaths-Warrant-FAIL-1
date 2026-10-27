"""Fit and freeze the broad research candidate, then explicitly run its reserved final check."""

import argparse; import json
from hashlib import sha256; from pathlib import Path
import pandas as pd
from deaths_warrant.cardiovascular_data import FINAL_CYCLE, SOURCE_COLUMNS, fetch_source, make_cardiovascular_table
from deaths_warrant.cardiovascular_prognosis import load_model, model_fingerprint
from deaths_warrant.cardiovascular_training import PROTOCOL, evaluate_candidate, export_model, fit_candidate, parameters, validate_development_split
from deaths_warrant.nhanes import load_lmf

# Write finite aggregate results and model coefficients, never participant rows.
def write_json(path, value):
    path.parent.mkdir(parents = True, exist_ok = True)
    path.write_text(json.dumps(value, indent = 2, allow_nan = False) + "\n", encoding = "utf-8")

# Detect changed prepared data before reusing the saved candidate for final checking.
def file_hash(path):
    return sha256(path.read_bytes()).hexdigest()

# Download the reserved cycle only after verifying the frozen candidate and protocol.
def prepare_final(data_dir):
    sources = {name + "_F.xpt": f"https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2009/DataFiles/{name}_F.xpt" for name in SOURCE_COLUMNS}
    mortality_name = "NHANES_2009_2010_MORT_2019_PUBLIC.dat"
    sources[mortality_name] = "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/datalinkage/linked_mortality/" + mortality_name
    provenance = [fetch_source(data_dir / filename, url) for filename, url in sources.items()]
    frames = {name: pd.read_sas(data_dir / (name + "_F.xpt"), format = "xport") for name in SOURCE_COLUMNS}
    table, report = make_cardiovascular_table(frames, load_lmf(data_dir / mortality_name), FINAL_CYCLE)
    return table, report, provenance

# Summarise the predefined statistical comparison without approving clinical use.
def decision(evaluation):
    five = evaluation["horizons"]["5"]
    return {"improvesBothFiveYearBaselines": five["brier"] < min(five["exponentialBrier"], five["weibullBrier"]),
        "ranksAboveChance": evaluation["concordance"] > 0.5, "patientPrognosisSupported": False,
        "reason": "Separate-period statistical checking does not validate lifetime extrapolation, clinical inputs or treatment effects."}

# Keep development fitting and the one reserved final assessment explicitly separate.
def main():
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument("--prepared-dir", type = Path, default = Path("data/processed/cardiovascular"))
    parser.add_argument("--data-dir", type = Path, default = Path("data/raw"))
    parser.add_argument("--output-dir", type = Path, default = Path("models/cardiovascular"))
    parser.add_argument("--final-check", action = "store_true")
    args = parser.parse_args()
    lock_owned = False
    try:
        args.output_dir.mkdir(parents = True, exist_ok = True)
        lock = args.output_dir / ".run.lock"
        with lock.open("x", encoding = "utf-8") as output:
            output.write("Model assessment in progress; remove only after confirming no assessment process remains.\n")
        lock_owned = True
        started_path = args.output_dir / "final_started.json"
        if started_path.exists() and not args.final_check:
            raise ValueError("Final checking has started; development must not replace the frozen candidate")
        paths = {name: args.prepared_dir / (name + ".csv") for name in ["training", "validation"]}
        training = pd.read_csv(paths["training"]); validation = pd.read_csv(paths["validation"])
        validate_development_split(training, validation)
        hashes = {name: file_hash(path) for name, path in paths.items()}
        final_path = args.output_dir / "final_evaluation.json"
        if final_path.exists():
            raise ValueError("Final check already recorded; retain this version and do not tune against its outcomes")
        print("Training participants:", len(training), "Recorded deaths:", int(training["death"].sum()), flush = True)
        fitter = fit_candidate(training)
        if args.final_check:
            model = load_model(args.output_dir / "model.json")
            freeze = json.loads((args.output_dir / "freeze.json").read_text(encoding = "utf-8"))
            if freeze["modelFingerprint"] != model_fingerprint(model) or freeze["preparedDataHashes"] != hashes or freeze["protocol"] != PROTOCOL:
                raise ValueError("Frozen candidate, data or protocol changed; final checking refused")
            if parameters(fitter) != model["parameters"]:
                raise ValueError("Reproduced fit differs from the frozen model; final checking refused")
            marker = {"modelFingerprint": freeze["modelFingerprint"], "preparedDataHashes": hashes, "protocol": PROTOCOL}
            if started_path.exists():
                if json.loads(started_path.read_text(encoding = "utf-8")) != marker:
                    raise ValueError("Final-check marker differs from the frozen candidate")
            else:
                # Persist this before accessing reserved data, even if downloading or evaluation fails.
                with started_path.open("x", encoding = "utf-8") as output:
                    output.write(json.dumps(marker, indent = 2, allow_nan = False) + "\n")
            print("Frozen model verified. Opening reserved 2009–2010 cycle...", flush = True)
            checking, audit, sources = prepare_final(args.data_dir)
            evaluation = evaluate_candidate(fitter, training, checking)
            report = {"modelFingerprint": model_fingerprint(model), "cycle": FINAL_CYCLE,
                "preparation": audit, "sources": sources, "evaluation": evaluation, "decision": decision(evaluation),
                "limitations": ["Separate-period survey sample, not forward-temporal or clinical validation.",
                    "Final means beyond observed follow-up cannot be checked from these outcomes.",
                    "Bootstrap uncertainty is ordinary resampling, not full survey-design uncertainty."]}
            write_json(final_path, report)
        else:
            print("Comparing internal validation and examination-weight sensitivity...", flush = True)
            evaluation = evaluate_candidate(fitter, training, validation)
            sensitivity = evaluate_candidate(fit_candidate(training, weighted = True), training, validation)
            print("Fitting 100 reproducible bootstrap samples...", flush = True)
            model = export_model(training, fitter)
            report = {"protocol": PROTOCOL, "validation": evaluation, "weightedSensitivity": sensitivity,
                "decision": decision(evaluation), "modelFingerprint": model_fingerprint(model)}
            write_json(args.output_dir / "model.json", model)
            write_json(args.output_dir / "development_evaluation.json", report)
            write_json(args.output_dir / "freeze.json", {"modelFingerprint": model_fingerprint(model),
                "preparedDataHashes": hashes, "protocol": PROTOCOL})
        print(json.dumps(report, indent = 2, allow_nan = False))
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    finally:
        if lock_owned:
            lock.unlink()

if __name__ == "__main__":
    main()
