"""
Data resources — expose static content or dynamic data via MCP resources.
"""


def register(mcp):

    @mcp.resource("jarvis://info")
    def server_info() -> str:
        """Returns basic info about this MCP server."""
        return (
            "J.A.R.V.I.S. MCP Server\n"
            "Just A Rather Very Intelligent System\n"
            "An Iron Man-inspired AI assistant.\n"
            "Built with FastMCP + LiveKit Agents."
        )
