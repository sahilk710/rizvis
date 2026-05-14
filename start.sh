#!/bin/bash
# ============================================================
# J.A.R.V.I.S. — One-Click Launcher
# ============================================================
# Just run: ./start.sh
# Starts: MCP Server (8000) + Dashboard (8080) + Voice Agent (mic).
# Say "Wake up Jarvis" or double-clap to activate.
# Say "Go to sleep" to deactivate.
# Press Ctrl+C to shut down everything.
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
BOLD='\033[1m'

echo ""
echo -e "${CYAN}${BOLD}"
echo "     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗"
echo "     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝"
echo "     ██║███████║██████╔╝██║   ██║██║███████╗"
echo "██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║"
echo "╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║"
echo " ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝"
echo -e "${NC}"
echo -e "${YELLOW}  Just A Rather Very Intelligent System${NC}"
echo -e "${CYAN}  ─────────────────────────────────────${NC}"
echo ""

if [ ! -f ".env" ]; then
    echo -e "${RED}ERROR: .env file not found!${NC}"
    echo "Copy .env.example to .env and fill in your API keys."
    exit 1
fi

# Free ports we own
echo -e "${YELLOW}▸ Clearing ports 8000 and 8080...${NC}"
lsof -ti :8000 | xargs kill -9 2>/dev/null || true
lsof -ti :8080 | xargs kill -9 2>/dev/null || true
sleep 1

# ── MCP Server ──
echo -e "${GREEN}▸ Starting MCP Server (port 8000)...${NC}"
uv run jarvis > /tmp/jarvis_mcp.log 2>&1 &
MCP_PID=$!

echo -ne "${YELLOW}▸ Waiting for MCP Server"
for i in $(seq 1 20); do
    if lsof -ti :8000 > /dev/null 2>&1; then
        echo -e " ${GREEN}ONLINE ✓${NC}"
        break
    fi
    if [ $i -eq 20 ]; then
        echo -e " ${RED}FAILED${NC}"
        echo "Check /tmp/jarvis_mcp.log for errors"
        kill $MCP_PID 2>/dev/null
        exit 1
    fi
    echo -n "."
    sleep 1
done

# ── Dashboard Server ──
echo -e "${GREEN}▸ Starting Dashboard Server (port 8080)...${NC}"
uv run jarvis_dashboard > /tmp/jarvis_dashboard.log 2>&1 &
DASH_PID=$!

echo -ne "${YELLOW}▸ Waiting for Dashboard"
for i in $(seq 1 20); do
    if lsof -ti :8080 > /dev/null 2>&1; then
        echo -e " ${GREEN}ONLINE ✓${NC}"
        break
    fi
    if [ $i -eq 20 ]; then
        echo -e " ${RED}FAILED${NC}"
        echo "Check /tmp/jarvis_dashboard.log for errors"
        kill $MCP_PID $DASH_PID 2>/dev/null
        exit 1
    fi
    echo -n "."
    sleep 1
done

# Open HUD in default browser
open "http://localhost:8080" 2>/dev/null || true

# Cleanup
cleanup() {
    echo ""
    echo -e "${YELLOW}▸ Shutting down J.A.R.V.I.S...${NC}"
    kill $MCP_PID $DASH_PID 2>/dev/null || true
    lsof -ti :8000 | xargs kill -9 2>/dev/null || true
    lsof -ti :8080 | xargs kill -9 2>/dev/null || true
    echo -e "${RED}▸ J.A.R.V.I.S. offline. Goodbye, boss.${NC}"
    echo ""
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

echo ""
echo -e "${GREEN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  J.A.R.V.I.S. is now listening from your mic.${NC}"
echo -e "${GREEN}  HUD:  ${BOLD}http://localhost:8080${NC}"
echo -e "${GREEN}  Say \"Wake up Jarvis\" or double-clap 👏👏${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  Press Ctrl+C to shut down.${NC}"
echo ""

# Voice agent in CONSOLE mode → direct mic/speaker, wake word + double-clap.
uv run jarvis_voice
