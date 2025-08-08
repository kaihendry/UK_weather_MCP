import os
from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("UK_weather")

# Constants
MET_OFFICE_API_BASE = "https://data.hub.api.metoffice.gov.uk/sitespecific/v0/point"
MET_OFFICE_API_KEY = os.getenv("MET_OFFICE_API_KEY")

if not MET_OFFICE_API_KEY:
    raise ValueError(
        "MET_OFFICE_API_KEY environment variable not set. Please set it in your .bashrc or similar."
    )

# Weather code lookup table
WEATHER_CODES = {
    "NA": "Not available",
    0: "Clear night",
    1: "Sunny day",
    2: "Partly cloudy (night)",
    3: "Partly cloudy (day)",
    4: "Not used",
    5: "Mist",
    6: "Fog",
    7: "Cloudy",
    8: "Overcast",
    9: "Light rain shower (night)",
    10: "Light rain shower (day)",
    11: "Drizzle",
    12: "Light rain",
    13: "Heavy rain shower (night)",
    14: "Heavy rain shower (day)",
    15: "Heavy rain",
    16: "Sleet shower (night)",
    17: "Sleet shower (day)",
    18: "Sleet",
    19: "Hail shower (night)",
    20: "Hail shower (day)",
    21: "Hail",
    22: "Light snow shower (night)",
    23: "Light snow shower (day)",
    24: "Light snow",
    25: "Heavy snow shower (night)",
    26: "Heavy snow shower (day)",
    27: "Heavy snow",
    28: "Thunder shower (night)",
    29: "Thunder shower (day)",
    30: "Thunder",
}


def get_weather_description(code: Any) -> str:
    """Returns the human-readable description for a given weather code."""
    try:
        return WEATHER_CODES.get(int(code), f"Unknown code: {code}")
    except (ValueError, TypeError):
        return WEATHER_CODES.get(str(code), f"Unknown code: {code}")


async def make_met_office_request(
    url: str, params: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """Make a request to the Met Office API with proper error handling."""
    headers = {"accept": "application/json", "apikey": MET_OFFICE_API_KEY}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                url, headers=headers, params=params, timeout=30.0
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            print(f"An error occurred: {e}")
            return None


@mcp.tool()
async def get_hourly_forecast(latitude: float, longitude: float) -> str:
    """Get the hourly weather forecast for a location in the UK.

    Args:
        latitude: Latitude of the location.
        longitude: Longitude of the location.
    """
    url = f"{MET_OFFICE_API_BASE}/hourly"
    # https://datahub.metoffice.gov.uk/docs/f/category/site-specific/type/site-specific/api-documentation#get-/point/hourly
    # The request data source must be BD1.
    params = {
        "dataSource": "BD1",
        "latitude": latitude,
        "longitude": longitude,
        "includeLocationName": "true",
    }
    data = await make_met_office_request(url, params=params)

    if not data:
        return "Unable to fetch forecast data for this location."

    try:
        # Extract time series and location from the response
        time_series = data["features"][0]["properties"]["timeSeries"]
        coordinates = data["features"][0]["geometry"]["coordinates"]
        location_info = f"Location: {coordinates[1]:.4f}°N, {coordinates[0]:.4f}°E"

        forecasts = [f"Hourly forecast for {location_info}:"]
        
        for period in time_series:
            # Parse the hourly data fields
            time = period["time"]
            temp = period.get("screenTemperature", "N/A")
            feels_like = period.get("feelsLikeTemperature", "N/A")
            humidity = period.get("screenRelativeHumidity", "N/A")
            wind_speed = period.get("windSpeed10m", "N/A")
            wind_direction = period.get("windDirectionFrom10m", "N/A")
            weather_code = period.get("significantWeatherCode", "NA")
            precipitation_rate = period.get("precipitationRate", "N/A")
            precipitation_prob = period.get("probOfPrecipitation", "N/A")
            visibility = period.get("visibility", "N/A")
            uv_index = period.get("uvIndex", "N/A")
            pressure = period.get("mslp", "N/A")

            weather_desc = get_weather_description(weather_code)

            # Convert units for better readability
            wind_speed_mph = f"{wind_speed * 2.237:.1f}" if wind_speed != "N/A" else "N/A"
            pressure_mb = f"{pressure / 100:.1f}" if pressure != "N/A" else "N/A"
            visibility_km = f"{visibility / 1000:.1f}" if visibility != "N/A" else "N/A"

            forecast = f"""
---
Time: {time}
Temperature: {temp}°C (feels like {feels_like}°C)
Weather: {weather_desc}
Wind: {wind_speed_mph} mph from {wind_direction}°
Humidity: {humidity}%
Precipitation: {precipitation_rate} mm/h ({precipitation_prob}% chance)
Pressure: {pressure_mb} mb
Visibility: {visibility_km} km
UV Index: {uv_index}
"""
            forecasts.append(forecast)

        return "\n".join(forecasts)
    except (KeyError, IndexError) as e:
        return f"Failed to parse the forecast data. Error: {e}"


@mcp.tool()
async def get_daily_forecast(latitude: float, longitude: float) -> str:
    """Get the daily weather forecast for a location in the UK.

    Args:
        latitude: Latitude of the location.
        longitude: Longitude of the location.
    """
    url = f"{MET_OFFICE_API_BASE}/daily"
    # The dataSource determines the forecast type. 'BD1' is for the UK 3-hourly site-specific forecast.
    # The API seems to use it for daily as well based on the endpoint.
    params = {
        "dataSource": "BD1",
        "latitude": latitude,
        "longitude": longitude,
        "includeLocationName": "true",
    }
    data = await make_met_office_request(url, params=params)

    if not data:
        return "Unable to fetch forecast data for this location."

    try:
        # According to Met Office docs, the data is nested.
        time_series = data["features"][0]["properties"]["timeSeries"]
        location_name = data["features"][0]["properties"]["location"]["name"]

        forecasts = [f"Daily forecast for {location_name}:"]
        for period in time_series:
            # The time is in ISO 8601 format (e.g., "2024-05-21T12:00Z"), let's just show the date part.
            date = period["time"].split("T")[0]
            day_max_temp = period.get("dayMaxScreenTemperature", "N/A")
            night_min_temp = period.get("nightMinScreenTemperature", "N/A")
            day_wind_speed = period.get("midday10MWindSpeed", "N/A")

            day_weather_code = period.get("daySignificantWeatherCode", "NA")
            night_weather_code = period.get("nightSignificantWeatherCode", "NA")

            day_weather_desc = get_weather_description(day_weather_code)
            night_weather_desc = get_weather_description(night_weather_code)

            if (
                day_max_temp == "N/A"
                or night_min_temp == "N/A"
                or day_wind_speed == "N/A"
            ):
                print(
                    f"Warning: Missing temperature or wind speed data for {date}. Raw data for this period: {period}"
                )

            forecast = f"""
---
Date: {date}
Max Temp: {day_max_temp}°C
Min Temp: {night_min_temp}°C
Weather Type: {day_weather_desc} (Day), {night_weather_desc} (Night)
Wind Speed (10m): {day_wind_speed} mph
"""
            forecasts.append(forecast)

        return "\n".join(forecasts)
    except (KeyError, IndexError):
        return "Failed to parse the forecast data. The structure might have changed or the location is invalid."


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport="stdio")
