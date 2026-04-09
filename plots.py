# plots.py
# Generates parametric trend plots from the collected simulation results.
# All charts are saved to the plots/ directory as high-resolution PNGs.
# This module is intentionally kept separate so the main script stays clean.

import os
import logging
import matplotlib
matplotlib.use("Agg")             # non-interactive backend — no display needed
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np
from config import PLOTS_DIR


def _ensure_dir():
    os.makedirs(PLOTS_DIR, exist_ok=True)


def _save(fig, filename: str):
    path = os.path.join(PLOTS_DIR, filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logging.info("Plot saved: %s", path)


# ── PFR plots ─────────────────────────────────────────────────────────────────

def pfr_conversion_vs_volume(records: list):
    """
    Conversion vs reactor volume — one line per temperature.
    """
    _ensure_dir()
    ok = [r for r in records if r.get("success_flag") == 1 and r.get("case_type") == "PFR"]
    if not ok:
        logging.warning("No successful PFR results — skipping conversion-vs-volume plot.")
        return

    temps = sorted(set(r["T"] for r in ok))
    cmap  = cm.get_cmap("plasma", len(temps))

    fig, ax = plt.subplots(figsize=(7, 4.5))

    for idx, temp in enumerate(temps):
        subset = sorted(
            [r for r in ok if r["T"] == temp],
            key=lambda r: r["V"],
        )
        vols  = [r["V"]   for r in subset]
        convs = [r["conversion"] * 100 for r in subset]
        ax.plot(vols, convs, marker="o", color=cmap(idx), label=f"{int(temp)} K", linewidth=1.8)

    ax.set_xlabel("Reactor Volume (m³)", fontsize=11)
    ax.set_ylabel("n-Pentane Conversion (%)", fontsize=11)
    ax.set_title("PFR — Conversion vs Reactor Volume", fontsize=12, fontweight="bold")
    ax.legend(title="Temperature", fontsize=9, title_fontsize=9)
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.set_ylim(0, 105)
    fig.tight_layout()
    _save(fig, "pfr_conversion_vs_volume.png")


def pfr_conversion_vs_temperature(records: list):
    """
    Conversion vs feed temperature — one line per reactor volume.
    """
    _ensure_dir()
    ok = [r for r in records if r.get("success_flag") == 1 and r.get("case_type") == "PFR"]
    if not ok:
        logging.warning("No successful PFR results — skipping conversion-vs-temp plot.")
        return

    vols = sorted(set(r["V"] for r in ok))
    cmap = cm.get_cmap("viridis", len(vols))

    fig, ax = plt.subplots(figsize=(7, 4.5))

    for idx, vol in enumerate(vols):
        subset = sorted(
            [r for r in ok if r["V"] == vol],
            key=lambda r: r["T"],
        )
        temps = [r["T"]    for r in subset]
        convs = [r["conversion"] * 100 for r in subset]
        ax.plot(temps, convs, marker="s", color=cmap(idx), label=f"{vol} m³", linewidth=1.8)

    ax.set_xlabel("Feed Temperature (K)", fontsize=11)
    ax.set_ylabel("n-Pentane Conversion (%)", fontsize=11)
    ax.set_title("PFR — Conversion vs Temperature", fontsize=12, fontweight="bold")
    ax.legend(title="Reactor Volume", fontsize=9, title_fontsize=9)
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.set_ylim(0, 105)
    fig.tight_layout()
    _save(fig, "pfr_conversion_vs_temperature.png")


# ── Distillation plots ────────────────────────────────────────────────────────

def col_purity_vs_reflux(records: list):
    """
    Distillate isopentane purity vs reflux ratio — one line per stage count.
    """
    _ensure_dir()
    ok = [r for r in records if r.get("success_flag") == 1 and r.get("case_type") == "Distillation"]
    if not ok:
        logging.warning("No successful column results — skipping purity-vs-reflux plot.")
        return

    stages = sorted(set(r["N"] for r in ok))
    cmap   = cm.get_cmap("cool", len(stages))

    fig, ax = plt.subplots(figsize=(7, 4.5))

    for idx, ns in enumerate(stages):
        subset = sorted(
            [r for r in ok if r["N"] == ns],
            key=lambda r: r["RR"],
        )
        rrs    = [r["RR"]            for r in subset]
        purs   = [r["distillate_purity"] * 100 for r in subset]
        ax.plot(rrs, purs, marker="D", color=cmap(idx), label=f"N={ns}", linewidth=1.8)

    ax.set_xlabel("Reflux Ratio (L/D)", fontsize=11)
    ax.set_ylabel("Distillate i-C5 Purity (mol%)", fontsize=11)
    ax.set_title("Distillation — Purity vs Reflux Ratio", fontsize=12, fontweight="bold")
    ax.legend(title="No. of stages", fontsize=9, title_fontsize=9)
    ax.grid(True, linestyle="--", alpha=0.4)
    fig.tight_layout()
    _save(fig, "col_purity_vs_reflux.png")


def col_duty_vs_stages(records: list):
    """
    Condenser and reboiler duty vs number of stages — one set of lines per
    reflux ratio (condenser = solid line, reboiler = dashed).
    """
    _ensure_dir()
    ok = [r for r in records if r.get("success_flag") == 1 and r.get("case_type") == "Distillation"]
    if not ok:
        logging.warning("No successful column results — skipping duty-vs-stages plot.")
        return

    rrs  = sorted(set(r["RR"] for r in ok))
    cmap = cm.get_cmap("autumn", len(rrs))

    fig, ax = plt.subplots(figsize=(7, 4.5))

    for idx, rr in enumerate(rrs):
        subset = sorted(
            [r for r in ok if r["RR"] == rr],
            key=lambda r: r["N"],
        )
        ns_vals = [r["N"]          for r in subset]
        cond    = [abs(r["condenser_duty"]) for r in subset]
        reb     = [r["reboiler_duty"]   for r in subset]

        color = cmap(idx)
        ax.plot(ns_vals, cond, color=color, linestyle="-",  linewidth=1.6,
                label=f"RR={rr} condenser")
        ax.plot(ns_vals, reb,  color=color, linestyle="--", linewidth=1.6,
                label=f"RR={rr} reboiler")

    ax.set_xlabel("Number of Stages", fontsize=11)
    ax.set_ylabel("|Duty| (kW)", fontsize=11)
    ax.set_title("Distillation — Column Duty vs Stages", fontsize=12, fontweight="bold")
    ax.legend(fontsize=7.5, ncol=2)
    ax.grid(True, linestyle="--", alpha=0.4)
    fig.tight_layout()
    _save(fig, "col_duty_vs_stages.png")


def generate_all(pfr_records: list, col_records: list):
    """
    Convenience wrapper — generate every plot in one call from run_screening.py.
    """
    logging.info("Generating plots...")
    pfr_conversion_vs_volume(pfr_records)
    pfr_conversion_vs_temperature(pfr_records)
    col_purity_vs_reflux(col_records)
    col_duty_vs_stages(col_records)
    logging.info("All plots saved to %s/", PLOTS_DIR)
