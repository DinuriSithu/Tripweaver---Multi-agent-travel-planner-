from typing import List, Optional, Dict, Any, TypedDict
from langchain_core.messages import BaseMessage


class GraphState(TypedDict, total=False):
    messages: List[BaseMessage]

    intent: str
    sub_action: str
    activity_state: str
    tool_status: Optional[str]

    city: Optional[str]
    check_in: Optional[str]
    check_out: Optional[str]

    origin: Optional[str]
    destination: Optional[str]
    flight_date: Optional[str]

    hotel_id: Optional[str]
    guest_name: Optional[str]
    guest_email: Optional[str]
    room_type: Optional[str]

    flight_id: Optional[str]
    passenger_name: Optional[str]
    passenger_email: Optional[str]

    hotel_results: List[Dict[str, Any]]
    flight_results: List[Dict[str, Any]]

    booking_result: Any
    response_text: str
    error_message: Optional[str]

    selection_index: Optional[int]
    selection_type: Optional[str]

    selected_hotel: Optional[Dict[str, Any]]
    selected_flight: Optional[Dict[str, Any]]