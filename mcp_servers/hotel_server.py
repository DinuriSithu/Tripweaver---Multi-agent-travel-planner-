import os
import json
import urllib.request
import urllib.parse
from typing import Optional
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

mcp = FastMCP("Hotel Service", port=int(os.environ.get("PORT", 8001)), host="0.0.0.0")

BASE_URL = os.getenv("HOTEL_API_BASE_URL")


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
    

def _extract_hotels(data):
    if isinstance(data, dict) and "hotels" in data:
        return data["hotels"]

    elif isinstance(data, list):
        return data

    else:
         return {
            "error": True,
            "message": "Unexpected Hotel API response format"
         }

@mcp.tool()
def list_hotels() -> list[dict] | dict:
    url = f"{BASE_URL}/hotels"
    data = _get_json(url)
    return _extract_hotels(data)


@mcp.tool()
def search_hotels(city: str,checkIn: Optional[str] = None,checkOut: Optional[str] = None) -> list[dict] | dict:
    params = {
        "city": city
    }

    if checkIn:
        params["checkIn"] = checkIn

    if checkOut:
        params["checkOut"] = checkOut

    query_string = urllib.parse.urlencode(params)
    url = (f"{BASE_URL}/hotels/search?{query_string}")
    data = _get_json(url)
    return _extract_hotels(data)


@mcp.tool()
def book_hotel(hotel_id: str,guest_name: str,guest_email: str,check_in_date: str,check_out_date: str,room_type: str
) -> dict:
    payload = {
        "hotelId": hotel_id,
        "guestName": guest_name,
        "guestEmail": guest_email,
        "checkInDate": check_in_date,
        "checkOutDate": check_out_date,
        "roomType": room_type
    }
    url = f"{BASE_URL}/hotels/book"
    return _post_json(url, payload)

if __name__ == "__main__":
    mcp.run(transport="streamable-http")