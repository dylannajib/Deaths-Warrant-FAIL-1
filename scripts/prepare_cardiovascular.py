"""Prepare development CSVs and reserve the unopened final checking cycle. Does not fit a model."""

import argparse; import json
from pathlib import Path
import pandas as pd
from deaths_warrant.cardiovascular_data import DEVELOPMENT_CYCLES, FEATURES, FINAL_CYCLE, PLAN_VERSION, SPLIT_SEED, prepare_development_cycle, split_development

# Write development splits and a historical preparation summary.
def main():
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument("--data-dir", type = Path, default = Path("data/raw"))
    parser.add_argument("--output-dir", type = Path, default = Path("data/processed/cardiovascular"))
    parser.add_argument("--summary", type = Path, default = Path("models/cardiovascular/data_summary.json"))
    args = parser.parse_args()
    tables, cycles, sources = [], [], []
    try:
        for cycle in DEVELOPMENT_CYCLES:
            print("Preparing development cycle:", cycle, flush = True)
            table, report, records = prepare_development_cycle(args.data_dir, cycle)
            tables.append(table); cycles.append(report); sources.extend(records)
        development = pd.concat(tables, ignore_index = True)
        training, validation = split_development(development)
        args.output_dir.mkdir(parents = True, exist_ok = True)
        for name, table in [("training.csv", training), ("validation.csv", validation)]:
            table.to_csv(args.output_dir / name, index = False)
        summary = {
            "schemaVersion": 1, "planVersion": PLAN_VERSION, "purpose": "Data preparation only; no model fitted", "features": FEATURES,
            "outcome": {"event": "all-cause death", "origin": "NHANES examination", "units": "years", "followUpThrough": 2019},
            "developmentCycles": list(DEVELOPMENT_CYCLES), "cycles": cycles, "splitSeed": SPLIT_SEED,
            "splitMethod": "Fixed SHA-256 participant assignment, approximately 80/20 within development; independent of outcomes.",
            "training": {"participants": len(training), "deaths": int(training["death"].sum())},
            "validation": {"participants": len(validation), "deaths": int(validation["death"].sum())},
            "finalChecking": {"cycle": FINAL_CYCLE, "status": "reserved_not_downloaded_or_opened_by_this_pipeline",
                "reason": "Separate previously uninspected survey cycle with potential follow-up beyond five years.",
                "limitation": "Earlier than some development cycles; not a forward-temporal or independent clinical-population assessment."},
            "noParticipantRowsInSummary": True, "sources": sources
        }
        args.summary.parent.mkdir(parents = True, exist_ok = True)
        args.summary.write_text(json.dumps(summary, indent = 2, allow_nan = False) + "\n", encoding = "utf-8")
        (args.output_dir / "manifest.json").write_text(json.dumps(summary, indent = 2, allow_nan = False) + "\n", encoding = "utf-8")
        print("Training:", summary["training"], "Validation:", summary["validation"])
        print("Final checking cycle remains unopened:", FINAL_CYCLE)
        print("Files written to:", args.output_dir)
    except (OSError, ValueError) as error:
        parser.error(str(error))

if __name__ == "__main__":
    main()
