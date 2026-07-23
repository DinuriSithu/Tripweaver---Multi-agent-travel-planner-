import os
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv(override=True)

HOTEL_MCP_URL = os.getenv("HOTEL_MCP_URL")
FLIGHT_MCP_URL = os.getenv("FLIGHT_MCP_URL")


async def get_hotel_tools():
    if not HOTEL_MCP_URL:
        raise RuntimeError("HOTEL_MCP_URL is not configured in the environment.")

    client = MultiServerMCPClient(
        {
            "hotel-service": {"url": HOTEL_MCP_URL, "transport": "streamable_http",}
        }
    )

    tools = await client.get_tools()
    return {
        tool.name: tool
        for tool in tools
    }


async def get_flight_tools():
    if not FLIGHT_MCP_URL:
        raise RuntimeError("FLIGHT_MCP_URL is not configured in the environment.")

    client = MultiServerMCPClient(
        {
            "flight-service": {"url": FLIGHT_MCP_URL,"transport": "streamable_http",}
        }
    )

    tools = await client.get_tools()
    return {
        tool.name: tool
        for tool in tools
    }


