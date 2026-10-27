from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import json

from deaths_warrant.cli import main

# Run the CLI on browser CSV text and return either its summary or a readable error as JSON.
def analyse_csv(csv_text, start, end, remove_cause = None):
    output = StringIO()
    errors = StringIO()
    with TemporaryDirectory() as directory:
        csv_path = Path(directory) / "patients.csv"
        csv_path.write_text(csv_text, encoding="utf-8")
        arguments = [str(csv_path), "--start", str(start), "--end", str(end)]
        if remove_cause:
            arguments.append("--remove-cause"); arguments.append(remove_cause)
        with redirect_stdout(output), redirect_stderr(errors):
            try:
                main(arguments)
            except SystemExit:
                return json.dumps({"ok": False, "error": errors.getvalue().split(": error:", 1)[-1].strip()})
    return json.dumps({"ok": True, "summary": json.loads(output.getvalue())})