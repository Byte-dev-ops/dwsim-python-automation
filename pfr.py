# pfr.py
# Simulates n-pentane → isopentane isomerization in a PFR.
#
# KEY FIXES (2026-04-09):
#
# 1. ISimulationObject interface: AddObject() returns ISimulationObject which
#    does NOT expose stream-specific methods (SetTemperature, etc.) or reactor-
#    specific properties (Volume, ReactionSetID, etc.).
#    Solution: cast material/energy streams; use reflection for PFR props.
#
# 2. ReactionSetID was NEVER set on the PFR — this is why conversion = 0.0%.
#    The PFR must be explicitly told which reaction set to use via:
#       _rset(pfr, "ReactionSetID", "DefaultSet")
#    Without this the kinetic reactions are ignored and no conversion occurs.
#
# 3. ReactorSizingType: Using SizingType.Length requires Length AND Diameter.
#    Change to SizingType.Volume (0) so the Volume property is used directly.
#
# 4. Feed stream: SetMolarFlow() + SetOverallMolarComposition() is correct API.
#    Python lists are implicitly converted to .NET Double[] by pythonnet.

import logging
from config import (
    FEED_PRESSURE_PA,
    FEED_MOLAR_FLOW,
    PFR_PRE_EXP,
    PFR_ACT_ENERGY_J,
    PFR_RXORDER,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_pp_key(interf):
    keys = list(interf.AvailablePropertyPackages.Keys)
    for c in ["Peng-Robinson (PR)", "Peng-Robinson", "Peng-Robinson 1978 (PR78)"]:
        if c in keys:
            return c
    for k in keys:
        if "peng" in k.lower():
            return k
    raise RuntimeError(f"No Peng-Robinson package found. Available: {keys}")


def _get_obj(sim, go):
    """Raw ISimulationObject — for unit operations accessed via reflection."""
    return sim.SimulationObjects[go.Name]


def _get_material_stream(sim, go):
    """Return object properly typed as IMaterialStream."""
    from DWSIM.Interfaces import IMaterialStream
    return IMaterialStream(sim.SimulationObjects[go.Name])


def _get_energy_stream(sim, go):
    """Return object properly typed as IEnergyStream."""
    from DWSIM.Interfaces import IEnergyStream
    return IEnergyStream(sim.SimulationObjects[go.Name])


def _rget(obj, prop_name):
    """Reflection-based property getter — reads from the concrete class."""
    prop = obj.GetType().GetProperty(prop_name)
    if prop is not None:
        return prop.GetValue(obj)
    raise AttributeError(
        f"Property '{prop_name}' not found on {obj.GetType().FullName}"
    )


def _rset(obj, prop_name, value):
    """
    Reflection-based property setter — writes to the concrete class.

    Handles:
    - Python int   → System.Int32
    - Python float → System.Double
    - Python int for .NET Enum → Enum.ToObject(enum_type, int_val)
    - All other types (enum objects, strings, bools) → passed as-is
    """
    from System import Int32, Double, Enum
    prop = obj.GetType().GetProperty(prop_name)
    if prop is not None:
        prop_type = prop.PropertyType
        tn = prop_type.FullName
        if tn == "System.Int32":
            boxed = Int32(int(value))
        elif tn == "System.Double":
            boxed = Double(float(value))
        elif prop_type.IsEnum and isinstance(value, int):
            # Python int passed for a .NET enum: convert via Enum.ToObject
            boxed = Enum.ToObject(prop_type, value)
        else:
            boxed = value      # enum objects, strings, bools — pass as-is
        prop.SetValue(obj, boxed)
        return
    raise AttributeError(
        f"Property '{prop_name}' not found on {obj.GetType().FullName}"
    )


# ── Main simulation function ───────────────────────────────────────────────────

def run_pfr(interf, volume_m3: float, feed_temp_K: float) -> dict:
    from System.Collections.Generic import Dictionary
    from DWSIM.Interfaces.Enums.GraphicObjects import ObjectType
    from DWSIM.UnitOperations import Reactors

    logging.debug("PFR | V=%.2f m3  T=%.0f K", volume_m3, feed_temp_K)

    pp_key = _find_pp_key(interf)
    sim = interf.CreateFlowsheet()

    sim.AddCompound("n-Pentane")
    sim.AddCompound("Isopentane")

    # ── Kinetic reaction ──────────────────────────────────────────────────────
    # n-Pentane → Isopentane (liquid-phase skeletal isomerization, first-order)
    stoich = Dictionary[str, float]()
    stoich["n-Pentane"]  = -1.0
    stoich["Isopentane"] =  1.0

    d_ord = Dictionary[str, float]()
    d_ord["n-Pentane"]  = float(PFR_RXORDER)
    d_ord["Isopentane"] = 0.0

    r_ord = Dictionary[str, float]()
    r_ord["n-Pentane"]  = 0.0
    r_ord["Isopentane"] = 0.0

    kr = sim.CreateKineticReaction(
        "nC5_to_iC5", "n-Pentane skeletal isomerisation",
        stoich, d_ord, r_ord,
        "n-Pentane", "Vapor",          # n-pentane is vapor at 350-450K / 1 atm
        "Molar Concentration", "kmol/m3", "kmol/[m3.s]",
        PFR_PRE_EXP, PFR_ACT_ENERGY_J,
        0.0, 0.0, "", "",
    )
    sim.AddReaction(kr)
    sim.AddReactionToSet(kr.ID, "DefaultSet", True, 0)

    sim.CreateAndAddPropertyPackage(pp_key)

    # ── Add objects ───────────────────────────────────────────────────────────
    go_feed = sim.AddObject(ObjectType.MaterialStream, 50,  150, "Feed")
    go_out  = sim.AddObject(ObjectType.MaterialStream, 550, 150, "Outlet")
    go_heat = sim.AddObject(ObjectType.EnergyStream,   300, 300, "HeatDuty")
    go_pfr  = sim.AddObject(ObjectType.RCT_PFR,        300, 150, "PFR_Reactor")

    # ── Cast streams to their proper interface types ───────────────────────────
    m_feed = _get_material_stream(sim, go_feed)
    m_out  = _get_material_stream(sim, go_out)
    e_heat = _get_energy_stream(sim, go_heat)

    # PFR stays as ISimulationObject; reactor-specific props via reflection.
    pfr = _get_obj(sim, go_pfr)

    # ── Connect streams ───────────────────────────────────────────────────────
    pfr.ConnectFeedMaterialStream(m_feed, 0)
    pfr.ConnectProductMaterialStream(m_out, 0)
    pfr.ConnectFeedEnergyStream(e_heat, 1)

    # ── PFR settings via reflection ───────────────────────────────────────────
    # FIX: ReactionSetID — THE ROOT CAUSE of 0% conversion.
    # Without this the PFR finds no reactions and conversion = 0 always.
    _rset(pfr, "ReactionSetID", "DefaultSet")

    # Operation mode: Isothermic
    _rset(pfr, "ReactorOperationMode", Reactors.OperationMode.Isothermic)
    _rset(pfr, "OutletTemperature",    float(feed_temp_K))

    # FIX: SizingType enum has only 'Length'(0) and 'Diameter'(1) — NO 'Volume' member.
    # Use Length-based sizing: compute L from volume using multiple tubes.
    # V = NumberOfTubes * (pi/4) * d^2 * L  =>  L = 4*V / (N_tubes * pi * d^2)
    # Using N_tubes=100, d=0.05m gives L ~ 5.1m per tube for V=0.5m3 - acceptable.
    import math
    n_tubes = 100
    tube_d  = 0.05    # m
    tube_l  = 4.0 * volume_m3 / (n_tubes * math.pi * tube_d ** 2)
    _rset(pfr, "Volume",        float(volume_m3))
    _rset(pfr, "Length",        float(tube_l))
    _rset(pfr, "Diameter",      float(tube_d))
    _rset(pfr, "NumberOfTubes", n_tubes)
    # SizingType: leave as default Length — no Volume enum member exists

    sim.AutoLayout()

    # ── Feed conditions ───────────────────────────────────────────────────────
    # IMaterialStream API: SetMolarFlow (total mol/s) + SetOverallMolarComposition.
    # Compounds added in order: [n-Pentane index=0, Isopentane index=1].
    feed_mol_s = FEED_MOLAR_FLOW * 1000.0 / 3600.0   # kmol/h → mol/s
    m_feed.SetTemperature(feed_temp_K)
    m_feed.SetPressure(FEED_PRESSURE_PA)
    m_feed.SetMolarFlow(feed_mol_s)
    m_feed.SetOverallMolarComposition([1.0, 0.0])     # pure n-Pentane feed

    # ── Solve ─────────────────────────────────────────────────────────────────
    errors = interf.CalculateFlowsheet4(sim)
    if errors and len(errors) > 0:
        for e in errors:
            logging.debug("Solver error: %s", str(e))

    # ── Extract results ───────────────────────────────────────────────────────
    conversion = 0.0
    try:
        comp_conv = _rget(pfr, "ComponentConversions")
        if comp_conv and "n-Pentane" in comp_conv:
            conversion = float(comp_conv["n-Pentane"])
    except Exception as exc:
        logging.debug("ComponentConversions read failed: %s", exc)
    conversion = max(0.0, min(1.0, conversion))

    out_comp      = list(m_out.GetOverallComposition())
    out_total_ms  = m_out.GetMolarFlow() * 1000.0         # mol/s
    nC5_out_mol_h = out_comp[0] * out_total_ms * 3600.0   # mol/h
    iC5_out_mol_h = out_comp[1] * out_total_ms * 3600.0
    outlet_temp_K = m_out.GetTemperature()

    try:
        heat_duty_kW = float(_rget(pfr, "DeltaQ"))
    except Exception:
        heat_duty_kW = 0.0

    logging.debug("PFR done | conv=%.4f  iC5=%.1f mol/h", conversion, iC5_out_mol_h)

    return {
        "pfr_conversion":              round(conversion,      6),
        "pfr_npentane_outlet_mol_h":   round(nC5_out_mol_h,  3),
        "pfr_isopentane_outlet_mol_h": round(iC5_out_mol_h,  3),
        "pfr_outlet_temp_K":           round(outlet_temp_K,  3),
        "pfr_heat_duty_kW":            round(heat_duty_kW,   4),
    }