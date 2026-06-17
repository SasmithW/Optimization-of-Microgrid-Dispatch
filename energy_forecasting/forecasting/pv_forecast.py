# forecasting/pv_forecast.py

import pandas as pd
import numpy as np
import pvlib
from pvlib.pvsystem import PVSystem
from pvlib.location import Location
from pvlib.modelchain import ModelChain
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS

def generate_pv_forecast(
    weather_df: pd.DataFrame,
    lat: float,
    lon: float,
    capacity_kw: float = 250.0,
    efficiency: float = 0.20,
    tilt: float = 15.0,
    azimuth: float = 180.0,
    inverter_efficiency: float = 0.96
) -> dict:
    """
    Generates a 24-hour PV generation forecast based on weather data.
    
    Args:
        weather_df (pd.DataFrame): Weather DataFrame from open_meteo.py.
        lat (float): Latitude of the site.
        lon (float): Longitude of the site.
        capacity_kw (float): System capacity in kW.
        efficiency (float): Panel efficiency (0-1).
        tilt (float): Panel tilt angle in degrees.
        azimuth (float): Panel azimuth angle in degrees (180 is South).
        inverter_efficiency (float): Inverter efficiency (0-1).
        
    Returns:
        dict: Containing 'dataframe', 'array', and 'list' representations of the hourly forecast.
    """
    if weather_df.empty:
        print("Empty weather dataframe provided. Returning zeros.")
        zeros = np.zeros(24)
        return {"dataframe": pd.DataFrame({"pv_forecast_kw": zeros}), "array": zeros, "list": zeros.tolist()}

    # Set up PVlib Location
    site_location = Location(lat, lon)
    
    # Ensure the timestamp column is the index for PVlib
    weather_df = weather_df.set_index('timestamp')
    
    # We need DNI, DHI, and GHI for PVlib. 
    # Open-Meteo provides 'shortwave_radiation' which is GHI (Global Horizontal Irradiance).
    # We use pvlib's erbs model to estimate DNI and DHI from GHI.
    solpos = site_location.get_solarposition(weather_df.index)
    dni_extra = pvlib.irradiance.get_extra_radiation(weather_df.index)
    
    # Handle zeros in GHI
    ghi = weather_df['shortwave_radiation']
    
    # Calculate DNI and DHI
    erbs = pvlib.irradiance.erbs(ghi, solpos['zenith'], weather_df.index)
    
    # Construct pvlib weather DataFrame
    pv_weather = pd.DataFrame({
        'ghi': ghi,
        'dni': erbs['dni'],
        'dhi': erbs['dhi'],
        'temp_air': weather_df['temperature_2m'],
        'wind_speed': 0 # We didn't fetch wind speed, assuming 0 for simplicity
    })
    
    # Fill any NaNs created by erbs with 0
    pv_weather = pv_weather.fillna(0)

    # Calculate Plane of Array (POA) irradiance
    poa_irrad = pvlib.irradiance.get_total_irradiance(
        surface_tilt=tilt,
        surface_azimuth=azimuth,
        dni=pv_weather['dni'],
        ghi=pv_weather['ghi'],
        dhi=pv_weather['dhi'],
        solar_zenith=solpos['apparent_zenith'],
        solar_azimuth=solpos['azimuth']
    )
    
    # Calculate cell temperature
    temp_model_params = TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']
    cell_temp = pvlib.temperature.sapm_cell(
        poa_irrad['poa_global'],
        pv_weather['temp_air'],
        pv_weather['wind_speed'],
        **temp_model_params
    )
    
    # Calculate DC power generation (simplistic calculation based on area and efficiency)
    # Area calculation: Capacity (W) / (Standard Test Conditions Irradiance (1000 W/m2) * efficiency)
    capacity_w = capacity_kw * 1000
    total_area_m2 = capacity_w / (1000 * efficiency)
    
    # PV generation = POA Irradiance * Area * Efficiency
    # We add a simple temperature coefficient degradation
    gamma_pdc = -0.004 # -0.4% per degree C above 25
    temp_derate = 1 + gamma_pdc * (cell_temp - 25)
    
    dc_power_w = poa_irrad['poa_global'] * total_area_m2 * efficiency * temp_derate
    
    # Apply Inverter Efficiency and convert to kW
    ac_power_kw = (dc_power_w * inverter_efficiency) / 1000.0
    
    # Clip negative values to zero (nighttime)
    ac_power_kw = ac_power_kw.clip(lower=0)
    
    # Prepare outputs
    # Reset index to get timestamp back as a column
    result_df = ac_power_kw.to_frame(name='pv_forecast_kw').reset_index()
    
    # Extract as numpy array and list
    forecast_array = result_df['pv_forecast_kw'].to_numpy()
    forecast_list = forecast_array.tolist()
    
    return {
        "dataframe": result_df,
        "array": forecast_array,
        "list": forecast_list
    }
