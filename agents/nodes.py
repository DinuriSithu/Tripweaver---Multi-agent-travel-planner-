import json
from typing import Optional, Literal
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from .mcp_client import get_mcp_tools
from .llm import llm
from .prompts import get_system_prompt_for_unknown_node, get_system_prompt_with_history
from .entity import GraphState



class TravelExtraction(BaseModel):
    intent: Literal["hotel", "flight", "unknown"] = Field(
        default="unknown",
        description="Main user intent: hotel, flight, or unknown."
    )

    sub_action: Literal["search", "list_all","book", "general"] = Field(
        default="general",
        description="Action type: search, list_all, book or general."
    )

    city: Optional[str] = Field(
        default=None,
        description="Hotel city name. Example: Mumbai, Colombo, Bangkok."
    )

    check_in: Optional[str] = Field(
        default=None,
        description="Hotel check-in date in YYYY-MM-DD format. Null if not provided."
    )

    check_out: Optional[str] = Field(
        default=None,
        description="Hotel check-out date in YYYY-MM-DD format. Null if not provided."
    )

    origin: Optional[str] = Field(
        default=None,
        description="Flight origin city or airport code. Example: BOM, CMB, Mumbai."
    )

    destination: Optional[str] = Field(
        default=None,
        description="Flight destination city or airport code. Example: DEL, BKK, Delhi."
    )

    flight_date: Optional[str] = Field(
        default=None,
        description="Flight date in YYYY-MM-DD format. Null if not provided."
    )

    hotel_id: Optional[str] = Field(
        default=None,
        description="ID of the hotel to book. Null if not provided."
    )

    guest_name: Optional[str] = Field(
        default=None,
        description="Guest full name for hotel booking. Null if not provided."
    )

    guest_email: Optional[str] = Field(
        default=None,
        description="Guest email for hotel booking. Null if not provided."
    )

    room_type: Optional[str] = Field(
        default=None,
        description="Hotel room type such as single, double, or suite. Null if not provided."
    )

    flight_id: Optional[str] = Field(
        default=None,
        description="ID of the flight to book. Null if not provided."
    )

    passenger_name: Optional[str] = Field(
        default=None,
        description="Passenger full name for flight booking. Null if not provided."
    )

    passenger_email: Optional[str] = Field(
        default=None,
        description="Passenger email for flight booking. Null if not provided."
    )

    selection_index: Optional[int] = Field(
         default=None,
         description=(
             "The numbered result selected by the user. "
             "For example, if the user says 'book option 2', return 2."
        ),
    )

    selection_type: Optional[Literal["hotel", "flight"]] = Field(
        default=None,
        description=(
            "The selected result type: hotel or flight."
        ),
    )

travel_extractor = llm.with_structured_output(TravelExtraction)


async def _get_mcp_tool_map(): 
    return await get_mcp_tools()


def normalize_mcp_results(result):
    if hasattr(result, "content"):

        return normalize_mcp_results(
            result.content
        )


    if isinstance(result, dict):
        if (
            "airline" in result
            or "flightNumber" in result
            or "flight_number" in result
        ):
            return [result]


        if "flights" in result:
            return normalize_mcp_results(result["flights"])

        if (
            result.get("type") == "text"
            and "text" in result
        ):
            try:
                parsed = json.loads(result["text"])
                return normalize_mcp_results(parsed)

            except Exception:
                return []
            

    if isinstance(result, list):
        normalized = []
        for item in result:
            normalized.extend(normalize_mcp_results(item))
        return normalized
    return []


def normalize_hotel_results(result):
    if hasattr(result, "content"):
        return normalize_hotel_results(result.content)

    if isinstance(result, dict):
        if "hotels" in result:
            return normalize_hotel_results(result["hotels"])

        if result.get("type") == "text" and "text" in result:
            try:
                parsed = json.loads(result["text"])
                return normalize_hotel_results(parsed)

            except Exception:
                return []

        if (
            "id" in result
            or "_id" in result
            or "hotel_id" in result
            or "hotelName" in result
            or "name" in result
        ):
            return [result]

    if isinstance(result, list):
        normalized = []
        for item in result:
            normalized.extend(normalize_hotel_results(item))
        return normalized
    return []

def select_previous_result(
    state: GraphState,
    selection_index: Optional[int],
    selection_type: Optional[str],
):
    
    if not selection_index:
        return None, None

    if selection_index < 1:
        return None, None

    index = selection_index - 1

    if selection_type == "flight":
        flight_results = state.get("flight_results", [])
        if index >= len(flight_results):
            return None, "flight"
        return flight_results[index], "flight"

    if selection_type == "hotel":
        hotel_results = state.get("hotel_results", [])
        if index >= len(hotel_results):
            return None, "hotel"
        return hotel_results[index], "hotel"

    return None, None


