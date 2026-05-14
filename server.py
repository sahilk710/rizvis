"""
J.A.R.V.I.S. MCP Server — Entry Point
Run with: uv run jarvis
"""

from mcp.server.fastmcp import FastMCP
from jarvis.tools import register_all_tools
from jarvis.prompts import register_all_prompts
from jarvis.resources import register_all_resources
from jarvis.config import config

# Create the MCP server instance
mcp = FastMCP(
    name=config.SERVER_NAME,
    instructions=(
        "You are J.A.R.V.I.S. — Just A Rather Very Intelligent System — "
        "Tony Stark's personal AI assistant. "
        "You have access to a set of tools to help the user. "
        "Be concise, accurate, and deliver information with the calm confidence "
        "of an AI that's been running Stark Industries since before the user woke up."
    ),
)

# Register tools, prompts, and resources
register_all_tools(mcp)
register_all_prompts(mcp)
register_all_resources(mcp)


def main():
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
