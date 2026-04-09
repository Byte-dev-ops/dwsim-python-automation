"""
run_screening.py
================
Main entry point for the DWSIM Python Automation screening task.

What this script does
---------------------
1. Initialises the DWSIM Automation3 interface (no GUI opened).
2. Part A — runs a PFR simulation for n-pentane → isopentane isomerization.
3. Part B — runs a distillation column simulation for n-C5 / i-C5 separation.
4. Part C — performs a parametric sweep for both units (25 PFR cases,
            20 column cases) and logs every case to results.csv.
5. Generates four trend plots and a plain-text summary report.

Usage
-----
    python run_screening.py

All output lands in the same directory as this script:
    results.csv          — full results table
    simulation.log       — timestamped execution log
    simulation_report.txt — human-readable summary
    plots/               — four PNG charts
"""

import logging
import time
from datetime import datetime

# ── Project modules ───────────────────────────────────────────────────────────
# pythoncom must be initialised before DWSIM on Windows (COM threading model)
try:
    import pythoncom
    pythoncom.CoInitialize()
except ImportError:
    pass  # not on Windows or not needed

import utils
import pfr as pfr_module
import distillation as col_module
import plots as plot_module
from config import PFR_VOLUMES_M3, PFR_TEMPS_K, COL_REFLUX_RATIOS, COL_STAGE_COUNTS


# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _make_base_row(model_type: str) -> dict:
    """Return a dict pre-filled with metadata matching the exact CSV structure."""
    return {
        "case_type": model_type,
        "V": "",
        "T": "",
        "RR": "",
        "N": "",
        "conversion": "",
        "distillate_purity": "",
        "nC5_outlet_flow": "",
        "iC5_outlet_flow": "",
        "temperature_out": "",
        "condenser_duty": "",
        "reboiler_duty": "",
        "heat_duty": "",
        "success_flag": 0,
        "error_message": "",
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  Part A + C — PFR parametric sweep
# ═══════════════════════════════════════════════════════════════════════════════

def run_pfr_sweep(interf) -> list:
    """
    Sweep over all combinations of reactor volume and feed temperature.
    Returns a list of result dicts (one per case) for CSV writing and plotting.
    """
    records = []
    total   = len(PFR_VOLUMES_M3) * len(PFR_TEMPS_K)
    counter = 0

    logging.info("--- PFR sweep: %d cases (%d volumes x %d temperatures) ---",
                 total, len(PFR_VOLUMES_M3), len(PFR_TEMPS_K))

    for volume in PFR_VOLUMES_M3:
        for temp in PFR_TEMPS_K:
            counter += 1
            case_id = f"PFR_{counter:03d}"
            row = _make_base_row("PFR")
            row["V"] = volume
            row["T"] = temp

            print(f"  [{counter:02d}/{total}] PFR  V={volume} m3  T={temp} K", end="  ", flush=True)

            with utils.Timer() as t:
                try:
                    kpis = pfr_module.run_pfr(interf, volume, temp)
                    # Map the KPIs from pfr.py to the CSV exactly as requested
                    row["conversion"]      = kpis["pfr_conversion"]
                    row["nC5_outlet_flow"] = kpis["pfr_npentane_outlet_mol_h"]
                    row["iC5_outlet_flow"] = kpis["pfr_isopentane_outlet_mol_h"]
                    row["temperature_out"] = kpis["pfr_outlet_temp_K"]
                    row["heat_duty"]       = kpis["pfr_heat_duty_kW"]
                    
                    row["success_flag"] = 1
                    print(f"-> conv={kpis['pfr_conversion']*100:.1f}% | nC5={kpis['pfr_npentane_outlet_mol_h']:.1f} | iC5={kpis['pfr_isopentane_outlet_mol_h']:.1f} mol/h | duty={kpis['pfr_heat_duty_kW']:.0f} kW | T={kpis['pfr_outlet_temp_K']:.0f} K  OK")
                except Exception as exc:
                    row["success_flag"] = 0
                    row["error_message"] = str(exc)[:200]
                    print(f"-> FAILED: {exc}")
                    logging.error("PFR V=%r T=%r failed: %s", volume, temp, exc)

            row["runtime_s"] = t.elapsed
            utils.append_csv_row(row)
            records.append(row)

    ok_count = sum(1 for r in records if r["success_flag"] == 1)
    logging.info("PFR sweep complete — %d/%d successful.", ok_count, total)
    return records


# ═══════════════════════════════════════════════════════════════════════════════
#  Part B + C — Distillation parametric sweep
# ═══════════════════════════════════════════════════════════════════════════════

def run_col_sweep(interf) -> list:
    """
    Sweep over all combinations of reflux ratio and number of stages.
    Returns a list of result dicts.
    """
    records = []
    total   = len(COL_REFLUX_RATIOS) * len(COL_STAGE_COUNTS)
    counter = 0

    logging.info("--- Distillation sweep: %d cases (%d RRs x %d stage counts) ---",
                 total, len(COL_REFLUX_RATIOS), len(COL_STAGE_COUNTS))

    for rr in COL_REFLUX_RATIOS:
        for ns in COL_STAGE_COUNTS:
            counter += 1
            case_id = f"COL_{counter:03d}"
            row = _make_base_row("Distillation")
            row["RR"] = rr
            row["N"]  = ns

            print(f"  [{counter:02d}/{total}] COL  RR={rr}  N={ns} stages", end="  ", flush=True)

            with utils.Timer() as t:
                try:
                    kpis = col_module.run_distillation(interf, ns, rr)
                    # Map the KPIs from distillation.py to the CSV exactly
                    row["distillate_purity"] = kpis["col_distillate_purity_iso"]
                    row["condenser_duty"]    = kpis["col_condenser_duty_kW"]
                    row["reboiler_duty"]     = kpis["col_reboiler_duty_kW"]
                    
                    # Fill the rest of the flows so that they're visible if needed, but not necessarily swept
                    
                    row["success_flag"] = 1
                    purity_pct = kpis["col_distillate_purity_iso"] * 100
                    print(f"-> distillate i-C5={purity_pct:.1f}% | condenser={kpis['col_condenser_duty_kW']:.2f} kW | reboiler={kpis['col_reboiler_duty_kW']:.2f} kW  OK")
                except Exception as exc:
                    row["success_flag"] = 0
                    row["error_message"] = str(exc)[:200]
                    print(f"-> FAILED: {exc}")
                    logging.error("COL RR=%r N=%r failed: %s", rr, ns, exc)

            row["runtime_s"] = t.elapsed
            utils.append_csv_row(row)
            records.append(row)

    ok_count = sum(1 for r in records if r["success_flag"] == 1)
    logging.info("Distillation sweep complete — %d/%d successful.", ok_count, total)
    return records


# ═══════════════════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    wall_start = time.perf_counter()

    # ── Logging & CSV ─────────────────────────────────────────────────────────
    utils.setup_logging()
    utils.write_csv_header()

    logging.info("=" * 60)
    logging.info("DWSIM Screening Task — started %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    logging.info("=" * 60)

    # ── DWSIM initialisation ──────────────────────────────────────────────────
    try:
        interf = utils.init_dwsim()
    except RuntimeError as exc:
        logging.critical("Cannot start DWSIM: %s", exc)
        print(f"\nFATAL: {exc}\n")
        raise SystemExit(1)

    # ── PFR sweep ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 55)
    print("  PART A & C — PFR Parametric Sweep")
    print("=" * 55)
    pfr_records = run_pfr_sweep(interf)

    # ── Distillation sweep ────────────────────────────────────────────────────
    print("\n" + "=" * 55)
    print("  PART B & C — Distillation Column Parametric Sweep")
    print("=" * 55)
    col_records = run_col_sweep(interf)

    # ── Plots ─────────────────────────────────────────────────────────────────
    print("\nGenerating plots...", flush=True)
    plot_module.generate_all(pfr_records, col_records)

    # ── Summary report ────────────────────────────────────────────────────────
    total_runtime = time.perf_counter() - wall_start
    utils.write_report(pfr_records, col_records, total_runtime)


if __name__ == "__main__":
    main()
