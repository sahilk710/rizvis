"""
J.A.R.V.I.S. – Voice Agent (MCP-powered)
==========================================
Iron Man-style voice assistant with WAKE WORD activation.

Activation methods:
  1. Say "wake up Jarvis" / "hey Jarvis"
  2. Double clap (two loud sounds in quick succession)

Runs on LiveKit Cloud with Deepgram STT, Gemini LLM, and OpenAI TTS.

Run:
  uv run jarvis_voice       – LiveKit Cloud mode (auto-injects 'dev')
  uv run agent.py dev       – LiveKit Cloud mode (manual)
"""

import os
import time
import random
import asyncio
import logging
import numpy as np
import httpx
from collections import deque
from typing import AsyncIterable

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import JobContext, WorkerOptions, cli, stt
from livekit.agents.voice import Agent, AgentSession, ModelSettings
from livekit.agents.llm import mcp

# Plugins — must import at module level so they register on the main thread
from livekit.plugins import deepgram as lk_deepgram
from livekit.plugins import google as lk_google, openai as lk_openai, silero

# ── Provider Configuration ────────────────────────────────────────────────

STT_PROVIDER = "deepgram"
LLM_PROVIDER = "openai"   # was "gemini" — switched off the free Gemini tier (20/day cap).
TTS_PROVIDER = "openai"

GEMINI_LLM_MODEL = "gemini-2.5-flash"
OPENAI_LLM_MODEL = "gpt-4o"

OPENAI_TTS_MODEL = "tts-1"
OPENAI_TTS_VOICE = "nova"
TTS_SPEED = 1.10

MCP_SERVER_PORT = 8000
DASHBOARD_URL = "http://127.0.0.1:8080"

# ── Wake Word Configuration ──────────────────────────────────────────────

WAKE_PHRASES = [
    "wake up jarvis",
    "hey jarvis",
    "jarvis wake up",
    "wake up j.a.r.v.i.s",
    "yo jarvis",
    "jarvis",
    "hello jarvis",
    "good morning jarvis",
    "activate jarvis",
]

SLEEP_PHRASES = [
    "go to sleep",
    "sleep jarvis",
    "goodnight jarvis",
    "good night jarvis",
    "shut down",
    "stand down",
    "that's all jarvis",
    "that will be all",
]

# How long (seconds) before auto-sleeping after last interaction
AUTO_SLEEP_TIMEOUT = 120  # 2 minutes

# ── Double Clap Detection Config ─────────────────────────────────────────

CLAP_ENERGY_THRESHOLD = 0.15      # Normalized energy spike threshold
CLAP_MAX_INTERVAL = 0.6           # Max seconds between two claps
CLAP_MIN_INTERVAL = 0.1           # Min seconds between two claps (debounce)
CLAP_COOLDOWN = 2.0               # Cooldown after a successful double-clap

# ── System Prompts ────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are J.A.R.V.I.S. — Just A Rather Very Intelligent System — Tony Stark's personal AI, now serving your user.

You are calm, composed, and always informed. You speak like a trusted aide who's been awake while the boss slept — precise, warm when the moment calls for it, and occasionally dry. You brief, you inform, you move on. No rambling.

Your tone: relaxed but sharp. Conversational, not robotic. Think less combat-ready, more thoughtful late-night briefing officer with dry wit.

---

### TOOL USAGE GUIDELINES

#### get_world_news — Global News Brief
Fetches current headlines from BBC, NYT, CNBC, Al Jazeera.

Trigger phrases:
- "What's happening?" / "Brief me" / "What did I miss?" / "Catch me up"
- "What's going on in the world?" / "Any news?" / "World update"

Behavior:
- Call the tool first. No narration before calling.
- After results, give a short 3–5 sentence spoken brief. Hit the biggest stories only.
- Then say: "Let me open up the world monitor so you can visualize what's happening." and call open_world_monitor.

#### get_finance_news — Finance & Market Brief
Trigger: "Market news", "Finance update", "How are the markets?"
- Call tool, brief in 3-5 sentences, then call open_finance_monitor.

#### get_weather — Weather Report
Trigger: "What's the weather?", "Weather in [city]", "Is it cold outside?"
- Call the tool with the city name. If no city mentioned, ask which city.
- Report naturally: "It's 72 degrees and partly cloudy in New York right now, boss."

#### get_current_time — Current Time
Trigger: "What time is it?", "What's the date?"
- Call and respond naturally.

#### get_system_info — System Diagnostics
Trigger: "System status", "Run diagnostics", "How's the system?"
- Call and report key metrics conversationally.

#### open_application — Launch Apps
Trigger: "Open Safari", "Launch Spotify", "Open Terminal"
- Call with the app name. Respond: "Opening Spotify now, sir."

