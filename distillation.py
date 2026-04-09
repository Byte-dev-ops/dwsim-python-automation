# distillation.py
# Simulates n-pentane / isopentane distillation via DWSIM Automation API.
#
# KEY FIXES (2026-04-09):
#
# 1. ISimulationObject interface: cast streams; use reflection for column methods.
#
# 2. Column specs via SetPropertyValue("Condenser_Specification_Type", ...) DO NOT
#    work — these are not the correct property keys for DWSIM's DistillationColumn.
#    The correct mechanism is to directly mutate the ColumnSpec objects in the
#    Specs dictionary (keys "C" = condenser, "R" = reboiler) via reflection.
#    ColumnSpec properties:
#      SType:      SpecType enum (Stream_Ratio=0 for RR, Product_Molar_Flow_Rate=2 for distillate)
#      SpecValue:  the numeric value (reflux ratio or molar flow in mol/s)
#      SpecUnit:   "mol/s" etc.
#
# 3. Stage pressures: set on the Stages list (stage[0]=condenser, stage[-1]=reboiler).
#
# 4. NumberOfStages must be set AND the column's CreateStages() method called to
#    resize the internal stage list BEFORE ConnectFeed, so feed_stage is valid.
#    Alternatively: set NumberOfStages then call the column's Initialize method.
#    Simpler approach used here: use ConnectFeed with stage=1 placeholder, then
#    resize stages explicitly by calling CreateStages via reflection.

