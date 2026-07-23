import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from langchain_core.messages import HumanMessage, AIMessage
from entity import ChatRequest, ChatResponse
from agents.graph import graph


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def Greeting():
    return {"message": "Welcome to Multi Agent Travel Planner!"}

sessions = {}

def create_session():
    return {
        "messages": [],
        "hotel_results": [],
        "flight_results": [],
    }

conversation_state = {
    "hotel_results": [],
    "flight_results": [],

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
}

def _build_initial_state(session, message: str) -> dict:
    previous_messages = session["messages"]
    recent_messages = previous_messages[-6:]
    flattened_messages = list(recent_messages)
    flattened_messages.append(HumanMessage(content=message))

    return {
        "messages": flattened_messages,
        "intent": "",
        "sub_action": "",
        "activity_state": "STARTING",

        "city": None,
        "check_in": None,
        "check_out": None,
        "hotel_id": None,
        "guest_name": None,
        "guest_email": None,
        "room_type": None,

        "origin": None,
        "destination": None,
        "flight_date": None,
        "flight_id": None,
        "passenger_name": None,
        "passenger_email": None,

        "hotel_results": [],
        "flight_results": [],

        "selection_index": None,
        "selection_type": None,
        "selected_hotel": None,
        "selected_flight": None,

        "booking_result": None,
        "response_text": "",
        "error_message": None,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    session_id = request.session_id

    if session_id not in sessions:
        sessions[session_id] = create_session()
    session = sessions[session_id]

    initial_state = _build_initial_state(session, request.message)

    try:
        result = await graph.ainvoke(initial_state)

        response_text = result.get(
            "response_text",
            "No response was generated."
        )

    except Exception as error:
        print(f"Graph execution error: {error}")

        response_text = (
            "I'm sorry, but I couldn't complete that travel request right now. "
            "The travel service encountered a temporary problem. "
            "Please try again or make another request."
        )

        return ChatResponse(
            response=response_text,
            hotels=None,
            flights=None,
            session_id=session_id,
            activity_state="FAILED",
            tool_status="FAILED",
            error= None,
        )

    session["messages"].append(HumanMessage(content=request.message))
    session["messages"].append(AIMessage(content=response_text))

    session["hotel_results"] = result.get("hotel_results", [])
    session["flight_results"] = result.get("flight_results", [])

    return ChatResponse(
        response=response_text,
        hotels=result.get("hotel_results", []) or None,
        flights=result.get("flight_results", []) or None,
        session_id=session_id,
        activity_state=result.get("activity_state", "RESPONDING"),
        tool_status=result.get("tool_status", "SUCCEEDED"),
        error=result.get("error_message"),
    )


ACTIVITY_LABELS = {
    "router": "Understanding your request…",
    "hotel_node": {
        "SEARCHING": "Searching hotel suggestions…",
        "BOOKING": "Booking your hotel…",
        "CLARIFYING": "Need a bit more information…",
        "FAILED": "Hotel service ran into a problem…",
        "RESPONDING": "Preparing hotel results…",
    },
    "flight_node": {
        "SEARCHING": "Searching flight suggestions…",
        "BOOKING": "Booking your flight…",
        "CLARIFYING": "Need a bit more information…",
        "FAILED": "Flight service ran into a problem…",
        "RESPONDING": "Preparing flight results…",
    },
    "unknown_node": "Thinking…",
    "generate_response": "Composing your answer…",
}

def _activity_label(node_name: str, node_output: dict) -> str:
    label = ACTIVITY_LABELS.get(node_name, "Working…")
    if isinstance(label, dict):
        state = (node_output or {}).get("activity_state", "SEARCHING")
        return label.get(state, "Working…")
    return label


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    session_id = request.session_id

    if session_id not in sessions:
        sessions[session_id] = create_session()
    session = sessions[session_id]

    initial_state = _build_initial_state(session, request.message)

    async def event_generator():
        final_result = {}
        try:
            async for step in graph.astream(initial_state, stream_mode="updates"):
                for node_name, node_output in step.items():
                    yield _sse("activity",
                        {
                            "node": node_name,
                            "label": _activity_label(node_name, node_output or {}),
                        },
                    )
                    final_result.update(node_output or {})

        except Exception as error:
            print(f"Graph streaming error: {error}")
            yield _sse("error",
                {
                    "message": (
                        "I'm sorry, but I couldn't complete that travel request "
                        "right now. The travel service encountered a temporary "
                        "problem. Please try again or make another request."
                    ),
                    "error": None,
                },)
            return

        response_text = final_result.get("response_text") or "No response was generated."

        words = response_text.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            yield _sse("token", {"text": chunk})

        session["messages"].append(HumanMessage(content=request.message))
        session["messages"].append(AIMessage(content=response_text))
        session["hotel_results"] = final_result.get("hotel_results", [])
        session["flight_results"] = final_result.get("flight_results", [])

        yield _sse("done",
            {
                "response": response_text,
                "session_id": session_id,
                "activity_state": final_result.get("activity_state", "RESPONDING"),
                "tool_status": final_result.get("tool_status", "SUCCEEDED"),
                "intent": final_result.get("intent"),
                "hotels": final_result.get("hotel_results") or None,
                "flights": final_result.get("flight_results") or None,
                "error": final_result.get("error_message"),
            },
        )
    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
       import uvicorn
       import os
       uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))