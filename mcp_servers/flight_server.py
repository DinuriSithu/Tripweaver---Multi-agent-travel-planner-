import os
import json
from dotenv import load_dotenv
import urllib.request
import urllib.parse
from typing import Optional
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("Flight Service", port=int(os.environ.get("PORT", 8002)), host="0.0.0.0")

BASE_URL = os.getenv("FLIGHT_API_BASE_URL")

def _get_json(url: str):
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            data = response.read().decode("utf-8")
            return json.loads(data)
    except Exception as e:
        return {
            "error": True,
            "message": str(e),
            "url": url
        }
    
def _post_json(url: str, payload: dict):
    try:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            response_data = response.read().decode("utf-8")
            return json.loads(response_data)

    except Exception as e:
        return {
            "error": True,
            "message": str(e),
            "url": url
        }

def _extract_flights(data):
    if isinstance(data, dict) and "flights" in data:
        return data["flights"]

    elif isinstance(data, list):
        return data

    else:
         return {
            "error": True,
            "message": "Unexpected flight API response format"
         }

@mcp.tool()
def list_flights() -> list[dict] | dict:
    url = f"{BASE_URL}/flights"
    data = _get_json(url)
    return _extract_flights(data)


@mcp.tool()
def search_flights(origin: str,destination: str,date: Optional[str] = None,) -> list[dict] | dict:
    params = {
        "origin": origin,
        "destination": destination,
    }

    if date:
        params["date"] = date

    query_string = urllib.parse.urlencode(params)
    url = (f"{BASE_URL}/flights/search?{query_string}")
    data = _get_json(url)
    print(json.dumps(data, indent=2))
    return _extract_flights(data)


@mcp.tool()
def book_flight(flight_id: str,passenger_name: str,passenger_email: str,) -> dict:
    payload = {
        "flightId": flight_id,
        "passengerName": passenger_name,
        "passengerEmail": passenger_email,
    }

    url = f"{BASE_URL}/flights/book"
    return _post_json(url, payload)
   
if __name__ == "__main__":
    mcp.run(transport="streamable-http")