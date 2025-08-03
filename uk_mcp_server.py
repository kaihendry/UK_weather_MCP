import os
import json
from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("UK_weather")

# Constants
MET_OFFICE_API_BASE = "http://datapoint.metoffice.gov.uk/public/data/val"
MET_OFFICE_API_KEY = os.getenv("MET_OFFICE_API_KEY")

# https://www.metoffice.gov.uk/services/data/datapoint/api-reference#location-specific

if not MET_OFFICE_API_KEY:
    raise ValueError(
        "MET_OFFICE_API_KEY environment variable not set. Please set it in your .bashrc or similar."
    )

# https://www.metoffice.gov.uk/services/data/datapoint/code-definitions
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


def lookup_station_id(query_name: str) -> str | None:
    """Lookup station ID by name from stations.json file.

    Args:
        query_name: The name of the location to search for

    Returns:
        The station ID if found, None otherwise
    """
    try:
        with open("stations.json", "r") as f:
            data = json.load(f)

        locations = data.get("Locations", {}).get("Location", [])

        # First try exact match (case insensitive)
        for location in locations:
            if location["name"].lower() == query_name.lower():
                return location["id"]

        # Then try partial match (case insensitive)
        for location in locations:
            if query_name.lower() in location["name"].lower():
                return location["id"]

        return None

    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        print(f"Error reading stations.json: {e}")
        return None


async def make_met_office_request(
    url: str, params: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """Make a request to the Met Office API with proper error handling."""
    # append key to params if not already present
    if params is None:
        params = {}
    params.setdefault("key", MET_OFFICE_API_KEY)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"HTTP Error: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            print(f"An error occurred: {e}")
            return None


@mcp.tool()
async def get_hourly_observations(name: str) -> str:
    """Returns hourly weather observations for the last 24 hours

    Args:
        name: Name of the location (e.g., "Cardinham")
    """
    # Lookup station ID from name
    locid = lookup_station_id(name)
    if not locid:
        return f"Location '{name}' not found. Please check the spelling or try a different location name."

    url = f"{MET_OFFICE_API_BASE}/wxobs/all/json/{locid}"
    params = {
        "res": "hourly",
    }
    data = await make_met_office_request(url, params=params)

    if not data:
        return "Unable to fetch observations data for this location."

    try:
        # Parse the Met Office response structure
        site_rep = data["SiteRep"]
        location = site_rep["DV"]["Location"]
        location_name = location["name"]
        
        observations = [f"Hourly observations for {location_name}:"]
        
        # Process each day's data
        for period in location["Period"]:
            date = period["value"]  # e.g., "2025-08-03Z"
            date_formatted = date.replace("Z", "")
            
            observations.append(f"\n=== {date_formatted} ===")
            
            # Process each hourly report
            for rep in period["Rep"]:
                # The '$' field contains time in minutes since midnight
                time_minutes = int(rep["$"])
                hours = time_minutes // 60
                minutes = time_minutes % 60
                time_str = f"{hours:02d}:{minutes:02d}"
                
                # Extract weather data
                temp = rep.get("T", "N/A")
                humidity = rep.get("H", "N/A")
                pressure = rep.get("P", "N/A")
                wind_speed = rep.get("S", "N/A")
                wind_gust = rep.get("G", "N/A")
                wind_dir = rep.get("D", "N/A")
                weather_code = rep.get("W", "NA")
                visibility = rep.get("V", "N/A")
                dew_point = rep.get("Dp", "N/A")
                
                weather_desc = get_weather_description(weather_code)
                
                observation = f"""
{time_str} - Temp: {temp}°C, Weather: {weather_desc}
         Humidity: {humidity}%, Pressure: {pressure}hPa
         Wind: {wind_speed}mph from {wind_dir} (gusts {wind_gust}mph)
         Visibility: {visibility}m, Dew Point: {dew_point}°C"""
                
                observations.append(observation)
        
        return "\n".join(observations)
        
    except (KeyError, IndexError, ValueError) as e:
        return f"Failed to parse the observations data: {str(e)}. The structure might have changed or the location is invalid."


if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport="stdio")
