import os
import sys

# Add shared module path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'shared')))
from config_loader import load_config, get_data_paths
from generate_actual_data import generate_actuals

def main():
    print("========================================")
    print(" REAL-TIME / ACTUAL DATA MODULE")
    print("========================================")
    
    config = load_config()
    paths = get_data_paths()
    
    outputs_dir = config["realtime_outputs_dir"]
    os.makedirs(outputs_dir, exist_ok=True)
    
    generate_actuals(paths["energy_forecast"], outputs_dir)
    print(f"Actual operational data saved to: {outputs_dir}")

if __name__ == "__main__":
    main()
