# weather/open_meteo.py

import requests
import pandas as pd
from datetime import datetime, timedelta

def fetch_weather_forecast(lat: float, lon: float) -> pd.DataFrame:
    """
    Fetches the day-ahead hourly weather forecast from the Open-Meteo API.
    
    Args:
        lat (float): Latitude
        lon (float): Longitude
        
    Returns:
        pd.DataFrame: Hourly weather data containing temperature, cloud cover, 
                      shortwave radiation, and timestamp.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    
    # We request the next 24 hours of data. Open-Meteo defaults to the current day.
    # We specify forecast_days=2 to ensure we get a full day-ahead coverage.
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
    
    # Filter for the next 24 hours starting from the next full hour
    now = pd.Timestamp.now(tz='UTC').floor('h')
    start_time = now + pd.Timedelta(hours=1)
    end_time = start_time + pd.Timedelta(hours=23)
    
    # Make timezone-naive for simplicity if it has a timezone, or just localize if needed.
    # Open-Meteo returns naive timestamps in local timezone when timezone='auto'
    
    mask = (df['timestamp'] >= start_time) & (df['timestamp'] <= end_time)
    day_ahead_df = df.loc[mask].reset_index(drop=True)
    
    # Ensure exactly 24 hours (if available)
    return day_ahead_df.head(24)
