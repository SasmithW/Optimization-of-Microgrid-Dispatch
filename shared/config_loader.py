import os
import json

def get_config_path():
    current_dir = os.path.abspath(os.path.dirname(__file__))
    for _ in range(3):
        config_path = os.path.join(current_dir, "microgrid_config.json")
        if os.path.exists(config_path):
            return config_path
        current_dir = os.path.dirname(current_dir)
    return os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')), "microgrid_config.json")

def load_config():
    with open(get_config_path(), 'r') as f:
        return json.load(f)

def save_config(new_config):
    with open(get_config_path(), 'w') as f:
        json.dump(new_config, f, indent=4)

def get_data_paths():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    forecast_out = os.path.join(root_dir, 'energy_forecasting', 'outputs')
    realtime_out = os.path.join(root_dir, 'realtime_data', 'outputs')
    opt_out = os.path.join(root_dir, 'optimization', 'outputs')
    
    os.makedirs(forecast_out, exist_ok=True)
    os.makedirs(realtime_out, exist_ok=True)
    os.makedirs(opt_out, exist_ok=True)
    
    return {
        "energy_forecast": os.path.join(forecast_out, "energy_forecast.csv"),
        "actual_pv": os.path.join(realtime_out, "actual_pv.csv"),
        "actual_load": os.path.join(realtime_out, "actual_load.csv"),
        "day_ahead_schedule": os.path.join(opt_out, "day_ahead_schedule.csv"),
        "rule_based_schedule": os.path.join(opt_out, "rule_based_schedule.csv")
    }
    
def get_parameters():
    return load_config().get("parameters", {})

def get_tariff_vectors(prices=None, schedule=None, exp_pct=None):
    config = load_config()
    if prices is None: prices = config.get("tou_prices", {"Off-Peak": 0.12, "Mid-Peak": 0.22, "Peak": 0.36})
    if schedule is None: schedule = config.get("tou_schedule", [
        {"Period": "Off-Peak", "Start": "00:00", "End": "07:00"},
        {"Period": "Mid-Peak", "Start": "07:00", "End": "12:00"},
        {"Period": "Off-Peak", "Start": "12:00", "End": "16:00"},
        {"Period": "Peak", "Start": "16:00", "End": "22:00"},
        {"Period": "Mid-Peak", "Start": "22:00", "End": "24:00"}
    ])
    if exp_pct is None: exp_pct = float(config.get("export_percentage", 50.0)) / 100.0
    else: exp_pct = float(exp_pct) / 100.0
    
    G_b = [0.0]*24
    for entry in schedule:
        try:
            start = int(entry["Start"].split(":")[0])
            end = int(entry["End"].split(":")[0])
            period = entry["Period"]
            for h in range(start, end):
                if 0 <= h < 24:
                    G_b[h] = prices[period]
        except Exception:
            pass
            
    G_s = [val * exp_pct for val in G_b]
    return G_b, G_s
