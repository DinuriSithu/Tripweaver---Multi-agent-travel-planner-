# TripWeaver — MCP-Based Multi-Agent Travel Planner

TripWeaver is a conversational multi-agent travel planning application that allows users to search for hotels, search for flights, and make hotel or flight booking requests through a single chat interface.

The system uses a LangGraph-based multi-agent workflow, FastAPI backend, Gradio frontend, and Model Context Protocol (MCP) servers to connect the AI agents with external hotel and flight services.

# Project Overview

TripWeaver allows travellers to interact with a travel planning assistant using natural language.

For example, a user can ask:

- "Find hotels in Paris."
- "Show me flights from Colombo to Dubai."
- "Book hotel H123."
- "Book flight F456."
- "I need flights from CMB to LHR on 2026-08-01."

The system interprets the user's intent and routes the request to the appropriate specialised agent.

**Supported Agents:**
- General QA Agent =	Handles general travel questions and unclear requests
- Hotel Agent	     =  Searches, lists, and books hotels
- Flight Agent	 =  Searches, lists, and books flights

The system uses MCP servers as the standardised communication layer between the AI agents and external travel services.

## Project layout


agents/
  entity.py      =  Shared LangGraph state schema
  llm.py         =  LLM initialisation
  mcp_client.py  =  get_hotel_tools() / get_flight_tools()
  nodes.py       =  router / hotel_node / flight_node / unknown_node / generate_response
  graph.py       =  Wires the nodes into a LangGraph StateGraph
  prompts.py     =  System prompts
mcp_servers/
  hotel_server.py  =  MCP server: list/search/book hotels
  flight_server.py =  MCP server: list/search/book flights
main.py          =  FastAPI backend (/chat, /chat/stream)
frontend.py      =  Gradio chat UI
entity.py        =  FastAPI request/response models
requirements.txt


# System Architecture

TripWeaver consists of four major layers.

1. Frontend Layer

The Gradio frontend provides the traveller chat interface.

Responsibilities:
Accept user messages
Display conversation history
Display activity messages
Receive streamed responses
Display friendly error messages

2. FastAPI Backend

The FastAPI backend acts as the main application API.

Responsibilities:
Receive chat requests
Manage conversation sessions
Execute the LangGraph workflow
Stream activity and response events
Return structured travel results

Main endpoints:
GET  /
POST /chat
POST /chat/stream

3. LangGraph Agent Layer

The LangGraph workflow is responsible for:
Understanding the user's request
Extracting travel information
Identifying the user's intent
Routing the request
Executing the appropriate specialised agent
Generating the final response

4. MCP Service Layer

MCP servers provide the connection between the agents and external travel services.


## 1. Setup

**Prerequisites**: Python, an OpenAI API key and base URLs for a
hotel API and a flight API.

bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt


Create a ".env" file in the project root and add the following:


OPENAI_API_KEY=your_actual_api_key_here

HOTEL_MCP_URL=http://localhost:8001/mcp
FLIGHT_MCP_URL=http://localhost:8002/mcp

HOTEL_API_BASE =your_hotel_api_base_url/hotels
FLIGHT_API_BASE =your_flight_api_base_url/flights

HOTEL_API_BASE_URL=your_hotel_api_base_url 
FLIGHT_API_BASE_URL=your_flight_api_base_url

# Must include /chat, not just the host
BACKEND_URL=http://localhost:8000/chat
`

**Run locally** (4 terminals):


python mcp_servers/hotel_server.py    # terminal 1
python mcp_servers/flight_server.py   # terminal 2
python main.py                        # terminal 3
python frontend.py                    # terminal 4


Open the URL Gradio prints (default `http://localhost:7860`).

## 2. MCP server guide

Each file in `mcp_servers/` is its own standalone process, not a library
imported into the agents this lets a service be swapped or
added without touching agent code.

