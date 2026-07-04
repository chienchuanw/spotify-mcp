import asyncio

from . import server
from .auth import auth_main


def main():
    """Main entry point for the MCP server."""
    asyncio.run(server.main())


__all__ = ['main', 'auth_main', 'server']
