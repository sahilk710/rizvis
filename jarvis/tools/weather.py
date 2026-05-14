"""
Weather tools — current conditions via Open-Meteo API (free, no key needed).

`fetch_weather` returns a structured dict and is reused by the dashboard API.
"""

import httpx


WMO_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def _decode_weather_code(code: int) -> str:
    return WMO_CODES.get(code, f"Unknown (code {code})")


async def fetch_weather(city: str) -> dict | None:
    """
    Look up a city via Open-Meteo geocoding and return current weather as a dict.
    Returns None if the city can't be resolved.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        geo_resp = await client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "en", "format": "json"},
        )
        geo_data = geo_resp.json()
        if not geo_data.get("results"):
            return None

        location = geo_data["results"][0]
        lat = location["latitude"]
        lng = location["longitude"]

        weather_resp = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lng,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,wind_direction_10m",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
            },
        )
        current = weather_resp.json().get("current", {})

    weather_code = current.get("weather_code", 0)
    return {
        "city": location.get("name", city),
        "country": location.get("country", ""),
        "latitude": lat,
        "longitude": lng,
        "temperature_f": current.get("temperature_2m"),
        "feels_like_f": current.get("apparent_temperature"),
        "humidity_pct": current.get("relative_humidity_2m"),
        "wind_mph": current.get("wind_speed_10m"),
        "wind_direction_deg": current.get("wind_direction_10m"),
        "weather_code": weather_code,
        "condition": _decode_weather_code(weather_code),
    }


def register(mcp):

    @mcp.tool()
    async def get_weather(city: str) -> str:
        """
        Get current weather for a city. Returns temperature, conditions, humidity, and wind.
        Uses Open-Meteo API (free, no API key required).
        Examples: get_weather("New York"), get_weather("London"), get_weather("Tokyo")
        """
        try:
            data = await fetch_weather(city)
            if data is None:
                return f"I couldn't find weather data for '{city}', sir. Try a different city name."
            return (
                f"### Weather for {data['city']}, {data['country']}\n\n"
                f"**Condition:** {data['condition']}\n"
                f"**Temperature:** {data['temperature_f']}°F (feels like {data['feels_like_f']}°F)\n"
                f"**Humidity:** {data['humidity_pct']}%\n"
                f"**Wind:** {data['wind_mph']} mph\n"
            )
        except Exception as e:
            return f"Weather systems are offline right now, sir: {str(e)}"
