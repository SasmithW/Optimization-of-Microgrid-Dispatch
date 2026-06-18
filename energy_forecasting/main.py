import os
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import argparse

# Import custom modules
from weather.open_meteo import fetch_weather_forecast
from forecasting.pv_forecast import generate_pv_forecast
from forecasting.demand_forecast import generate_demand_forecast

def generate_sample_historical_data(filepath: str):
    """Generates 30 days of synthetic hourly demand data for Prophet to train on."""
    if os.path.exists(filepath):
        return

    print("Generating sample historical demand data...")
    # 30 days of hourly data ending roughly now
    end_time = pd.Timestamp.now().floor('h')
    start_time = end_time - pd.Timedelta(days=30)
    
    dates = pd.date_range(start=start_time, end=end_time, freq='h')
    
    # Create a synthetic demand profile: base load + daily curve + some noise
    base_load = 50.0  # kW
    # A simple daily wave peaking around hour 18 (6 PM)
    daily_pattern = 30.0 * np.sin((dates.hour - 6) * np.pi / 12) 
    noise = np.random.normal(0, 5, len(dates))
    
    demand = base_load + daily_pattern + noise
    demand = np.clip(demand, a_min=10.0, a_max=None) # Ensure no negative/too low values
    
    df = pd.DataFrame({'timestamp': dates, 'demand_kw': demand})
    df.to_csv(filepath, index=False)
    print(f"Sample data created at {filepath}")

def main(target_date=None):
    # --- CONFIGURATION ---
    # Location (Default: Example Microgrid in a small town - arbitrary coordinates)
    # Using slightly sunny coordinates (e.g., somewhere in Spain/Italy) to show good PV curve
    LATITUDE = 6.9271
    LONGITUDE = 79.8612
    
    # PV System Parameters
    PV_CAPACITY_KW = 250.0
    PV_EFFICIENCY = 0.20
    PV_TILT = 15.0
    PV_AZIMUTH = 180.0
    INVERTER_EFFICIENCY = 0.96
    
    # Paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    OUTPUTS_DIR = os.path.join(BASE_DIR, 'outputs')
    HISTORICAL_DATA_PATH = os.path.join(DATA_DIR, 'sample_historical_demand.csv')
    
    # 1. Setup Data
    generate_sample_historical_data(HISTORICAL_DATA_PATH)
    
    # 2. Fetch Weather Data
    print(f"\nFetching weather data for Lat: {LATITUDE}, Lon: {LONGITUDE}...")
    weather_df = fetch_weather_forecast(lat=LATITUDE, lon=LONGITUDE, start_date=target_date)
    
    if weather_df.empty:
        print("Failed to fetch weather data. Exiting.")
        return
        
    forecast_start_time = weather_df['timestamp'].iloc[0]
    print(f"Forecast period: {forecast_start_time} to {weather_df['timestamp'].iloc[-1]}")

    # 3. Generate PV Forecast
    print("\nGenerating PV generation forecast...")
    pv_results = generate_pv_forecast(
        weather_df=weather_df,
        lat=LATITUDE,
        lon=LONGITUDE,
        capacity_kw=PV_CAPACITY_KW,
        efficiency=PV_EFFICIENCY,
        tilt=PV_TILT,
        azimuth=PV_AZIMUTH,
        inverter_efficiency=INVERTER_EFFICIENCY
    )
    
    # 4. Generate Demand Forecast
    print("Generating electricity demand forecast using Prophet...")
    demand_results = generate_demand_forecast(
        historical_csv_path=HISTORICAL_DATA_PATH,
        forecast_start_time=forecast_start_time
    )
    
    # --- OUTPUT GENERATION ---
    
    # Convert UTC timestamps to Sri Lanka Local Time (Asia/Colombo) before exporting
    weather_df['timestamp'] = weather_df['timestamp'].dt.tz_convert('Asia/Colombo').dt.tz_localize(None)
    # Note: forecast_start_time is used in JSON
    forecast_start_time = forecast_start_time.tz_convert('Asia/Colombo').tz_localize(None)
    
    # Combine into a single DataFrame for easy CSV export
    combined_df = pd.DataFrame({
        'timestamp': weather_df['timestamp'],
        'pv_forecast_kw': pv_results['array'],
        'demand_forecast_kw': demand_results['array']
    })
    
    # Export CSVs
    combined_csv_path = os.path.join(OUTPUTS_DIR, 'energy_forecast.csv')
    combined_df.to_csv(combined_csv_path, index=False)
    print(f"\nSaved CSV forecast to {combined_csv_path}")
    
    # Export JSONs
    # Convert timestamps to string for JSON serialization
    json_data = {
        "metadata": {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "pv_capacity_kw": PV_CAPACITY_KW,
            "start_time": str(forecast_start_time)
        },
        "forecasts": {
            "timestamps": combined_df['timestamp'].astype(str).tolist(),
            "pv_generation_kw": pv_results['list'],
            "demand_kw": demand_results['list']
        }
    }
    
    json_path = os.path.join(OUTPUTS_DIR, 'energy_forecast.json')
    with open(json_path, 'w') as f:
        json.dump(json_data, f, indent=4)
    print(f"Saved JSON forecast to {json_path}")
    
    # Print formatted arrays for PuLP
    print("\n" + "="*50)
    print(" READY FOR PULP OPTIMIZATION MODEL ")
    print("="*50)
    print("\n# Copy these arrays into your PuLP model script")
    print(f"pv_forecast = {np.round(pv_results['array'], 2).tolist()}")
    print(f"demand_forecast = {np.round(demand_results['array'], 2).tolist()}")
    print("="*50 + "\n")
    
    # --- VISUALIZATION ---
    print("Generating plots...")
    plt.figure(figsize=(12, 6))
    
    plt.plot(combined_df['timestamp'], combined_df['demand_forecast_kw'], 
             label='Demand Forecast (kW)', color='red', linewidth=2)
             
    plt.plot(combined_df['timestamp'], combined_df['pv_forecast_kw'], 
             label='PV Generation Forecast (kW)', color='orange', linewidth=2)
             
    # Shade the area where PV generation exceeds demand (surplus)
    plt.fill_between(combined_df['timestamp'], 
                     combined_df['demand_forecast_kw'], 
                     combined_df['pv_forecast_kw'], 
                     where=(combined_df['pv_forecast_kw'] > combined_df['demand_forecast_kw']),
                     interpolate=True, color='green', alpha=0.3, label='Potential Battery Charge / Grid Export')
                     
    # Shade area where demand exceeds PV (deficit)
    plt.fill_between(combined_df['timestamp'], 
                     combined_df['pv_forecast_kw'], 
                     combined_df['demand_forecast_kw'], 
                     where=(combined_df['demand_forecast_kw'] > combined_df['pv_forecast_kw']),
                     interpolate=True, color='red', alpha=0.1, label='Potential Battery Discharge / Grid Import')

    plt.title('24-Hour Day-Ahead Energy Forecast for Microgrid')
    plt.xlabel('Time')
    plt.ylabel('Power (kW)')
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    plot_path = os.path.join(OUTPUTS_DIR, 'forecast_plot.png')
    plt.savefig(plot_path, dpi=300)
    print(f"Saved plot to {plot_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Energy Forecasting Pipeline")
    parser.add_argument("--date", type=str, default=None, help="Target simulation date in YYYY-MM-DD format (Historical)")
    args = parser.parse_args()
    main(target_date=args.date)
