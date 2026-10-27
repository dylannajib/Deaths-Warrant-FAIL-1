"""Rebuild the experimental model from ignored local NHANES files."""

import argparse; import json
from pathlib import Path
from deaths_warrant.prognosis_training import assess_feasibility, evaluate_model, fit_research_model, model_fingerprint, prepare_cycle

# Rebuild the heart-failure model and write its evaluation and feasibility artifacts.
def main():
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument("--data-dir", type = Path, default = Path("data/raw"))
    parser.add_argument("--output-dir", type = Path, default = Path("models/heart_failure"))
    parser.add_argument("--bootstrap-samples", type = int, default = 100)
    parser.add_argument("--seed", type = int, default = 20261027)
    args = parser.parse_args()
    try:
        training, training_report = prepare_cycle(args.data_dir / "MCQ_G.xpt", args.data_dir / "DEMO_G.xpt",
            args.data_dir / "NHANES_2011_2012_MORT_2019_PUBLIC.dat", "2011-2012")
        checking, checking_report = prepare_cycle(args.data_dir / "MCQ_H.xpt", args.data_dir / "DEMO_H.xpt",
            args.data_dir / "NHANES_2013_2014_MORT_2019_PUBLIC.dat", "2013-2014")
        print("Fitting research model and bootstrap samples...", flush = True)
        model = fit_research_model(training, args.bootstrap_samples, args.seed)
        model["training"]["cycle"] = "2011-2012"
        evaluation = evaluate_model(model, training, checking)
        report = {"modelVersion": model["modelVersion"], "modelFingerprint": model_fingerprint(model),
            "training": training_report, "checking": checking_report,
            "evaluation": evaluation, "clinicallyValidated": False,
            "improvesFiveYearBrier": evaluation["brier"] < evaluation["baselineBrier"],
            "releaseDecision": "Do not use for patient prognosis; experimental calculations only.",
            "limitations": ["Historical self-reported diagnoses; no current severity or treatment effects.",
                "Unweighted; ordinary bootstrap does not account for survey design.",
                "Lifetime extrapolation is unvalidated; checking cycle already inspected during development.",
                "Clinical records and self-reported survey histories are different measurement sources."]}
        feasibility = assess_feasibility(model, report)
        args.output_dir.mkdir(parents = True, exist_ok = True)
        for name, value in [("model.json", model), ("evaluation.json", report), ("feasibility.json", feasibility)]:
            (args.output_dir / name).write_text(json.dumps(value, indent = 2, allow_nan = False) + "\n", encoding = "utf-8")
        print(json.dumps(report, indent = 2, allow_nan = False))
        print("Feasibility decision:", feasibility["decision"], "— patient prognosis supported:", feasibility["patientPrognosisSupported"])
    except (OSError, ValueError) as error:
        parser.error(str(error))

if __name__ == "__main__":
    main()