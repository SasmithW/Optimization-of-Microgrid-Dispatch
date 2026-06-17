import os
import sys
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'shared')))
from config_loader import load_config, get_data_paths, get_parameters, get_tariff_vectors
from optimizer import run_day_ahead_optimization
from rule_based import run_rule_based

def run_optimization_pipeline():
    paths = get_data_paths()
    params = get_parameters()
    
    outputs_dir = os.path.dirname(paths["day_ahead_schedule"])
    os.makedirs(outputs_dir, exist_ok=True)
    
    try:
        df = pd.read_csv(paths["energy_forecast"])
        pv_col = 'pv_forecast_kw' if 'pv_forecast_kw' in df.columns else df.columns[1]
        load_col = 'demand_forecast_kw' if 'demand_forecast_kw' in df.columns else df.columns[2]
        
        S_av_forecast = df[pv_col].tolist()
        D_forecast = df[load_col].tolist()
        timestamps = df.get('timestamp', df.index).tolist()
    except Exception as e:
        print(f"Could not load forecast data: {e}. Using fallback data.")
        D_forecast = [120]*24
        S_av_forecast = [0]*6 + [10, 40, 80, 150, 220, 270, 300, 310, 290, 250, 200, 130, 60] + [0]*5
        timestamps = [f"Hour_{i}" for i in range(1, 25)]

    G_b, G_s = get_tariff_vectors()
    
    # 1. Run MILP Optimization
    results_opt = run_day_ahead_optimization(D_forecast, S_av_forecast, G_b, G_s, params)
    
    # 2. Run Rule-Based EMS
    results_rule = run_rule_based(D_forecast, S_av_forecast, G_b, G_s, params)
    
    if results_opt['status'] == "Optimal":
        # Calculate Binding Constraints via Arrays
        C_g = float(params.get('C_g', 300.0))
        C_br = float(params.get('C_br', 200.0))
        C_bl = float(params.get('C_bl', 500.0))
        
        binding_status = {
            "Grid_Import_Limit": any(abs(qg - C_g) < 1e-4 for qg in results_opt['Qg']),
            "Grid_Export_Limit": any(abs(qge - C_g) < 1e-4 for qge in results_opt['Qge']),
            "Battery_Discharge_Limit": any(abs(qb - C_br) < 1e-4 for qb in results_opt['Qb']),
            "Battery_Charge_Limit": any(abs(qsb - C_br) < 1e-4 for qsb in results_opt['Qsb']),
            "SOC_Max_Limit": any(abs(s - C_bl) < 1e-4 for s in results_opt['S'])
        }
        
        summary = {
            "solver": results_opt["solver_info"],
            "binding_constraints": binding_status
        }
        
        import json
        summary_path = os.path.join(outputs_dir, "optimization_summary.json")
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=4)

        df_out_opt = pd.DataFrame({
            "Timestamp": timestamps,
            "Demand_Forecast_kW": D_forecast,
            "Solar_Forecast_kW": S_av_forecast,
            "Solar_Used_kW": [qs + qsb + qge for qs, qsb, qge in zip(results_opt['Qs'], results_opt['Qsb'], results_opt['Qge'])],
            "Bat_Charge_kW": results_opt['Qsb'],
            "Bat_Discharge_kW": results_opt['Qb'],
            "Grid_Import_kW": results_opt['Qg'],
            "Grid_Export_kW": results_opt['Qge'],
            "Scheduled_SOC_kWh": results_opt['S']
        })
        df_out_opt.to_csv(paths["day_ahead_schedule"], index=False)
        
        df_out_rule = pd.DataFrame({
            "Timestamp": timestamps,
            "Demand_Forecast_kW": D_forecast,
            "Solar_Forecast_kW": S_av_forecast,
            "Solar_Used_kW": [qs + qsb + qge for qs, qsb, qge in zip(results_rule['Qs'], results_rule['Qsb'], results_rule['Qge'])],
            "Bat_Charge_kW": results_rule['Qsb'],
            "Bat_Discharge_kW": results_rule['Qb'],
            "Grid_Import_kW": results_rule['Qg'],
            "Grid_Export_kW": results_rule['Qge'],
            "Scheduled_SOC_kWh": results_rule['S']
        })
        df_out_rule.to_csv(paths["rule_based_schedule"], index=False)
        
        print(f"Optimization Cost: ${results_opt['cost']:.2f}")
        print(f"Rule-Based Cost: ${results_rule['cost']:.2f}")
        
        return True, results_opt['cost']
    else:
        return False, results_opt['status']

if __name__ == "__main__":
    run_optimization_pipeline()
