import pandas as pd
import numpy as np
import os

def generate_actuals(forecast_path, outputs_dir):
    if not os.path.exists(forecast_path):
        print(f"Warning: Forecast file not found at {forecast_path}. Generating dummy data.")
        # Match forecasting timezone logic: UTC + 1 hour -> Asia/Colombo -> Naive
        start_utc = pd.Timestamp.now(tz='UTC').floor('h') + pd.Timedelta(hours=1)
        start_local = start_utc.tz_convert('Asia/Colombo').tz_localize(None)
        timestamps = pd.date_range(start=start_local, periods=24, freq='h')
        forecast_pv = np.array([0]*6 + [10, 40, 80, 150, 220, 270, 300, 310, 290, 250, 200, 130, 60] + [0]*5)
        forecast_load = np.array([120]*24)
    else:
        df = pd.read_csv(forecast_path)
        timestamps = df['timestamp'].tolist() if 'timestamp' in df.columns else df.iloc[:, 0].tolist()
        # Get the PV and Load columns, handling variations in column names
        pv_col = 'pv_forecast_kw' if 'pv_forecast_kw' in df.columns else df.columns[1]
        load_col = 'demand_forecast_kw' if 'demand_forecast_kw' in df.columns else df.columns[2]
        
        forecast_pv = df[pv_col].values
        forecast_load = df[load_col].values
        
    np.random.seed(42) # For reproducible "actuals"
    
    # Introduce some noise to simulate actual physical deviations
    actual_pv = forecast_pv * np.random.uniform(0.7, 1.1, size=len(forecast_pv))
    actual_pv = np.clip(actual_pv, 0, None)
    
    actual_load = forecast_load * np.random.uniform(0.9, 1.25, size=len(forecast_load))
    
    df_pv = pd.DataFrame({'Hour': range(1, len(timestamps)+1), 'Timestamp': timestamps, 'Actual_PV': actual_pv.round(2)})
    df_load = pd.DataFrame({'Hour': range(1, len(timestamps)+1), 'Timestamp': timestamps, 'Actual_Load': actual_load.round(2)})
    
    os.makedirs(outputs_dir, exist_ok=True)
    df_pv.to_csv(os.path.join(outputs_dir, 'actual_pv.csv'), index=False)
    df_load.to_csv(os.path.join(outputs_dir, 'actual_load.csv'), index=False)
    print("Generated actual_pv.csv and actual_load.csv")
