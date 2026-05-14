# J.A.R.V.I.S. — Just A Rather Very Intelligent System

> *An Iron Man-inspired AI voice assistant powered by MCP + LiveKit, with a live Iron-Man HUD.*

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Set up API keys
cp .env.example .env
# Edit .env with your keys

# 3. Launch everything (MCP server + HUD dashboard + voice agent)
./start.sh
```

`start.sh` will:

1. Boot the MCP tool server on `:8000`.
2. Boot the dashboard backend on `:8080` and open the HUD in your browser.
3. Run the voice agent in **console mode** — it listens directly through your
   laptop microphone.

Say **"Wake up Jarvis"** or **double-clap** to activate. Say **"Go to sleep"**
to send him back to standby. `Ctrl+C` shuts everything down cleanly.

You can also run each piece independently:

```bash
uv run jarvis            # MCP server only      (port 8000)
uv run jarvis_dashboard  # Dashboard only       (port 8080)
uv run jarvis_voice      # Voice agent only     (laptop mic)
uv run jarvis_cloud      # Voice agent — LiveKit Cloud playground mode
```

## Architecture

```
                ┌─────────────────────────────────────────────┐
                │           HUD Dashboard (browser)           │
                │     http://localhost:8080  (static + JS)    │
                └────────────────┬────────────────────────────┘
                                 │  fetch /api/{system,news,
                                 │  weather,health,activity}
                                 ▼
                ┌─────────────────────────────────────────────┐
                │   Dashboard Server  (Starlette, port 8080)  │
                │   - serves dashboard/ static files          │
                │   - JSON endpoints reuse jarvis.tools.*     │
                └────────────────┬────────────────────────────┘
                                 │
                                 │ (shared imports)
                                 ▼
Microphone ──► STT (Deepgram Nova-2)
                    │
                    ▼
             LLM (Gemini 2.5 Flash)  ◄──── SSE ────►  MCP Server  (FastMCP, port 8000)
                    │                                       │
                    ▼                                       │   register_all_tools()
             TTS (OpenAI Nova)                              │   register_all_prompts()
                    │                                       │   register_all_resources()
                    ▼                                       │
             Speaker (laptop)                               ▼
                                              jarvis.tools.{web,system,
                                              weather,knowledge,utils}
```

The voice agent also pushes wake/sleep/user-turn events to
`POST /api/activity` so the HUD's activity log shows what's really happening.

## Tools Available

All tools are exposed by the MCP server (`uv run jarvis`).

| Tool | Type | Description |
|------|------|-------------|
| `get_world_news` | web | Aggregated global headlines (BBC, NYT, CNBC, Al Jazeera) |
| `get_finance_news` | web | Aggregated market headlines (CNBC, MarketWatch, NYT Business) |
| `search_web` | web | Web search via DuckDuckGo HTML |
| `fetch_url` | web | Fetch the first 4000 chars of any URL |
| `open_world_monitor` | web | Open `worldmonitor.app` in the default browser |
| `open_finance_monitor` | web | Open `finance.worldmonitor.app` in the default browser |
| `get_weather` | weather | Current weather for any city (Open-Meteo, no key) |
| `get_current_time` | system | Current date/time |
| `get_system_info` | system | Live CPU / RAM / disk stats (`psutil`) |
| `open_application` | system | Launch a macOS application by name |
| `set_volume` | system | Set macOS output volume (0–100) |
| `run_shell_command` | system | Run a read-only shell command (substring blocklist) |
| `wikipedia_summary` | knowledge | Wikipedia REST summary lookup |
| `calculate` | knowledge | Safe AST-based math evaluator |
| `format_json` | utils | Pretty-print a JSON string |
| `word_count` | utils | Count words, characters, and lines in text |

The MCP server also registers three reusable **prompts** (`summarize`,
`explain_code`, `translate`) and one **resource** (`jarvis://info`).

## Live HUD

Open `http://localhost:8080` after running `./start.sh`. The HUD pulls real data:

- **System Diagnostics** → `GET /api/system` (live `psutil` stats)
- **Weather Intel** → `GET /api/weather?city=New York` (Open-Meteo)
- **Global Intel Feed** → `GET /api/news?type=world` (live RSS aggregation)
- **Activity Log** → `GET /api/activity` (wake/sleep + user turns from the agent)
- **MCP Server status** → `GET /api/health` (probes the SSE endpoint)

## Wake-up

Two ways to activate J.A.R.V.I.S. while he's sleeping:

- **Voice**: any of "wake up jarvis", "hey jarvis", "jarvis", "good morning jarvis", …
- **Double-clap**: two loud claps within ~0.6 seconds, detected on the raw mic stream.

He auto-sleeps after 2 minutes of inactivity, or instantly on "go to sleep" /
"stand down" / "that's all jarvis".

## License
MIT