def router(state: GraphState) -> dict:
    user_message = state["messages"][-1]
    history_messages = state["messages"][:-1]
    history_text = "\n".join(message.content for message in history_messages)
    
    system_prompt = get_system_prompt_with_history(history_text)
    invocation_messages = [
        SystemMessage(content=system_prompt),
        *history_messages,
        user_message,
    ]

    try:
        extracted = travel_extractor.invoke(invocation_messages)
        data = extracted.model_dump()

    except Exception as error:
        print(f"Intent extraction error: {error}")

        data = {
            "intent": "unknown",
            "sub_action": "general",
            "city": None,
            "check_in": None,
            "check_out": None,
            "origin": None,
            "destination": None,
            "flight_date": None,
            "hotel_id": None,
            "guest_name": None,
            "guest_email": None,
            "room_type": None,
            "flight_id": None,
            "passenger_name": None,
            "passenger_email": None,
            "selection_index": None,
            "selection_type": None,
        }

    return {
        **data,
        "activity_state": "ROUTING",
    }

def _format_hotel(hotel: dict) -> str:
    hotel_id = (
        hotel.get("id")
        or hotel.get("_id")
        or hotel.get("hotel_id")
        or "N/A"
    )

    name = hotel.get("name", "Unknown hotel")

    city_data = hotel.get("city", "unknown city")
    if isinstance(city_data, dict):
        city = city_data.get("name", "unknown city")
    else:
        city = city_data

    stars = hotel.get("stars", hotel.get("rating", "N/A"))
    price = hotel.get("price", hotel.get("pricePerNight", "N/A"))
    currency = hotel.get("currency", "USD")

    available = hotel.get("available_rooms",
        hotel.get("availableRooms", hotel.get("available", "N/A"))
    )

    return (
        f"Hotel ID: {hotel_id}\n"
        f"Name: {name}\n"
        f"Location: {city}\n"
        f"Rating: {stars} stars\n"
        f"Price: {currency} {price} per night\n"
        f"Available rooms: {available}"
    )

def _format_flight(flight: dict) -> str:
    airline = flight.get("airline", "Unknown airline")

    flight_number = flight.get("flightNumber",
        flight.get("flight_number", flight.get("flightNo", "N/A"))
    )

    origin_data = flight.get("origin", "unknown")
    destination_data = flight.get("destination", "unknown")

    if isinstance(origin_data, dict):
        origin = origin_data.get("airport", origin_data.get("city", "unknown"))
    else:
        origin = origin_data

    if isinstance(destination_data, dict):
        destination = destination_data.get("airport", destination_data.get("city", "unknown"))
    else:
        destination = destination_data

    flight_date = flight.get("flightDate",
        flight.get("date", flight.get("departure_date", "unknown"))
    )

    departure_time = flight.get("departureTime",
        flight.get("departure_time", "N/A")
    )

    arrival_time = flight.get("arrivalTime",
        flight.get("arrival_time", "N/A")
    )

    duration = flight.get("duration","N/A")
    price = flight.get("price", "N/A")
    currency = flight.get("currency", "USD")

    seats = flight.get("availableSeats",
        flight.get("available_seats", flight.get("seats", "N/A"))
    )
    aircraft = flight.get("aircraft","N/A")

    return (
        f"{airline} {flight_number} from {origin} to {destination} "
        f"on {flight_date}, {departure_time} - {arrival_time} "
        f"- {currency} {price} - {seats} seats"
        f"- {aircraft} "
        f"- {duration} "
    )

