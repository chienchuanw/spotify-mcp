import logging
import sys

import mcp.types as types
import mcp.server.stdio
from mcp.server import Server

from .auth import get_client
from .errors import format_error
from .tools import TOOL_MODELS, HANDLERS

logger = logging.getLogger(__name__)

server = Server("spotify-mcp")


@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    return []


@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    return []


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    tools = [model.as_tool() for model in TOOL_MODELS]
    logger.info("Available tools: %s", [t.name for t in tools])
    return tools


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    logger.info("Tool called: %s with arguments: %s", name, arguments)
    handler = HANDLERS.get(name)
    if handler is None:
        return [types.TextContent(type="text", text=f"Unknown tool: {name}")]
    try:
        client = get_client()
        return handler(client, arguments or {})
    except Exception as e:
        logger.error("Error handling %s: %s", name, e, exc_info=True)
        return [types.TextContent(type="text", text=format_error(e))]


async def main():
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(levelname)s %(name)s: %(message)s",
    )
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
