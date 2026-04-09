# config.py
# All tunable parameters live here. If you need to change a sweep range,
# operating condition, or file path, this is the only file you touch.

import os

# ── DWSIM install path ────────────────────────────────────────────────────────
# Default installer puts DWSIM here on most Windows machines.
# Change if yours is different (check C:\Users\Public\ or C:\Program Files\).
DWSIM_PATH = r"E:\DWSIM"

# ── Output paths ──────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
RESULTS_CSV  = os.path.join(BASE_DIR, "results.csv")
PLOTS_DIR    = os.path.join(BASE_DIR, "plots")
LOG_FILE     = os.path.join(BASE_DIR, "simulation.log")
REPORT_FILE  = os.path.join(BASE_DIR, "simulation_report.txt")

# ── Shared feed conditions ─────────────────────────────────────────────────────
FEED_PRESSURE_PA = 101325.0   # Pa, atmospheric
FEED_MOLAR_FLOW  = 100.0      # kmol/h

# ── PFR kinetics — n-pentane → isopentane (liquid-phase, first-order Arrhenius)
# Ea and A consistent with published skeletal isomerization data.
PFR_PRE_EXP        = 1.2e8     # frequency factor, s⁻¹
PFR_ACT_ENERGY_J   = 65000.0   # activation energy, J/mol
PFR_RXORDER        = 1.0
PFR_ISOTHERMAL     = True

# ── PFR sweep grid  (5 × 5 = 25 cases) ───────────────────────────────────────
PFR_VOLUMES_M3     = [0.5, 1.0, 2.0, 5.0, 10.0]
PFR_TEMPS_K        = [350, 375, 400, 425, 450]

# ── Distillation feed ──────────────────────────────────────────────────────────
COL_FEED_COMP      = {"n-Pentane": 0.5, "Isopentane": 0.5}
COL_FEED_TEMP_K    = 310.0
COL_FEED_PRES_PA   = 202650.0   # 2 atm — enough to keep mixture liquid on feed
COL_FEED_FLOW      = 100.0      # kmol/h

# Fixed distillation specs (the two that do not sweep)
COL_CONDENSER      = "Total"
COL_DISTILLATE     = 50.0       # kmol/h — 4th spec alongside reflux ratio

# ── Distillation sweep grid  (5 × 4 = 20 cases) ──────────────────────────────
COL_REFLUX_RATIOS  = [1.2, 1.5, 2.0, 3.0, 4.0]
COL_STAGE_COUNTS   = [10, 15, 20, 25]
# Feed stage is always set to floor(N/2) inside distillation.py

CSV_FIELDNAMES = [
    "case_type",
    "V",
    "T",
    "RR",
    "N",
    "conversion",
    "distillate_purity",
    "nC5_outlet_flow",
    "iC5_outlet_flow",
    "temperature_out",
    "condenser_duty",
    "reboiler_duty",
    "heat_duty",
    "success_flag",
    "error_message"
]