import logging
from config import (
    COL_FEED_TEMP_K,
    COL_FEED_PRES_PA,
    COL_FEED_FLOW,
    COL_FEED_COMP,
    COL_DISTILLATE,
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
    return sim.SimulationObjects[go.Name]


def _get_material_stream(sim, go):
    from DWSIM.Interfaces import IMaterialStream
    return IMaterialStream(sim.SimulationObjects[go.Name])


def _get_energy_stream(sim, go):
    from DWSIM.Interfaces import IEnergyStream
    return IEnergyStream(sim.SimulationObjects[go.Name])


def _rget(obj, prop_name):
    """Reflection-based property getter."""
    prop = obj.GetType().GetProperty(prop_name)
    if prop is not None:
        return prop.GetValue(obj)
    raise AttributeError(f"Property '{prop_name}' not found on {obj.GetType().FullName}")


def _rset(obj, prop_name, value):
    """
    Reflection-based property setter.
    Boxes Python int→Int32 and float→Double explicitly to satisfy reflection.
    """
    from System import Int32, Double
    prop = obj.GetType().GetProperty(prop_name)
    if prop is not None:
        tn = prop.PropertyType.FullName
        if tn == "System.Int32":
            boxed = Int32(int(value))
        elif tn == "System.Double":
            boxed = Double(float(value))
        else:
            boxed = value
        prop.SetValue(obj, boxed)
        return
    raise AttributeError(f"Property '{prop_name}' not found on {obj.GetType().FullName}")


def _rcall(obj, method_name, *args):
    """
    Reflection-based method call. Boxes int/float per parameter type.
    Tries all overloads with matching parameter count.
    """
    from System import Array, Object as SysObject, Int32, Double

    def _box(val, param_info):
        tn = param_info.ParameterType.FullName
        if tn == "System.Int32":
            return Int32(int(val))
        if tn == "System.Double":
            return Double(float(val))
        return val

    typ     = obj.GetType()
    methods = [m for m in typ.GetMethods() if m.Name == method_name]
    if not methods:
        raise AttributeError(f"Method '{method_name}' not found on {typ.FullName}")

    last_exc = None
    for m in methods:
        params = list(m.GetParameters())
        if len(params) != len(args):
            continue
        try:
            arg_array = Array[SysObject](len(args))
            for i, (a, p) in enumerate(zip(args, params)):
                arg_array[i] = _box(a, p)
            return m.Invoke(obj, arg_array)
        except Exception as exc:
            last_exc = exc
            logging.debug("_rcall %s overload failed: %s", method_name, exc)

    raise RuntimeError(
        f"No matching overload for {method_name}({len(args)} args) "
        f"on {obj.GetType().FullName}. Last error: {last_exc}"
    )

# Removed _set_col_spec as it breaks internal solver references.


def System_Enum_ToObject(enum_type, int_val):
    """Convert an integer to the target .NET enum type via Enum.ToObject."""
    from System import Enum
    return Enum.ToObject(enum_type, int_val)


def _resize_column_stages(col, n_stages):
    """
    Use the column's SetNumberOfStages() method to resize the internal Stages list.

    Key insight: Setting the NumberOfStages *property* does NOT resize the internal
    Stages list. The SetNumberOfStages() *method* actually resizes it.
    ConnectFeed validates the feed stage index against Stages.Count, so the list
    must be the right size before ConnectFeed is called.
    """
    from System import Array, Object as SysObject, Int32
    typ     = col.GetType()
    methods = [m for m in typ.GetMethods() if m.Name == "SetNumberOfStages"]
    for m in methods:
        params = list(m.GetParameters())
        if len(params) == 1 and params[0].ParameterType.FullName == "System.Int32":
            arg_arr = Array[SysObject](1)
            arg_arr[0] = Int32(n_stages)
            m.Invoke(col, arg_arr)
            stages = col.GetType().GetProperty("Stages").GetValue(col)
            logging.debug("SetNumberOfStages(%d) -> Stages.Count=%d", n_stages, stages.Count)
            return
    # Fallback: property setter only (solver may still handle resize internally)
    _rset(col, "NumberOfStages", n_stages)
    logging.warning("SetNumberOfStages method not found; used property setter only")


# ── Main simulation function ───────────────────────────────────────────────────

def run_distillation(interf, n_stages: int, reflux_ratio: float) -> dict:
    from DWSIM.Interfaces.Enums.GraphicObjects import ObjectType

    # Feed stage: middle of column (1-indexed; stage 1=just below condenser)
    # Must be 1 <= feed_stage <= n_stages-2 (condenser=0, reboiler=n_stages-1)
    feed_stage = max(1, min(n_stages // 2, n_stages - 2))
    logging.debug("COL | N=%d  feed_stage=%d  RR=%.2f", n_stages, feed_stage, reflux_ratio)

    pp_key = _find_pp_key(interf)
    sim = interf.CreateFlowsheet()

    sim.AddCompound("n-Pentane")
    sim.AddCompound("Isopentane")
    sim.CreateAndAddPropertyPackage(pp_key)

    # ── Add objects ───────────────────────────────────────────────────────────
    go_feed = sim.AddObject(ObjectType.MaterialStream,      50,  300, "ColFeed")
    go_dist = sim.AddObject(ObjectType.MaterialStream,     550,  100, "Distillate")
    go_bot  = sim.AddObject(ObjectType.MaterialStream,     550,  500, "Bottoms")
    go_cond = sim.AddObject(ObjectType.EnergyStream,       300,   50, "CondenserDuty")
    go_reb  = sim.AddObject(ObjectType.EnergyStream,       300,  550, "ReboilerDuty")
    go_col  = sim.AddObject(ObjectType.DistillationColumn, 300,  300, "Column")

    # ── Cast streams ─────────────────────────────────────────────────────────
    m_feed = _get_material_stream(sim, go_feed)
    m_dist = _get_material_stream(sim, go_dist)
    m_bot  = _get_material_stream(sim, go_bot)
    e_cond = _get_energy_stream(sim, go_cond)
    e_reb  = _get_energy_stream(sim, go_reb)
    col    = _get_obj(sim, go_col)

    # ── Resize column to target stage count ───────────────────────────────────
    # Must happen BEFORE ConnectFeed so feed_stage index is valid.
    _resize_column_stages(col, n_stages)

    # ── Connect streams ───────────────────────────────────────────────────────
    _rcall(col, "ConnectDistillate",    m_dist)
    _rcall(col, "ConnectBottoms",       m_bot)
    _rcall(col, "ConnectCondenserDuty", e_cond)
    _rcall(col, "ConnectReboilerDuty",  e_reb)
    _rcall(col, "ConnectFeed",          m_feed, feed_stage)

    # ── Column specs via SetPropertyValue (Safe and handles side-effects) ─────
    distillate_mol_s = COL_DISTILLATE * 1000.0 / 3600.0  # kmol/h → mol/s
    col.SetPropertyValue("Condenser_Specification_Type", "Reflux Ratio")
    col.SetPropertyValue("Condenser_Specification_Value", float(reflux_ratio))
    col.SetPropertyValue("Reboiler_Specification_Type", "Distillate Flow Rate")
    col.SetPropertyValue("Reboiler_Specification_Value", float(distillate_mol_s))

    # ── Stage pressures ───────────────────────────────────────────────────────
    from System import Double
    stages = _rget(col, "Stages")
    for i in range(stages.Count):
        stage = stages[i]
        stage.GetType().GetProperty("P").SetValue(stage, Double(COL_FEED_PRES_PA))

    sim.AutoLayout()

    # ── Feed conditions ───────────────────────────────────────────────────────
    feed_mol_s = COL_FEED_FLOW * 1000.0 / 3600.0    # kmol/h → mol/s
    xnC5 = COL_FEED_COMP["n-Pentane"]
    xiC5 = COL_FEED_COMP["Isopentane"]
    m_feed.SetTemperature(COL_FEED_TEMP_K)
    m_feed.SetPressure(COL_FEED_PRES_PA)
    m_feed.SetMolarFlow(feed_mol_s)
    m_feed.SetOverallMolarComposition([xnC5, xiC5])

    # VERY IMPORTANT: Rebuild internal solver matrices for the new stage count
    # after stage pressures and feed compositions are set.
    _rcall(col, "ResetInitialEstimates")

    # ── Solve ─────────────────────────────────────────────────────────────────
    errors = interf.CalculateFlowsheet4(sim)
    if errors and len(errors) > 0:
        err_msgs = [str(e) for e in errors]
        for e in err_msgs:
            logging.debug("Solver: %s", e)
        # Raise error to fail the simulation case, instead of silently passing
        raise RuntimeError("Distillation Column solver failed: " + " | ".join(err_msgs))

    # Optional: also check the calculated flag
    is_calc = _rget(col, "Calculated")
    if not is_calc:
        msg = _rget(col, "ErrorMessage") or "Unknown error"
        raise RuntimeError(f"Column calculated flag is False. Error: {msg}")

    # ── Extract results ───────────────────────────────────────────────────────
    dist_comp = list(m_dist.GetOverallComposition())
    bot_comp  = list(m_bot.GetOverallComposition())

    dist_purity_iC5 = dist_comp[1]   # index 1 = Isopentane (added 2nd)
    bot_purity_nC5  = bot_comp[0]    # index 0 = n-Pentane  (added 1st)

    try:
        cond_duty_kW = float(_rget(col, "CondenserDuty")) / 1000.0
    except Exception:
        try:
            cond_duty_kW = float(e_cond.EnergyFlow) / 1000.0
        except Exception:
            cond_duty_kW = float("nan")

    try:
        reb_duty_kW = float(_rget(col, "ReboilerDuty")) / 1000.0
    except Exception:
        try:
            reb_duty_kW = float(e_reb.EnergyFlow) / 1000.0
        except Exception:
            reb_duty_kW = float("nan")

    logging.debug("COL done | dist_iC5=%.4f  bot_nC5=%.4f", dist_purity_iC5, bot_purity_nC5)

    return {
        "col_feed_stage":            feed_stage,
        "col_distillate_purity_iso": round(dist_purity_iC5, 6),
        "col_bottoms_purity_nC5":    round(bot_purity_nC5,  6),
        "col_condenser_duty_kW":     round(cond_duty_kW,    3),
        "col_reboiler_duty_kW":      round(reb_duty_kW,     3),
    }