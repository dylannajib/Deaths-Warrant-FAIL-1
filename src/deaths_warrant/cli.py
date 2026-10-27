import argparse; import pandas as pd; import json; from math import isfinite
from deaths_warrant.schema import validate
from deaths_warrant.estimators import AalenJohansenEstimator
from deaths_warrant.years_lost import summarise_years
from deaths_warrant.what_if import remove_cause

# Define CSV input, analysis-window and cause-removal command-line options.
def build_parser():
    parser = argparse.ArgumentParser(description="Analyse restricted years lived and lost")
    parser.add_argument("input", help = "Path to the standard patient CSV")
    parser.add_argument("--start", type = float, required = True, help = "Start of the analysis interval")
    parser.add_argument(
        "--end", "--tau", dest="tau", metavar="END", type = float, required = True, help = "End of the analysis interval"
    )
    parser.add_argument("--remove-cause", help = "Takes a cause label")
    return parser

# Assign stable positive codes to death causes while reserving zero for censoring.
def encode_causes(table):
    labels = sorted(table["cause"].dropna().unique())
    label_to_code = {}
    for code, label in enumerate(labels, start = 1):
        label_to_code[label] = code
    codes = table["cause"].map(label_to_code).fillna(0).astype(int).tolist()
    return codes, label_to_code

# Validate patient CSV input and emit restricted-years analysis and optional scenario JSON.
def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        table = pd.read_csv(args.input, dtype = {"id": "string", "cause": "string"})
        if table.empty:
            raise ValueError("CSV cannot be empty (main)")
        validate(table)
        if not (isfinite(args.start) and isfinite(args.tau)):
            raise ValueError("Start and tau must be finite (main)")
        if args.start < table["entry_age"].min():
            raise ValueError("Start cannot precede the earliest observed entry age (main)")
        codes, label_to_code = encode_causes(table)
        weights = None
        if "weight" in table.columns:
            weights = table["weight"].tolist()
        result = AalenJohansenEstimator().estimate(
            table["exit_age"].tolist(), codes, entry = table["entry_age"].tolist(), weights = weights
        )
        summary = summarise_years(result.curve, args.start, args.tau)
        labelled_losses = {}
        for label, code in label_to_code.items():
            labelled_losses[label] = summary["years_lost_by_cause"][f"cif_{code}"]
        summary["years_lost_by_cause"] = labelled_losses
        summary["method"] = result.method
        summary["weighted"] = weights is not None
        summary["warnings"] = ["Point estimates only. Survey-design uncertainty is not calculated."]
        if not (args.remove_cause is None):
            if not (args.remove_cause in label_to_code):
                raise ValueError("Unknown cause label (main)")
            selected_code = label_to_code[args.remove_cause]
            scenario = remove_cause(table["exit_age"].tolist(), codes, selected_code, table["entry_age"].tolist(), weights)
            scenario_summary = summarise_years(scenario["curve"], args.start, args.tau)
            summary["scenario"] = {
                "removed_cause": args.remove_cause,
                "years_lived": scenario_summary["years_lived"],
                "years_gained": scenario_summary["years_lived"] - summary["years_lived"],
                "assumption_dependent": scenario["assumption_dependent"],
                "warning": scenario["warning"]
            }
            summary["warnings"].append(scenario["warning"])
        jdump = json.dumps(summary, indent = 2, allow_nan = False)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(jdump)
    return 0
