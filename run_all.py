"""Rebuild every output from the raw Kaggle CSV: ETL -> charts -> SQL (+ reconciliation) -> dashboard -> Tableau extracts -> notebooks."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = [
    [sys.executable, "src/pipeline.py"],
    [sys.executable, "src/charts.py"],
    [sys.executable, "src/charts_advanced.py"],
    [sys.executable, "src/run_sql.py"],
    [sys.executable, "src/reconcile_sql.py"],
    [sys.executable, "src/export_dashboard.py"],
    [sys.executable, "src/export_tableau.py"],
    [sys.executable, "-m", "jupyter", "nbconvert", "--to", "notebook", "--execute", "--inplace",
     "notebooks/btc_market_analysis.ipynb"],
    [sys.executable, "-m", "jupyter", "nbconvert", "--to", "notebook", "--execute", "--inplace",
     "--ExecutePreprocessor.timeout=1800", "notebooks/advanced_analysis.ipynb"],
]

for cmd in STEPS:
    print(f"\n>>> {' '.join(cmd[1:])}", flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)
print("\nDone. Open dashboard/index.html or the notebook.")