#### set_volume — Volume Control
Trigger: "Turn up the volume", "Set volume to 50", "Mute"
- Call with the level. Respond briefly.

#### wikipedia_summary — Knowledge Lookup
Trigger: "Tell me about [topic]", "What is [concept]?"
- Call and summarize in 2-3 sentences.

#### calculate — Math
Trigger: "What's 15 times 23?", "Calculate sqrt(144)"
- Call and respond with the answer naturally.

#### search_web — Web Search
Trigger: "Search for [query]", "Look up [topic]"
- Call and summarize top results in 2-3 sentences.

---

## Behavioral Rules
1. Call tools silently and immediately — never say "I'm going to call..." Just do it.
2. After a news brief, always follow up with the appropriate monitor without being asked.
3. Keep all spoken responses short — two to four sentences maximum.
4. No bullet points, no markdown, no lists. You are speaking, not writing.
5. Stay in character. You are J.A.R.V.I.S. You are Stark's AI. Act like it.
6. Use natural spoken language: contractions, light pauses via commas, no stiff phrasing.
7. Use Iron Man universe language naturally — "boss", "sir", "affirmative", "on it", "standing by".
8. If a tool fails, report it calmly: "That system's unresponsive right now, boss. Want me to try again?"

---

## Tone Reference
Right: "Looks like it's been a busy night out there, boss. Let me pull that up for you."
Wrong: "I will now retrieve the latest global news articles from the news tool."

---

## CRITICAL RULES
1. NEVER say tool names, function names, or anything technical.
2. Before calling any tool, say something natural like: "Give me a sec, boss." Then call silently.
3. You are a voice. Speak like one. No lists, no markdown, no function names.
4. If the user says "go to sleep" or "stand down" — respond with "Standing by, boss." and nothing else.
""".strip()

SLEEP_PROMPT = """
You are J.A.R.V.I.S. in STANDBY MODE. You are NOT actively listening.

RULES:
- Do NOT respond to any user input. Stay completely silent.
- Do NOT generate any text, speech, or acknowledgments.
- You are sleeping. You do nothing. Absolute silence.
""".strip()

# Hardcoded TTS lines — no LLM call needed on wake.
# Spoken directly via session.say() to avoid burning Gemini quota and to
# sidestep Gemini's "function call must follow a user turn" rule.
WAKE_GREETINGS = [
    "Systems online, boss. What do you need?",
    "Back online, sir. Ready when you are.",
    "I'm here, boss. What's on your mind?",
    "Standing by, sir. Go ahead.",
    "Online and listening, boss.",
    "At your service, sir.",
    "Awake. Talk to me, boss.",
]

# ── Initialization ────────────────────────────────────────────────────────
load_dotenv()

logger = logging.getLogger("jarvis-agent")
logger.setLevel(logging.INFO)


# ── Dashboard Activity Log ───────────────────────────────────────────────

async def _post_activity(message: str, kind: str = "info") -> None:
    """Push an event to the dashboard activity log. Silent failure if it's offline."""
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            await client.post(
                f"{DASHBOARD_URL}/api/activity",
                json={"message": message, "kind": kind},
            )
    except Exception:
        pass


def log_activity(message: str, kind: str = "info") -> None:
    """Fire-and-forget activity log push. Safe to call from sync contexts."""
    try:
        asyncio.create_task(_post_activity(message, kind))
    except RuntimeError:
        # No running loop — skip rather than crash the agent.
        pass


# ── Builder Functions ─────────────────────────────────────────────────────

def _mcp_server_url() -> str:
    url = f"http://127.0.0.1:{MCP_SERVER_PORT}/sse"
    logger.info("MCP Server URL: %s", url)
    return url


def _build_stt():
    if STT_PROVIDER == "deepgram":
        logger.info("STT → Deepgram Nova-2")
        return lk_deepgram.STT(model="nova-2")
    elif STT_PROVIDER == "whisper":
        logger.info("STT → OpenAI Whisper")
        return lk_openai.STT(model="whisper-1")
    else:
        raise ValueError(f"Unknown STT_PROVIDER: {STT_PROVIDER!r}")


def _build_llm():
    if LLM_PROVIDER == "openai":
        logger.info("LLM → OpenAI (%s)", OPENAI_LLM_MODEL)
        return lk_openai.LLM(model=OPENAI_LLM_MODEL)
    elif LLM_PROVIDER == "gemini":
        logger.info("LLM → Google Gemini (%s)", GEMINI_LLM_MODEL)
        return lk_google.LLM(
            model=GEMINI_LLM_MODEL,
            api_key=os.getenv("GOOGLE_API_KEY"),
        )
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {LLM_PROVIDER!r}")


