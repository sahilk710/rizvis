"""
System tools — time, system info, macOS app launcher, volume control, shell commands.

`get_system_stats` returns raw numbers and is consumed by both the MCP tool
and the dashboard backend.
"""

import datetime
import platform
import subprocess

import psutil


def get_system_stats() -> dict:
    """Raw system stats — numbers, not formatted strings. Used by the dashboard API."""
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    cpu_percent = psutil.cpu_percent(interval=0.5)

    return {
        "os": platform.system(),
        "os_version": (
            platform.mac_ver()[0]
            if platform.system() == "Darwin"
            else platform.version()
        ),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
        "cpu_cores": psutil.cpu_count(),
        "cpu_percent": round(cpu_percent, 1),
        "ram_total_gb": round(mem.total / (1024**3), 1),
        "ram_used_gb": round(mem.used / (1024**3), 1),
        "ram_percent": round(mem.percent, 1),
        "disk_total_gb": round(disk.total / (1024**3)),
        "disk_used_gb": round(disk.used / (1024**3)),
        "disk_percent": round(disk.percent, 1),
    }


def register(mcp):

    @mcp.tool()
    def get_current_time() -> str:
        """Return the current date and time in a human-readable format with ISO 8601."""
        now = datetime.datetime.now()
        return (
            f"**Date:** {now.strftime('%A, %B %d, %Y')}\n"
            f"**Time:** {now.strftime('%I:%M %p')}\n"
            f"**ISO:** {now.isoformat()}"
        )

    @mcp.tool()
    def get_system_info() -> dict:
        """Return information about the host system including OS, CPU, RAM, disk, and Python version."""
        return get_system_stats()

    @mcp.tool()
    def open_application(app_name: str) -> str:
        """
        Open a macOS application by name.
        Examples: open_application("Safari"), open_application("Spotify"), open_application("Terminal")
        """
        try:
            subprocess.Popen(
                ["open", "-a", app_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            return f"Opening {app_name} now, sir."
        except Exception as e:
            return f"I couldn't open {app_name}: {str(e)}"

    @mcp.tool()
    def set_volume(level: int) -> str:
        """
        Set the macOS system volume. Level should be between 0 (mute) and 100 (max).
        Examples: set_volume(50), set_volume(0), set_volume(100)
        """
        level = max(0, min(100, level))
        try:
            subprocess.run(
                ["osascript", "-e", f"set volume output volume {level}"],
                capture_output=True,
                timeout=5,
            )
            if level == 0:
                return "Muted, sir."
            return f"Volume set to {level}%, sir."
        except Exception as e:
            return f"Couldn't adjust the volume: {str(e)}"

    @mcp.tool()
    def run_shell_command(command: str) -> str:
        """
        Execute a safe shell command on macOS and return the output.
        Only use for informational commands (ls, cat, echo, df, uptime, etc.).
        Do NOT use for destructive commands (rm, mv, etc.).
        """
        dangerous = ["rm ", "rm -", "mkfs", "dd ", "format", "> /dev", "sudo", "chmod 777"]
        cmd_lower = command.lower().strip()
        for d in dangerous:
            if d in cmd_lower:
                return f"I can't execute that command for safety reasons, sir. '{command}' looks potentially destructive."

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            output = result.stdout.strip()
            if result.returncode != 0:
                error = result.stderr.strip()
                return f"Command failed (exit {result.returncode}):\n{error}"
            return output[:2000] if output else "Command executed successfully (no output)."
        except subprocess.TimeoutExpired:
            return "Command timed out after 10 seconds, sir."
        except Exception as e:
            return f"Couldn't execute that command: {str(e)}"
