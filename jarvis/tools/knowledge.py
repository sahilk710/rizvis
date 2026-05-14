"""
Knowledge tools — Wikipedia summaries and math calculations.
"""

import httpx
import ast
import operator


def register(mcp):

    @mcp.tool()
    async def wikipedia_summary(topic: str) -> str:
        """
        Fetch a summary about any topic from Wikipedia.
        Examples: wikipedia_summary("Quantum Computing"), wikipedia_summary("Tony Stark")
        """
        try:
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{topic}"
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": "Jarvis-AI/1.0"},
                    follow_redirects=True,
                )

                if response.status_code == 404:
                    return f"I couldn't find a Wikipedia article on '{topic}', sir. Try a different search term."

                response.raise_for_status()
                data = response.json()

                title = data.get("title", topic)
                extract = data.get("extract", "No summary available.")
                page_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")

                return (
                    f"### {title}\n\n"
                    f"{extract}\n\n"
                    f"Read more: {page_url}"
                )
        except Exception as e:
            return f"Knowledge base is unresponsive right now, sir: {str(e)}"

    @mcp.tool()
    def calculate(expression: str) -> str:
        """
        Safely evaluate a mathematical expression.
        Examples: calculate("2 + 2"), calculate("sqrt(144)"), calculate("15 * 23 + 7")
        """
        # Safe operators for AST-based evaluation
        SAFE_OPS = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
        }

        def _eval_node(node):
            if isinstance(node, ast.Expression):
                return _eval_node(node.body)
            elif isinstance(node, ast.Constant):
                if isinstance(node.value, (int, float)):
                    return node.value
                raise ValueError(f"Unsupported constant: {node.value}")
            elif isinstance(node, ast.BinOp):
                left = _eval_node(node.left)
                right = _eval_node(node.right)
                op = SAFE_OPS.get(type(node.op))
                if op is None:
                    raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
                return op(left, right)
            elif isinstance(node, ast.UnaryOp):
                operand = _eval_node(node.operand)
                op = SAFE_OPS.get(type(node.op))
                if op is None:
                    raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
                return op(operand)
            else:
                raise ValueError(f"Unsupported expression: {type(node).__name__}")

        try:
            # Handle common math functions by substituting them
            import math
            expr = expression.strip()
            expr = expr.replace("sqrt(", "___SQRT___(")
            expr = expr.replace("pi", str(math.pi))
            expr = expr.replace("e", str(math.e)) if expr.strip() == "e" else expr

            if "___SQRT___(" in expr:
                # Simple sqrt handling
                import re
                match = re.search(r"___SQRT___\(([^)]+)\)", expr)
                if match:
                    inner = float(match.group(1))
                    result = math.sqrt(inner)
                    return f"√({match.group(1)}) = **{result:g}**"

            tree = ast.parse(expr, mode="eval")
            result = _eval_node(tree)

            if isinstance(result, float) and result == int(result):
                result = int(result)

            return f"{expression} = **{result:g}**"
        except ZeroDivisionError:
            return "Division by zero — even I can't solve that, sir."
        except Exception as e:
            return f"I couldn't evaluate that expression: {str(e)}"