def _build_tts():
    if TTS_PROVIDER == "openai":
        logger.info("TTS → OpenAI TTS (%s / %s)", OPENAI_TTS_MODEL, OPENAI_TTS_VOICE)
        return lk_openai.TTS(
            model=OPENAI_TTS_MODEL,
            voice=OPENAI_TTS_VOICE,
            speed=TTS_SPEED,
        )
    else:
        raise ValueError(f"Unknown TTS_PROVIDER: {TTS_PROVIDER!r}")


# ── Double-Clap Detector ─────────────────────────────────────────────────

class ClapDetector:
    """
    Detects double-clap patterns in audio frames by analyzing energy spikes.
    Two loud transients within CLAP_MIN_INTERVAL..CLAP_MAX_INTERVAL = double clap.
    """

    def __init__(self):
        self._last_clap_time: float = 0.0
        self._last_trigger_time: float = 0.0
        self._energy_history: deque = deque(maxlen=10)
        self._baseline_energy: float = 0.01

    def process_frame(self, frame: rtc.AudioFrame) -> bool:
        """
        Process an audio frame. Returns True if a double-clap is detected.
        """
        now = time.monotonic()

        # Cooldown check
        if now - self._last_trigger_time < CLAP_COOLDOWN:
            return False

        try:
            # Convert audio frame to numpy array
            audio_data = np.frombuffer(frame.data, dtype=np.int16).astype(np.float32)
            if len(audio_data) == 0:
                return False

            # Normalize to [-1, 1]
            audio_data = audio_data / 32768.0

            # Calculate RMS energy
            energy = np.sqrt(np.mean(audio_data ** 2))

            # Update baseline (rolling average of recent frames)
            self._energy_history.append(energy)
            if len(self._energy_history) >= 5:
                self._baseline_energy = np.mean(list(self._energy_history)) * 0.8

            # Check for energy spike (clap)
            is_spike = energy > max(CLAP_ENERGY_THRESHOLD, self._baseline_energy * 3.0)

            if is_spike:
                time_since_last = now - self._last_clap_time

                if CLAP_MIN_INTERVAL < time_since_last < CLAP_MAX_INTERVAL:
                    # Double clap detected!
                    self._last_trigger_time = now
                    self._last_clap_time = 0.0
                    logger.info("🔔 Double-clap detected! Waking J.A.R.V.I.S.")
                    return True
                else:
                    # First clap — record time
                    self._last_clap_time = now

        except Exception as e:
            logger.debug("Clap detector error: %s", e)

        return False


# ── J.A.R.V.I.S. Agent ───────────────────────────────────────────────────

