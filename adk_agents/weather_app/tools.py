
import datetime
from zoneinfo import ZoneInfo

import requests

def _get_location_data(city: str) -> dict | None:
    """Fetches location data (lat, lon, timezone) for a city using Open-Meteo Geocoding API."""
    try:
        url = "https://geocoding-api.open-meteo.com/v1/search"
        params = {"name": city, "count": 1, "language": "en", "format": "json"}
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        if not data.get("results"):
            return None
        result = data["results"][0]
        return {
            "latitude": result["latitude"],
            "longitude": result["longitude"],
            "timezone": result.get("timezone")
        }
    except Exception as e:
        print(f"Error fetching location data: {e}")
        return None

def _get_wmo_description(code: int) -> str:
    """Maps WMO weather codes to human-readable descriptions."""
    # Codes from Open-Meteo docs
    if code == 0: return "Clear sky"
    if code in [1, 2, 3]: return "Mainly clear, partly cloudy, and overcast"
    if code in [45, 48]: return "Fog and depositing rime fog"
    if code in [51, 53, 55]: return "Drizzle: Light, moderate, and dense intensity"
    if code in [56, 57]: return "Freezing Drizzle: Light and dense intensity"
    if code in [61, 63, 65]: return "Rain: Slight, moderate and heavy intensity"
    if code in [66, 67]: return "Freezing Rain: Light and heavy intensity"
    if code in [71, 73, 75]: return "Snow fall: Slight, moderate, and heavy intensity"
    if code == 77: return "Snow grains"
    if code in [80, 81, 82]: return "Rain showers: Slight, moderate, and violent"
    if code in [85, 86]: return "Snow showers slight and heavy"
    if code == 95: return "Thunderstorm: Slight or moderate"
    if code in [96, 99]: return "Thunderstorm with slight and heavy hail"
    return "Unknown weather"

def get_weather(city: str) -> dict:
    """Retrieves the current weather report for a specified city.

    Args:
        city (str): The name of the city for which to retrieve the weather report.

    Returns:
        dict: status and result or error msg.
    """
    location = _get_location_data(city)
    if not location:
        return {
            "status": "error",
            "error_message": f"Could not find location data for city: '{city}'.",
        }
    
    lat = location["latitude"]
    lon = location["longitude"]
    
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,weather_code",
        }
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        current = data.get("current", {})
        temp = current.get("temperature_2m")
        code = current.get("weather_code")
        description = _get_wmo_description(code)
        
        report = (
            f"The weather in {city} is {description} with a temperature of {temp} degrees Celsius."
        )
        
        return {
            "status": "success",
            "report": report,
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Failed to fetch weather data: {str(e)}",
        }


def get_current_time(city: str) -> dict:
    """Returns the current time in a specified city.

    Args:
        city (str): The name of the city for which to retrieve the current time.

    Returns:
        dict: status and result or error msg.
    """
    location = _get_location_data(city)
    if not location:
        return {
            "status": "error",
            "error_message": f"Could not find location data for city: '{city}'.",
        }
    
    timezone_str = location.get("timezone")
    if not timezone_str:
         return {
            "status": "error",
            "error_message": f"Timezone information not found for city: '{city}'.",
        }

    try:
        tz = ZoneInfo(timezone_str)
        now = datetime.datetime.now(tz)
        report = (
            f'The current time in {city} is {now.strftime("%Y-%m-%d %H:%M:%S %Z%z")}'
        )
        return {"status": "success", "report": report}
    except Exception as e:
         return {
            "status": "error",
            "error_message": f"Failed to determine time: {str(e)}",
        }
