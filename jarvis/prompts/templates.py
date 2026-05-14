"""
Reusable prompt templates registered with the MCP server.
"""


def register(mcp):

    @mcp.prompt()
    def summarize(text: str) -> str:
        """Prompt to summarize a block of text concisely."""
        return f"Summarize the following text concisely:\n\n{text}"

    @mcp.prompt()
    def explain_code(code: str, language: str = "Python") -> str:
        """Prompt to explain a block of code step by step."""
        return (
            f"Explain the following {language} code in plain English, "
            f"step by step:\n\n```{language.lower()}\n{code}\n```"
        )

    @mcp.prompt()
    def translate(text: str, target_language: str = "Spanish") -> str:
        """Prompt to translate text into a target language."""
        return (
            f"Translate the following text into {target_language}. "
            f"Provide only the translation:\n\n{text}"
        )
