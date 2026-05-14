"""
Tool registry — imports and registers all tool modules with the MCP server.
Add new tool modules here as you build them.
"""

from jarvis.tools import web, system, weather, knowledge, utils


def register_all_tools(mcp):
    """Register all tool groups onto the MCP server instance."""
    web.register(mcp)
    system.register(mcp)
    weather.register(mcp)
    knowledge.register(mcp)
    utils.register(mcp)