async def hotel_node(state: GraphState) -> dict:
    try:
        tools = await get_mcp_tools()
        list_hotels = tools.get("list_hotels")
        search_hotels = tools.get("search_hotels")
        book_hotel = tools.get("book_hotel")

        if not list_hotels or not search_hotels or not book_hotel: 
            raise RuntimeError( "Required hotel MCP tools are unavailable." )

    except Exception as error:
        print( f"Hotel booking MCP error: {error}" )
        return {
            "hotel_results": [],
            "flight_results": [],
            "response_text": (
                "The hotel service is currently unavailable. "
                "Please try again later."
            ),

            "booking_result": None,
            "error_message": str(error),
            "tool_status": "FAILED",
            "activity_state": "FAILED",
        }

    if state.get("sub_action") == "book":
        hotel_id = state.get("hotel_id")
        guest_name = state.get("guest_name")
        guest_email = state.get("guest_email")
        room_type = state.get("room_type")
        check_in_date = state.get("check_in")
        check_out_date = state.get("check_out")

        missing = []
        if not hotel_id:
            missing.append("hotel_id")

        if not guest_name:
            missing.append("guest_name")

        if not guest_email:
            missing.append("guest_email")

        if not check_in_date:
            missing.append("check_in")

        if not check_out_date:
            missing.append("check_out")

        if not room_type:
            missing.append("room_type")

        if missing:
            return {
                "hotel_results": [],
                "flight_results": [],
                "booking_result": None,
                "response_text": (
                    "I need more details to book the hotel. "
                    "Please provide hotel_id, guest_name, guest_email, room_type, "
                    "check_in, and check_out."
                ),
                "error_message": None,
                "activity_state": "CLARIFYING",
            }

        try:
            result = await book_hotel.ainvoke(
                {
                    "hotel_id": hotel_id,
                    "guest_name": guest_name,
                    "guest_email": guest_email,
                    "check_in_date": check_in_date,
                    "check_out_date": check_out_date,
                    "room_type": room_type,
                }
            )

            if isinstance(result, dict):
                confirmation = (
                    result.get("message")
                    or result.get("confirmation")
                    or result.get("status")
                    or "Hotel booking completed successfully."
                )

            else:
                confirmation = (
                    "Hotel booking completed successfully."
                )

            return {
                "hotel_results": [],
                "flight_results": [],
                "booking_result": result,
                "response_text": confirmation,
                "error_message": None,
                "tool_status": "SUCCEEDED",
                "activity_state": "RESPONDING",
            }

        except Exception as error:
            print( f"Hotel booking MCP error: {error}" )
            return {
                "hotel_results": [],
                "flight_results": [],
                "booking_result": None,
                "response_text": (
                    "I couldn't complete the hotel booking. "
                    "Please try again later."
                ),
                "error_message": str(error),
                "tool_status": "FAILED",
                "activity_state": "FAILED",
            }

    city = state.get("city")
    check_in = state.get("check_in")
    check_out = state.get("check_out")

    try:
        if state.get("sub_action") == "list_all":
            result = await list_hotels.ainvoke({})

        elif city:
            params = {"city": city}
            if check_in:
                params["checkIn"] = check_in

            if check_out:
                params["checkOut"] = check_out
            result = await search_hotels.ainvoke(params)
        else:
            result = await list_hotels.ainvoke({})

    except Exception as error:
        print( f"Hotel search MCP error: {error}" )
        return {
            "hotel_results": [],
            "flight_results": [],
            "booking_result": None,
            "response_text": (
                "The hotel service is currently unavailable."
            ),
            "error_message": str(error),
            "tool_status": "FAILED",
            "activity_state": "FAILED",
        }

    hotel_results = normalize_hotel_results(result)

    if not hotel_results:
        return {
            "hotel_results": [],
            "flight_results": [],
            "booking_result": None,
            "response_text": ("I couldn't find any hotels."),
            "error_message": None,
            "activity_state": "RESPONDING",
        }

    return {
        "hotel_results": hotel_results,
        "flight_results": [],
        "booking_result": None,
        "response_text": "",
        "error_message": None,
        "tool_status": "SUCCEEDED",
        "activity_state": "RESPONDING",
    }


