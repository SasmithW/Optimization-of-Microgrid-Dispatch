# weather/open_meteo.py

import requests
import pandas as pd
from datetime import datetime, timedelta

def fetch_weather_forecast(lat: float, lon: float, start_date: str = None) -> pd.DataFrame:
    """
    Fetches the day-ahead hourly weather forecast from the Open-Meteo API.
    If start_date is provided (YYYY-MM-DD), fetches historical data for that day.
    
    Args:
        lat (float): Latitude
        lon (float): Longitude
        start_date (str, optional): Target simulation date in YYYY-MM-DD format.
        
    Returns:
        pd.DataFrame: Hourly weather data containing temperature, cloud cover, 
                      shortwave radiation, and timestamp.
    """
    if start_date:
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,cloudcover,shortwave_radiation",
            "timezone": "UTC",
            "start_date": start_date,
            "end_date": start_date
        }
    else:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m,cloudcover,shortwave_radiation",
            "timezone": "UTC",
            "forecast_days": 2
        }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from Open-Meteo: {e}")
        return pd.DataFrame()

    # Extract hourly data
    hourly_data = data.get("hourly", {})
    
    # Create DataFrame
    df = pd.DataFrame({
        "timestamp": pd.to_datetime(hourly_data.get("time")).tz_localize("UTC"),
        "temperature_2m": hourly_data.get("temperature_2m"),
        "cloudcover": hourly_data.get("cloudcover"),
        "shortwave_radiation": hourly_data.get("shortwave_radiation")
    })
    
    # Filter for the correct 24-hour window
    if start_date:
        # If historical, return exactly that day from 00:00 to 23:00
        target = pd.to_datetime(start_date).tz_localize("UTC")
        end_target = target + pd.Timedelta(hours=23)
        mask = (df['timestamp'] >= target) & (df['timestamp'] <= end_target)
    else:
        # If real-time, filter for the next 24 hours starting from the next full hour
        now = pd.Timestamp.now(tz='UTC').floor('h')
        start_time = now + pd.Timedelta(hours=1)
        end_time = start_time + pd.Timedelta(hours=23)
        mask = (df['timestamp'] >= start_time) & (df['timestamp'] <= end_time)
        
    day_ahead_df = df.loc[mask].reset_index(drop=True)
    
    # Ensure exactly 24 hours (if available)
    return day_ahead_df.head(24)
