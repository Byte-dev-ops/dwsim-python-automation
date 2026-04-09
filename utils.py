import sys
import os
import logging
import csv
import time
from datetime import datetime
from config import (
    DWSIM_PATH,
    LOG_FILE,
    RESULTS_CSV,
    REPORT_FILE,
    PLOTS_DIR,
    CSV_FIELDNAMES,   # 🔥 ADD THIS
)


# ── Logging ───────────────────────────────────────────────────────────────────

def setup_logging():
    """
    Configure root logger to write to both the console and simulation.log.
    Call this once at the top of run_screening.py before anything else.
    """
    os.makedirs(os.path.dirname(LOG_FILE) or ".", exist_ok=True)
    fmt = "%(asctime)s  %(levelname)-8s  %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt=datefmt,
        handlers=[
            logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.info("Logging initialised — output also written to %s", LOG_FILE)


# ── DWSIM bootstrap ───────────────────────────────────────────────────────────

def init_dwsim():
    import clr
    clr.AddReference("System")
    import os
    import sys
    from System.IO import Directory

    if not os.path.isdir(DWSIM_PATH):
        raise RuntimeError(f"DWSIM path not found: {DWSIM_PATH}")

    # ✅ VERY IMPORTANT
    Directory.SetCurrentDirectory(DWSIM_PATH)
    sys.path.append(DWSIM_PATH)

    # ✅ FORCE LOAD ALL DLLs (NO FALLBACK)
    required_dlls = [
        "CapeOpen.dll",
        "DWSIM.Automation.dll",
        "DWSIM.Interfaces.dll",
        "DWSIM.GlobalSettings.dll",
        "DWSIM.SharedClasses.dll",
        "DWSIM.Thermodynamics.dll",
        "DWSIM.UnitOperations.dll",
        "DWSIM.FlowsheetBase.dll"
    ]

    for dll in required_dlls:
        full_path = os.path.join(DWSIM_PATH, dll)

        if not os.path.exists(full_path):
            raise RuntimeError(f"❌ Missing DLL: {full_path}")

        clr.AddReference(full_path)

    # Optional DLL
    thermo_c = os.path.join(DWSIM_PATH, "DWSIM.Thermodynamics.ThermoC.dll")
    if os.path.exists(thermo_c):
        clr.AddReference(thermo_c)

    # ✅ INIT AUTOMATION
    from DWSIM.Automation import Automation3
    interf = Automation3()

    logging.info(
        "DWSIM ready.  Compounds: %d  Property packages: %d",
        len(interf.AvailableCompounds),
        len(interf.AvailablePropertyPackages),
    )

    # 🔥 DEBUG (IMPORTANT — KEEP THIS TEMPORARILY)
    logging.info("Available Property Packages:")
    for k in interf.AvailablePropertyPackages:
        logging.info(f"  - {k}")

    return interf

def write_csv_header():
    """Create results.csv and write the header row."""
    os.makedirs(os.path.dirname(RESULTS_CSV) or ".", exist_ok=True)
    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
    logging.info("results.csv created at %s", RESULTS_CSV)


def append_csv_row(row: dict):
    """
    Append one result row to results.csv.
    Any key not in CSV_FIELDNAMES is silently ignored.
    Missing keys are written as empty strings.
    """
    filled = {k: row.get(k, "") for k in CSV_FIELDNAMES}
    with open(RESULTS_CSV, "a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES)
        writer.writerow(filled)


# ── Timing helper ─────────────────────────────────────────────────────────────

class Timer:
    """Simple context-manager stopwatch.  Usage:  with Timer() as t: ..."""
    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_):
        self.elapsed = round(time.perf_counter() - self._start, 3)


# ── Final report ──────────────────────────────────────────────────────────────

def write_report(pfr_records: list, col_records: list, total_runtime: float):
    """
    Print a clean summary to the console and save it to simulation_report.txt.
    This gives evaluators an instant overview without opening the CSV.
    """
    pfr_ok  = [r for r in pfr_records if r.get("success_flag") == 1]
    pfr_bad = [r for r in pfr_records if r.get("success_flag") == 0]
    col_ok  = [r for r in col_records if r.get("success_flag") == 1]
    col_bad = [r for r in col_records if r.get("success_flag") == 0]

    best_pfr = max(pfr_ok, key=lambda r: r.get("conversion", 0), default=None)
    best_col = max(col_ok, key=lambda r: r.get("distillate_purity", 0), default=None)

    lines = [
        "=" * 60,
        "  DWSIM SCREENING TASK — SIMULATION SUMMARY",
        f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 60,
        "",
        "PFR (n-pentane isomerization)",
        f"  Cases run  : {len(pfr_records)}",
        f"  Successful : {len(pfr_ok)}",
        f"  Failed     : {len(pfr_bad)}",
    ]

    if best_pfr:
        conv_pct = round(best_pfr["conversion"] * 100, 2)
        lines.append(
            f"  Best conversion: {conv_pct}%  "
            f"(V={best_pfr['V']} m³, "
            f"T={best_pfr['T']} K)"
        )

    lines += [
        "",
        "Distillation column (n-C5 / i-C5 separation)",
        f"  Cases run  : {len(col_records)}",
        f"  Successful : {len(col_ok)}",
        f"  Failed     : {len(col_bad)}",
    ]

    if best_col:
        pur_pct = round(best_col["distillate_purity"] * 100, 2)
        lines.append(
            f"  Best distillate purity: {pur_pct}% i-C5  "
            f"(RR={best_col['RR']}, "
            f"N={best_col['N']} stages)"
        )

    lines += [
        "",
        f"Total simulation runtime : {round(total_runtime, 1)} s",
        f"Results file             : results.csv",
        f"Plots                    : plots/",
        f"Full log                 : simulation.log",
        "=" * 60,
    ]

    report_text = "\n".join(lines)
    print("\n" + report_text + "\n")

    with open(REPORT_FILE, "w", encoding="utf-8") as fh:
        fh.write(report_text + "\n")

    logging.info("Simulation report saved to %s", REPORT_FILE)