async def flight_node(state: GraphState) -> dict:
    try:
        tools = await get_mcp_tools()
        list_flights = tools.get("list_flights")
        search_flights = tools.get("search_flights")
        book_flight = tools.get("book_flight")

        if not list_flights or not search_flights or not book_flight: 
            raise RuntimeError( "Required flight MCP tools are unavailable." )

    except Exception as error:
        print( f"Flight MCP connection error: {error}" )
        return {
            "hotel_results": [],
            "flight_results": [],
            "booking_result": None,
            "response_text": (
                     "The flight service is currently unavailable. "
                     "Please try again later."
            ),
            "error_message": str(error),
            "tool_status": "FAILED",
            "activity_state": "FAILED",
    }
    
    if state.get("sub_action") == "book":
        flight_id = state.get("flight_id")
        passenger_name = state.get("passenger_name")
        passenger_email = state.get("passenger_email")

        missing = []
        if not flight_id:
            missing.append("flight_id")

        if not passenger_name:
            missing.append("passenger_name")

        if not passenger_email:
            missing.append("passenger_email")

        if missing:
            return {
                "hotel_results": [],
                "flight_results": [],
                "booking_result": None,
                "response_text": (
                    "I need more details to book the flight. "
                    "Please provide flight_id, passenger_name, and passenger_email."
                ),
                "error_message": None,
                "activity_state": "CLARIFYING",
            }

        try:
            result = await book_flight.ainvoke(
                {
                    "flight_id": flight_id,
                    "passenger_name": passenger_name,
                    "passenger_email": passenger_email,
                }
            )

            if isinstance(result, dict):
                confirmation = (result.get("message")
                    or result.get("confirmation")
                    or result.get("status")
                    or "Flight booking completed successfully."
                )

            else:
                confirmation = ("Flight booking completed successfully.")

            return {
                "hotel_results": [],
                "flight_results": [],
                "booking_result": result,
                "response_text": confirmation,
                "error_message": None,
                "tool_status": "SUCCEEDED",
                "activity_state": "RESPONDING",
            }

        except Exception as error:
            print( f"Flight booking MCP error: {error}" )
            return {
                "hotel_results": [],
                "flight_results": [],
                "booking_result": None,
                "response_text": (
                    "I couldn't complete the flight booking. "
                    "Please try again later."
                ),
                "error_message": str(error),
                "tool_status": "FAILED",
                "activity_state": "FAILED",
            }

    origin = state.get("origin")
    destination = state.get("destination")
    flight_date = state.get("flight_date")

    try:
        if state.get("sub_action") == "list_all":
            result = await list_flights.ainvoke({})

        elif origin and destination:
            params = {"origin": origin,"destination": destination,}

            if flight_date:
                params["date"] = flight_date

            result = await search_flights.ainvoke(params)

        elif origin or destination:
            return {
                "hotel_results": [],
                "flight_results": [],
                "booking_result": None,
                "response_text": ("I need both departure and destination information."),
                "error_message": None,
                "activity_state": "CLARIFYING",
            }

        else:
            result = await list_flights.ainvoke({})

    except Exception as error:
            print( f"Flight search MCP error: {error}" )
            return {
                "hotel_results": [],
                "flight_results": [],
                "booking_result": None,
                "response_text": (
                    "The flight service is currently unavailable. "
                    "Please try again later."
                ),
                "error_message": str(error),
                "tool_status": "FAILED",
                "activity_state": "FAILED",
            }

    flight_results = normalize_mcp_results( result)

    if not flight_results:
        return {
            "hotel_results": [],
            "flight_results": [],
            "booking_result": None,
            "response_text": ("I couldn't find flights matching your request."),
            "error_message": None,
            "activity_state": "RESPONDING",
        }

    return {
        "hotel_results": [],
        "flight_results": flight_results,
        "booking_result": None,
        "response_text": "",
        "error_message": None,
        "tool_status": "SUCCEEDED",
        "activity_state": "RESPONDING",
    }


def unknown_node(state: GraphState) -> dict:
    user_message = state["messages"][-1]
    history_messages = state["messages"][:-1]
    history_text = "\n".join(message.content for message in history_messages)

    system_prompt = get_system_prompt_for_unknown_node(history_text)
    invocation_messages = [
        SystemMessage(content=system_prompt),
        *history_messages,
        user_message,
    ]

    try:
        response = llm.invoke(invocation_messages)
        return {
            "hotel_results": [],
            "flight_results": [],
            "response_text": response.content,
            "activity_state": "RESPONDING",
        }

    except Exception as error:
        return {
            "hotel_results": [],
            "flight_results": [],
            "response_text": ("I couldn't understand your request clearly."),
            "error_message": str(error),
            "activity_state": "FAILED",
        }


def generate_response(state: GraphState) -> dict:
    existing_response = state.get("response_text","")

    if existing_response:
        return {"response_text": existing_response}
    
    intent = state.get("intent","unknown")

    hotel_results = state.get("hotel_results", [])
    flight_results = state.get("flight_results", [])

    if intent == "hotel":
        if not hotel_results:
            return {"response_text": ("I couldn't find any hotels.")}
        
        formatted_hotels = []

        for index, hotel in enumerate(hotel_results[:7],start=1):
            formatted_hotels.append(
                f"\n--- Hotel Option {index} ---\n"+ _format_hotel(hotel)
            )

        return {
            "response_text": (
                f"I found {len(hotel_results)} hotel option(s):\n" + "\n".join(formatted_hotels))
        }


    if intent == "flight":
        if not flight_results:
            return {"response_text": ("I couldn't find flights matching your request.")}

        formatted_flights = []

        for index, flight in enumerate( flight_results[:7],start=1):
            formatted_flights.append(
                f"\n--- Flight Option {index} ---\n"+ _format_flight(flight))

        return {
            "response_text": (
                f"I found {len(flight_results)} flight option(s):\n"+ "\n".join(formatted_flights))
        }

    return {
        "response_text": ("I couldn't find matching travel options.")
    }

def route_after_extraction(state: GraphState) -> str:
    intent = state.get("intent", "unknown")

    if intent == "hotel":
        return "hotel"

    if intent == "flight":
        return "flight"

    return "unknown"