- **Tools** are defined with `@mcp.tool()`; the function signature and
  docstring become the schema the LLM sees. `hotel_server.py` exposes
  `list_hotels`, `search_hotels`, `book_hotel`; `flight_server.py` exposes
  `list_flights`, `search_flights`, `book_flight`.
  
- Each server calls a real API via `HOTEL_API_BASE_URL` /
  `FLIGHT_API_BASE_URL` — set in `.env`.
  
- `agents/mcp_client.py` fetches hotel and flight tools **independently**
  (`get_hotel_tools()`, `get_flight_tools()`), so if one service is down,
  only that agent degrades the other agent keeps working.
  
- **To add a new service** (e.g. weather): write
  `mcp_servers/weather_server.py` with its own `@mcp.tool()` functions and
  its own port, add a `get_weather_tools()` function to `mcp_client.py`
  following the same pattern, then use it in a new or existing node. No
  other agent code changes.

## 3. Deployment (Render, free tier)

Render needs services to bind `0.0.0.0` and read the port from the
`PORT` environment variable, so make sure these four spots look like
this before deploying:

**`main.py`** (at the bottom of file):

if __name__ == "__main__":
    import uvicorn, os
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))


**`mcp_servers/hotel_server.py`**:

import os
mcp = FastMCP("Hotel Service", port=int(os.environ.get("PORT", 8001)), host="0.0.0.0")


**`mcp_servers/flight_server.py`**:

import os
mcp = FastMCP("Flight Service", port=int(os.environ.get("PORT", 8002)), host="0.0.0.0")


**`frontend.py`** (`main()`):

demo.launch(
    server_name="0.0.0.0",
    server_port=int(os.environ.get("PORT", 7860)),
    theme=gr.themes.Soft(primary_hue="blue", secondary_hue="orange"),
    css=CUSTOM_CSS,
)


**Steps:**

1. Push this repo to GitHub.
2. On [render.com](https://render.com), create **4 separate Web
   Services**, all from the same repo, changing only the name and start
   command:

   | Name                   | Start Command |
   | `tripweaver-hotel-mcp` | `python mcp_servers/hotel_server.py` |
   | `tripweaver-flight-mcp`| `python mcp_servers/flight_server.py` |
   | `tripweaver-backend`   | `python main.py` |
   | `tripweaver-frontend`  | `python frontend.py` |

   For all four: **Build Command** = `pip install -r requirements.txt`,
   **Instance Type** = Free.

3. Set environment variables per service (Render dashboard → service →
   **Environment**):

   - `tripweaver-hotel-mcp`: `HOTEL_API_BASE_URL`
   - `tripweaver-flight-mcp`: `FLIGHT_API_BASE_URL`
   - `tripweaver-backend`: `OPENAI_API_KEY`, `HOTEL_API_BASE_URL`,
     `FLIGHT_API_BASE_URL`, and once the two MCP services are live:
     `HOTEL_MCP_URL=https://tripweaver-hotel-mcp.onrender.com/mcp`,
     `FLIGHT_MCP_URL=https://tripweaver-flight-mcp.onrender.com/mcp`
   - `tripweaver-frontend`: once the backend is live,
     `BACKEND_URL=https://tripweaver-backend.onrender.com/chat`

4. Deploy in this order: both MCP servers first, then backend, then
   frontend — each step needs the URL from the one before it.


### Docker Compose (alternative, local/self-hosted)

cp .env.example .env   
docker compose up --build

Starts all four services together on one Docker network.


## 4. User guide
1. Open the frontend URL. The status line below the chat shows what the
   system is doing.
2. Ask things like:
   - *"Show me all hotels"*
   - *"Find flights from CMB to DXB on 2026-08-10"*
   - *"Book hotel H101 for Alex Doe, alex@example.com, double room,
     2026-08-10 to 2026-08-14"*
3. While the agents work, the status line updates live (Understanding your request…, 
   "Composing your answer…").
4. If a booking is missing details, the assistant asks a follow-up
   question instead of guessing.
5. If a service is down, you'll get a clear message and the rest of the
   app keeps working.

