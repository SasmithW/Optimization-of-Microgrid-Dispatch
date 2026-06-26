import json
import os

SCENARIO_PARAMETERS = {
    "Base Case": {
        "description": "The default day-ahead forecast with no modifications. Uses the original PV and Load datasets.",
        "PV_FACTOR": 1.0,
        "LOAD_FACTOR": 1.0,
        "PEAK_TARIFF_FACTOR": 1.0,
        "INITIAL_SOC_FACTOR": 1.0
    },
    "Cloudy Day": {
        "description": "Simulates heavy cloud cover. PV generation is reduced by the specified factor.",
        "PV_FACTOR": 0.5,
        "LOAD_FACTOR": 1.0,
        "PEAK_TARIFF_FACTOR": 1.0,
        "INITIAL_SOC_FACTOR": 1.0
    },
    "Rainy Day": {
        "description": "Simulates a rainy day with very low PV generation and slightly higher load due to indoor activities/HVAC.",
        "PV_FACTOR": 0.2,
        "LOAD_FACTOR": 1.1,
        "PEAK_TARIFF_FACTOR": 1.0,
        "INITIAL_SOC_FACTOR": 1.0
    },
    "High Load Day": {
        "description": "Simulates an exceptionally hot or busy day where total energy demand increases significantly.",
        "PV_FACTOR": 1.0,
        "LOAD_FACTOR": 1.25,
        "PEAK_TARIFF_FACTOR": 1.0,
        "INITIAL_SOC_FACTOR": 1.0
    },
    "Low Load Day": {
        "description": "Simulates a weekend or holiday where energy demand is lower than normal.",
        "PV_FACTOR": 1.0,
        "LOAD_FACTOR": 0.75,
        "PEAK_TARIFF_FACTOR": 1.0,
        "INITIAL_SOC_FACTOR": 1.0
    },
    "Peak Demand Event": {
        "description": "Simulates an extreme load spike specifically during the evening peak hours (16:00 to 22:00).",
        "PV_FACTOR": 1.0,
        "LOAD_FACTOR": 1.0,
        "PEAK_TARIFF_FACTOR": 1.0,
        "INITIAL_SOC_FACTOR": 1.0,
        "EVENING_PEAK_FACTOR": 1.4,
        "EVENING_START": 16,
        "EVENING_END": 22
    },
    "High Tariff": {
        "description": "Simulates a grid stress event where peak grid import prices are multiplied.",
        "PV_FACTOR": 1.0,
        "LOAD_FACTOR": 1.0,
        "PEAK_TARIFF_FACTOR": 1.5,
        "INITIAL_SOC_FACTOR": 1.0
    },
    "Low Initial SOC": {
        "description": "Simulates starting the day with a depleted battery (closer to the minimum allowed SOC).",
        "PV_FACTOR": 1.0,
        "LOAD_FACTOR": 1.0,
        "PEAK_TARIFF_FACTOR": 1.0,
        "INITIAL_SOC_FACTOR": 0.25 # e.g. 25% of the original S_init
    }
}

def apply_scenario(D_forecast, S_av_forecast, G_b, G_s, params, scenario_name, timestamps, outputs_dir):
    """
    Applies deterministic modifications to the input arrays and parameters based on the selected scenario.
    Returns explicitly copied lists and dicts to ensure the original data remains strictly untouched.
    Generates scenario_summary.json.
    """
    if scenario_name not in SCENARIO_PARAMETERS:
        print(f"Warning: Scenario '{scenario_name}' not found. Defaulting to Base Case.")
        scenario_name = "Base Case"
        
    cfg = SCENARIO_PARAMETERS[scenario_name]
    
    # 1. Copy original data strictly
    D_mod = list(D_forecast)
    S_mod = list(S_av_forecast)
    Gb_mod = list(G_b)
    Gs_mod = list(G_s)
    params_mod = params.copy()
    
    # 2. Apply parameters
    if scenario_name != "Base Case":
        # PV
        if cfg.get("PV_FACTOR", 1.0) != 1.0:
            S_mod = [s * cfg["PV_FACTOR"] for s in S_mod]
            
        # Load
        if cfg.get("LOAD_FACTOR", 1.0) != 1.0:
            D_mod = [d * cfg["LOAD_FACTOR"] for d in D_mod]
            
        # Peak Demand Event specific load spike
        if "EVENING_PEAK_FACTOR" in cfg:
            start = cfg.get("EVENING_START", 16)
            end = cfg.get("EVENING_END", 22)
            for h in range(len(D_mod)):
                if h >= start and h < end:
                    D_mod[h] *= cfg["EVENING_PEAK_FACTOR"]
                    
        # Tariff
        if cfg.get("PEAK_TARIFF_FACTOR", 1.0) != 1.0:
            max_tariff = max(Gb_mod)
            for h in range(len(Gb_mod)):
                if Gb_mod[h] >= max_tariff * 0.95:
                    Gb_mod[h] *= cfg["PEAK_TARIFF_FACTOR"]
                    
        # Initial SOC
        if cfg.get("INITIAL_SOC_FACTOR", 1.0) != 1.0:
            params_mod['S_init'] = params_mod['S_init'] * cfg["INITIAL_SOC_FACTOR"]
            if params_mod['S_init'] < params_mod.get('S_min', 0):
                params_mod['S_init'] = params_mod.get('S_min', 0)

    # 3. Save Scenario Summary
    summary = {
        "Scenario Name": scenario_name,
        "Description": cfg.get("description", ""),
        "Applied Parameters": {k: v for k, v in cfg.items() if k != "description"}
    }
    
    summary_path = os.path.join(outputs_dir, "scenario_summary.json")
    try:
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=4)
    except Exception as e:
        print(f"Error writing scenario summary: {e}")
        
    return D_mod, S_mod, Gb_mod, Gs_mod, params_mod
