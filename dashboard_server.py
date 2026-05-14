"""
J.A.R.V.I.S. Dashboard Server
=============================
Serves the HUD dashboard at http://127.0.0.1:8080 and exposes live JSON
endpoints backed by the same data sources the MCP tools use.

Run with: uv run jarvis_dashboard
"""

import logging
import time
from collections import deque
from pathlib import Path

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from jarvis.tools.web import (
    FINANCE_FEEDS,
    WORLD_NEWS_FEEDS,
    fetch_news_items,
)
from jarvis.tools.system import get_system_stats
from jarvis.tools.weather import fetch_weather

DASHBOARD_DIR = Path(__file__).parent / "dashboard"
DASHBOARD_PORT = 8080
MCP_HEALTH_URL = "http://127.0.0.1:8000/sse"

logger = logging.getLogger("jarvis-dashboard")

# Bounded in-memory activity log. Other processes can POST events here.
_activity_log: deque[dict] = deque(maxlen=50)


def _log_event(message: str, kind: str = "info") -> dict:
    entry = {
        "timestamp": int(time.time() * 1000),
        "message": message,
        "kind": kind,
    }
    _activity_log.appendleft(entry)
    return entry


async def api_system(request: Request) -> JSONResponse:
    try:
        return JSONResponse(get_system_stats())
    except Exception as e:
        logger.exception("system stats failed")
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_news(request: Request) -> JSONResponse:
    feed_type = request.query_params.get("type", "world")
    feeds = FINANCE_FEEDS if feed_type == "finance" else WORLD_NEWS_FEEDS
    try:
        articles = await fetch_news_items(feeds, limit=10)
        return JSONResponse({"type": feed_type, "articles": articles})
    except Exception as e:
        logger.exception("news fetch failed")
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_weather(request: Request) -> JSONResponse:
    city = request.query_params.get("city", "New York")
    try:
        data = await fetch_weather(city)
        if data is None:
            return JSONResponse({"error": f"City '{city}' not found"}, status_code=404)
        return JSONResponse(data)
    except Exception as e:
        logger.exception("weather fetch failed")
        return JSONResponse({"error": str(e)}, status_code=500)


async def api_health(request: Request) -> JSONResponse:
    mcp_online = False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            # SSE endpoint returns a stream; a HEAD/GET that doesn't hang is enough.
            resp = await client.get(MCP_HEALTH_URL, timeout=1.5)
            mcp_online = resp.status_code < 500
    except httpx.ReadTimeout:
        # SSE keeps the connection open — a read timeout still means it answered.
        mcp_online = True
    except Exception:
        mcp_online = False

    return JSONResponse({
        "dashboard": "online",
        "mcp": "online" if mcp_online else "offline",
    })


async def api_activity_get(request: Request) -> JSONResponse:
    return JSONResponse({"entries": list(_activity_log)})


async def api_activity_post(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid json"}, status_code=400)
    message = (body or {}).get("message")
    kind = (body or {}).get("kind", "info")
    if not message:
        return JSONResponse({"error": "missing 'message'"}, status_code=400)
    entry = _log_event(str(message), str(kind))
    return JSONResponse(entry, status_code=201)


routes = [
    Route("/api/system", api_system),
    Route("/api/news", api_news),
    Route("/api/weather", api_weather),
    Route("/api/health", api_health),
    Route("/api/activity", api_activity_get, methods=["GET"]),
    Route("/api/activity", api_activity_post, methods=["POST"]),
    Mount("/", app=StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard"),
]

app = Starlette(routes=routes)


def main():
    import uvicorn
    _log_event("Dashboard server boot complete.")
    uvicorn.run(app, host="127.0.0.1", port=DASHBOARD_PORT, log_level="info")


if __name__ == "__main__":
    main()
