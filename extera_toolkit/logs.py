import re
from typing import Any, Dict, List, Optional

from .adb import AdbController

LOGCAT_LINE_REGEX = re.compile(
    r"^(?:\d\d-\d\d\s+\d\d:\d\d:\d\d\.\d+\s+\d+\s+\d+\s+)?([VDIWEF])\s+([^:]+):\s*(.*)$"
)


def clean_log_line(line: str) -> Dict[str, Any]:
    """Parses and strips verbose Android logcat prefixes to minimize LLM token waste."""
    match = LOGCAT_LINE_REGEX.match(line)
    if match:
        lvl, tag, msg = match.groups()
        return {
            "level": lvl,
            "tag": tag.strip(),
            "message": msg.strip(),
        }
    return {
        "level": "I",
        "tag": "raw",
        "message": line.strip(),
    }


class LogMonitor:
    """Monitors, extracts, and filters plugin and application logs."""

    def __init__(self, adb_controller: Optional[AdbController] = None):
        self.adb = adb_controller or AdbController()

    def get_logs(
        self,
        plugin_id: Optional[str] = None,
        level: str = "D",
        tail: int = 50,
        grep_pattern: Optional[str] = None,
        include_crashes: bool = True,
    ) -> List[Dict[str, Any]]:
        """Extracts filtered logcat records for a specific plugin or the whole app."""
        tag = f"plugin.{plugin_id}" if plugin_id else None
        pid = self.adb.get_app_pid()

        raw_lines = self.adb.read_logcat(
            tag=tag,
            pid=pid if not tag else None,
            level=level,
            tail=tail,
            grep_pattern=grep_pattern,
        )

        # If plugin specific tag returned few lines, also search general lines for plugin_id
        if plugin_id and len(raw_lines) < 5:
            extra_lines = self.adb.read_logcat(
                tag=None,
                pid=pid,
                level=level,
                tail=tail,
                grep_pattern=plugin_id,
            )
            raw_lines = sorted(list(set(raw_lines + extra_lines)))

        parsed = [clean_log_line(line) for line in raw_lines if line.strip()]

        if include_crashes:
            # Check for recent uncaught exceptions or tracebacks
            crash_lines = self.adb.read_logcat(
                tag="AndroidRuntime",
                level="E",
                tail=15,
            )
            for cl in crash_lines:
                parsed.append(clean_log_line(cl))

        return parsed[-tail:] if tail > 0 else parsed

    def clear(self) -> None:
        """Clears Android logcat buffer."""
        self.adb.clear_logcat()
