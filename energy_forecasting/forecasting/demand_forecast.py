# forecasting/demand_forecast.py

import pandas as pd
import numpy as np
from prophet import Prophet
import os

def generate_demand_forecast(
    historical_csv_path: str,
    forecast_start_time: pd.Timestamp
) -> dict:
    """
    Trains a Prophet model on historical demand data and generates a 24-hour forecast.
    
    Args:
        historical_csv_path (str): Path to the CSV containing 'timestamp' and 'demand_kw'.
        forecast_start_time (pd.Timestamp): The starting hour for the 24-hour forecast.
        
    Returns:
        dict: Containing 'dataframe', 'array', and 'list' representations of the hourly forecast.
    """
    
    if not os.path.exists(historical_csv_path):
        print(f"Error: Historical data file not found at {historical_csv_path}")
        zeros = np.zeros(24)
        return {"dataframe": pd.DataFrame({"demand_forecast_kw": zeros}), "array": zeros, "list": zeros.tolist()}
        
    try:
        # Read and preprocess historical data
        df = pd.read_csv(historical_csv_path)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Prophet requires columns to be named 'ds' (datestamp) and 'y' (value)
        prophet_df = df.rename(columns={'timestamp': 'ds', 'demand_kw': 'y'})
        
        # Initialize and train Prophet model
        # We assume hourly data, so we can disable daily seasonality if we have short data, 
        # but typically demand has strong daily seasonality.
        model = Prophet(daily_seasonality=True, yearly_seasonality=False, weekly_seasonality=True)
        model.fit(prophet_df)
        
        # Generate future dates for the forecast
        # We need 24 hours starting from forecast_start_time
        # Prophet doesn't support tz-aware datestamps.
        naive_start = forecast_start_time.tz_localize(None) if forecast_start_time.tzinfo else forecast_start_time
        future_dates = pd.date_range(
            start=naive_start, 
            periods=24, 
            freq='h'
        )
        future_df = pd.DataFrame({'ds': future_dates})
        
        # Make predictions
        forecast = model.predict(future_df)
        
        # Extract the relevant column ('yhat' is the predicted value)
        # Ensure non-negative demand
        forecast['yhat'] = forecast['yhat'].clip(lower=0)
        
        result_df = pd.DataFrame({
            'timestamp': forecast['ds'].dt.tz_localize('UTC') if forecast['ds'].dt.tz is None else forecast['ds'],
            'demand_forecast_kw': forecast['yhat']
        })
        
        # Extract as numpy array and list
        forecast_array = result_df['demand_forecast_kw'].to_numpy()
        forecast_list = forecast_array.tolist()
        
        return {
            "dataframe": result_df,
            "array": forecast_array,
            "list": forecast_list
        }
        
    except Exception as e:
        print(f"Error during demand forecasting: {e}")
        zeros = np.zeros(24)
        return {"dataframe": pd.DataFrame({"demand_forecast_kw": zeros}), "array": zeros, "list": zeros.tolist()}