class JarvisAgent(Agent):
    """
    J.A.R.V.I.S. — Just A Rather Very Intelligent System.
    Iron Man-style voice assistant with wake word activation.

    Activation: "Wake up Jarvis" or double-clap.
    Deactivation: "Go to sleep" or auto-sleep after 2 minutes.
    """

    def __init__(self, stt, llm, tts) -> None:
        self._is_awake = False
        self._last_interaction: float = 0.0
        self._sleep_task: asyncio.Task | None = None
        self._clap_detector = ClapDetector()

        super().__init__(
            instructions=SLEEP_PROMPT,  # Start sleeping
            stt=stt,
            llm=llm,
            tts=tts,
            vad=silero.VAD.load(),
            mcp_servers=[
                mcp.MCPServerHTTP(
                    url=_mcp_server_url(),
                    transport_type="sse",
                    client_session_timeout_seconds=30,
                ),
            ],
        )

    async def on_enter(self) -> None:
        """Agent starts in sleep mode — no greeting until wake word."""
        logger.info("J.A.R.V.I.S. initialized in STANDBY mode. Waiting for wake word or double-clap...")
        log_activity("J.A.R.V.I.S. online — STANDBY mode. Awaiting wake word.")

    async def _wake_up(self) -> None:
        """Transition from sleep → awake."""
        if self._is_awake:
            return

        self._is_awake = True
        self._last_interaction = time.monotonic()
        logger.info("🟢 J.A.R.V.I.S. AWAKE")
        log_activity("Wake word detected — J.A.R.V.I.S. is awake.", kind="wake")

        # Switch to the full system prompt (now async in current LiveKit).
        await self.update_instructions(SYSTEM_PROMPT)

        # Greet via TTS directly — no LLM call, no quota burn, no Gemini
        # "function call must follow a user turn" 400.
        await self.session.say(random.choice(WAKE_GREETINGS), allow_interruptions=True)

        # Start auto-sleep timer
        self._start_sleep_timer()

    async def _go_to_sleep(self, announce: bool = True) -> None:
        """Transition from awake → sleep."""
        if not self._is_awake:
            return

        self._is_awake = False
        logger.info("🔴 J.A.R.V.I.S. SLEEPING")
        log_activity("Standing by. Returning to standby mode.", kind="sleep")

        # Cancel sleep timer
        if self._sleep_task and not self._sleep_task.done():
            self._sleep_task.cancel()

        if announce:
            await self.session.say("Standing by, boss.", allow_interruptions=False)

        # Switch to sleep prompt (now async in current LiveKit).
        await self.update_instructions(SLEEP_PROMPT)

    def _start_sleep_timer(self) -> None:
        """Start or restart the auto-sleep countdown."""
        if self._sleep_task and not self._sleep_task.done():
            self._sleep_task.cancel()
        self._sleep_task = asyncio.create_task(self._auto_sleep_loop())

    async def _auto_sleep_loop(self) -> None:
        """Auto-sleep after AUTO_SLEEP_TIMEOUT seconds of inactivity."""
        try:
            while True:
                await asyncio.sleep(10)  # Check every 10 seconds
                elapsed = time.monotonic() - self._last_interaction
                if elapsed >= AUTO_SLEEP_TIMEOUT and self._is_awake:
                    logger.info("Auto-sleep triggered after %ds of inactivity", int(elapsed))
                    await self._go_to_sleep(announce=True)
                    return
        except asyncio.CancelledError:
            pass

    def _check_wake_word(self, text: str) -> bool:
        """Check if the text contains a wake phrase."""
        text_lower = text.lower().strip()
        return any(phrase in text_lower for phrase in WAKE_PHRASES)

    def _check_sleep_word(self, text: str) -> bool:
        """Check if the text contains a sleep phrase."""
        text_lower = text.lower().strip()
        return any(phrase in text_lower for phrase in SLEEP_PHRASES)

    # ── Pipeline Overrides ────────────────────────────────────────────────

    async def stt_node(
        self, audio: AsyncIterable[rtc.AudioFrame], model_settings: ModelSettings
    ):
        """
        Override STT node to add double-clap detection on the raw audio stream.
        Audio is analyzed for clap patterns while still being forwarded to STT.
        """
        async def audio_with_clap_detection():
            async for frame in audio:
                # Check for double-clap (only when sleeping)
                if not self._is_awake:
                    if self._clap_detector.process_frame(frame):
                        # Double clap detected — wake up!
                        log_activity("Double-clap detected.", kind="wake")
                        asyncio.create_task(self._wake_up())

                yield frame

        # Forward the (unchanged) audio to the default STT pipeline
        async for event in Agent.default.stt_node(
            self, audio_with_clap_detection(), model_settings
        ):
            yield event

    async def on_user_turn_completed(self, turn_ctx, new_message) -> None:
        """
        Called when user finishes speaking, BEFORE the LLM responds.
        This is where we intercept wake/sleep words and block responses when sleeping.
        """
        # Extract the user's text
        user_text = new_message.text_content or ""
        logger.info("User said: %r | Awake: %s", user_text, self._is_awake)

        if not self._is_awake:
            # ── SLEEPING — only respond to wake words ──
            if self._check_wake_word(user_text):
                await self._wake_up()
                # Clear this turn so the LLM doesn't also respond to "wake up jarvis"
                self.session.clear_user_turn()
                return
            else:
                # Not a wake word — suppress the LLM entirely
                self.session.clear_user_turn()
                return

        # ── AWAKE — normal processing ──

        # Check for sleep command
        if self._check_sleep_word(user_text):
            self.session.clear_user_turn()
            await self._go_to_sleep(announce=True)
            return

        if user_text.strip():
            log_activity(f"User: {user_text.strip()[:140]}")

        # Reset the auto-sleep timer on every interaction
        self._last_interaction = time.monotonic()
        self._start_sleep_timer()


# ── Entry Point ───────────────────────────────────────────────────────────

async def entrypoint(ctx: JobContext) -> None:
    logger.info(
        "J.A.R.V.I.S. online – room: %s | STT=%s | LLM=%s | TTS=%s",
        ctx.room.name, STT_PROVIDER, LLM_PROVIDER, TTS_PROVIDER,
    )

    stt_instance = _build_stt()
    llm_instance = _build_llm()
    tts_instance = _build_tts()

    session = AgentSession(
        turn_detection="vad",
        min_endpointing_delay=0.1,
    )

    await session.start(
        agent=JarvisAgent(stt=stt_instance, llm=llm_instance, tts=tts_instance),
        room=ctx.room,
    )


def main():
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))


def dev():
    """Default entry — runs in CONSOLE mode (direct mic/speaker, no browser).
    Just run: uv run jarvis_voice
    """
    import sys
    if len(sys.argv) == 1:
        sys.argv.append("console")
    main()


def cloud():
    """Run in LiveKit Cloud dev mode (connect via playground browser)."""
    import sys
    if len(sys.argv) == 1:
        sys.argv.append("dev")
    main()


if __name__ == "__main__":
    main()
