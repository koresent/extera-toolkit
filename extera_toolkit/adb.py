import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class AdbError(Exception):
    """Raised when an ADB command fails."""
    pass


class DeviceNotFoundError(AdbError):
    """Raised when no Android device is connected via ADB."""
    pass


DEFAULT_CANDIDATE_PACKAGES = [
    "org.telegram.messenger",
    "com.exteragram.messenger",
    "org.ayugram.messenger",
    "org.telegram.plus",
    "org.telegram.messenger.beta",
    "org.telegram.messenger.web",
]

DEFAULT_LAUNCH_ACTIVITY = "org.telegram.ui.LaunchActivity"


class AdbController:
    """Manages communication with Android devices via ADB."""

    def __init__(self, adb_path: Optional[str] = None, device_id: Optional[str] = None):
        self.adb_path = adb_path or shutil.which("adb") or "adb"
        self.device_id = device_id or os.environ.get("ANDROID_SERIAL")

    def _get_target_device_id(self) -> Optional[str]:
        if self.device_id:
            return self.device_id
        # If multiple devices connected, pick first authorized
        try:
            devs = self.list_devices()
            authorized = [d["id"] for d in devs if d["status"] == "device"]
            if authorized:
                return authorized[0]
        except Exception:
            pass
        return None

    def _base_cmd(self, target_specific: bool = True) -> List[str]:
        cmd = [self.adb_path]
        if target_specific:
            target = self._get_target_device_id()
            if target:
                cmd.extend(["-s", target])
        return cmd

    def run_cmd(
        self,
        args: List[str],
        timeout: int = 30,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        """Executes an ADB command synchronously."""
        is_general_cmd = args and args[0] in ("devices", "connect", "disconnect")
        full_cmd = self._base_cmd(target_specific=not is_general_cmd) + args
        try:
            res = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if check and res.returncode != 0:
                err_msg = res.stderr.strip() or res.stdout.strip()
                raise AdbError(f"ADB command failed ({res.returncode}): {' '.join(full_cmd)}\nError: {err_msg}")
            return res
        except subprocess.TimeoutExpired as exc:
            raise AdbError(f"ADB command timed out after {timeout}s: {' '.join(full_cmd)}") from exc
        except FileNotFoundError as exc:
            raise AdbError(f"ADB executable not found at '{self.adb_path}'") from exc

    def list_devices(self) -> List[Dict[str, str]]:
        """Lists connected ADB devices."""
        res = self.run_cmd(["devices", "-l"], check=False)
        devices = []
        for line in res.stdout.strip().splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                dev_id = parts[0]
                status = parts[1]
                details = " ".join(parts[2:]) if len(parts) > 2 else ""
                devices.append({
                    "id": dev_id,
                    "status": status,
                    "details": details,
                })
        return devices

    def check_connection(self) -> bool:
        """Verifies that at least one device is connected and authorized."""
        devices = self.list_devices()
        authorized = [d for d in devices if d["status"] == "device"]
        return len(authorized) > 0

    def connect_device(self, host_port: str) -> str:
        """Connects to a remote ADB device over Wi-Fi (e.g. 192.168.1.50:5555)."""
        res = self.run_cmd(["connect", host_port], check=False)
        return res.stdout.strip()

    def disconnect_device(self, host_port: Optional[str] = None) -> str:
        """Disconnects a Wi-Fi device or all Wi-Fi devices."""
        args = ["disconnect"]
        if host_port:
            args.append(host_port)
        res = self.run_cmd(args, check=False)
        return res.stdout.strip()

    def ensure_forward(self, local_port: int = 42690, remote_port: int = 42690) -> None:
        """Sets up port forwarding via ADB."""
        self.run_cmd(["forward", f"tcp:{local_port}", f"tcp:{remote_port}"])

    def remove_forward(self, local_port: int = 42690) -> None:
        """Removes port forwarding via ADB."""
        self.run_cmd(["forward", "--remove", f"tcp:{local_port}"], check=False)

    def ensure_reverse(self, remote_port: int, local_port: int) -> None:
        """Sets up reverse port forwarding (phone -> host)."""
        self.run_cmd(["reverse", f"tcp:{remote_port}", f"tcp:{local_port}"])

    def shell(self, command: str, timeout: int = 30, check: bool = True) -> str:
        """Runs a command inside Android shell."""
        res = self.run_cmd(["shell", command], timeout=timeout, check=check)
        return res.stdout.strip()

    def autodetect_package(self) -> Optional[str]:
        """Detects the installed Telegram/exteraGram package."""
        packages_out = self.shell("pm list packages --user 0", check=False)
        if not packages_out.strip() or "Error" in packages_out:
            packages_out = self.shell("pm list packages", check=False)
        installed = {line.replace("package:", "").strip() for line in packages_out.splitlines()}
        for candidate in DEFAULT_CANDIDATE_PACKAGES:
            if candidate in installed:
                return candidate
        # Fallback: check any package containing exteragram or ayugram
        for p in installed:
            if "exteragram" in p or "ayugram" in p:
                return p
        return None

    def get_app_pid(self, package_name: Optional[str] = None) -> Optional[int]:
        """Gets PID of the running app."""
        pkg = package_name or self.autodetect_package()
        if not pkg:
            return None
        out = self.shell(f"pidof {pkg}", check=False)
        if out:
            pids = out.split()
            try:
                return int(pids[0])
            except (ValueError, IndexError):
                pass
        return None

    def restart_app(
        self,
        package_name: Optional[str] = None,
        activity: str = DEFAULT_LAUNCH_ACTIVITY,
    ) -> None:
        """Restarts the target app cleanly."""
        pkg = package_name or self.autodetect_package()
        if not pkg:
            raise AdbError("Could not detect Telegram/exteraGram package to restart.")
        self.shell(f"am force-stop {pkg}")
        time.sleep(0.5)
        self.shell(f"am start -n {pkg}/{activity}")

    def input_tap(self, x: int, y: int) -> None:
        """Simulates a tap gesture at (x, y)."""
        self.shell(f"input tap {x} {y}")

    def input_keyevent(self, keycode: int) -> None:
        """Simulates a key event (e.g. 4 for BACK)."""
        self.shell(f"input keyevent {keycode}")

    def input_swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 250) -> None:
        """Simulates a drag/swipe gesture from (x1, y1) to (x2, y2)."""
        self.shell(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")

    def input_swipe_direction(self, direction: str, distance: int = 500) -> None:
        """Performs a swipe gesture in a named direction (up, down, left, right)."""
        # Default middle coordinates for standard mobile view
        cx, cy = 600, 1200
        d = direction.lower().strip()
        if d == "up":
            self.input_swipe(cx, cy + (distance // 2), cx, cy - (distance // 2))
        elif d == "down":
            self.input_swipe(cx, cy - (distance // 2), cx, cy + (distance // 2))
        elif d == "left":
            self.input_swipe(cx + (distance // 2), cy, cx - (distance // 2), cy)
        elif d == "right":
            self.input_swipe(cx - (distance // 2), cy, cx + (distance // 2), cy)
        else:
            raise ValueError(f"Unknown direction '{direction}'. Use 'up', 'down', 'left', or 'right'.")

    def input_back(self) -> None:
        """Simulates BACK button press."""
        self.input_keyevent(4)

    def input_text(self, text: str) -> None:
        """Types text into the currently focused input."""
        escaped = text.replace(" ", "%s").replace("'", "\\'").replace('"', '\\"')
        self.shell(f"input text '{escaped}'")

    def dump_window_hierarchy(self, remote_tmp: str = "/sdcard/window_dump.xml") -> str:
        """Dumps UI hierarchy using uiautomator and returns the XML string."""
        self.shell(f"uiautomator dump {remote_tmp}")
        res = self.shell(f"cat {remote_tmp}")
        self.shell(f"rm -f {remote_tmp}", check=False)
        return res

    def screencap(
        self,
        local_path: Optional[str] = None,
        remote_tmp: str = "/sdcard/extera_screencap.png",
    ) -> str:
        """Takes a screenshot and pulls it locally."""
        if not local_path:
            out_dir = Path(tempfile.gettempdir()) / "extera-toolkit" / "screenshots"
            out_dir.mkdir(parents=True, exist_ok=True)
            local_path = str(out_dir / f"screen_{int(time.time())}.png")
        self.shell(f"screencap -p {remote_tmp}")
        self.run_cmd(["pull", remote_tmp, local_path])
        self.shell(f"rm -f {remote_tmp}", check=False)
        return local_path

    def read_logcat(
        self,
        tag: Optional[str] = None,
        pid: Optional[int] = None,
        level: str = "D",
        tail: int = 50,
        grep_pattern: Optional[str] = None,
    ) -> List[str]:
        """Reads recent logcat entries."""
        args = ["logcat", "-d"]
        if tag:
            args.extend(["-s", f"{tag}:{level}"])
        if pid:
            args.extend(["--pid", str(pid)])
        res = self.run_cmd(args, check=False)
        lines = res.stdout.strip().splitlines()
        if grep_pattern:
            rx = re.compile(grep_pattern, re.IGNORECASE)
            lines = [l for l in lines if rx.search(l)]
        return lines[-tail:] if tail > 0 else lines

    def clear_logcat(self) -> None:
        """Clears logcat buffer."""
        self.run_cmd(["logcat", "-c"], check=False)

    def get_crash_log(self, tail: int = 50) -> List[str]:
        """Reads recent crash traces from logcat crash buffer and AndroidRuntime."""
        crash_buf = self.run_cmd(["logcat", "-d", "-b", "crash"], check=False).stdout.strip().splitlines()
        runtime_buf = self.run_cmd(["logcat", "-d", "-s", "AndroidRuntime:E"], check=False).stdout.strip().splitlines()
        combined = crash_buf + [l for l in runtime_buf if l not in crash_buf]
        return combined[-tail:] if tail > 0 else combined

    def fs_cat(self, remote_path: str) -> str:
        """Reads content of a file on device."""
        return self.shell(f"cat '{remote_path}'")

    def fs_tail(self, remote_path: str, lines: int = 50) -> str:
        """Reads the last N lines of a file on device."""
        return self.shell(f"tail -n {lines} '{remote_path}'")

    def fs_grep(self, pattern: str, remote_path: str) -> List[str]:
        """Searches for pattern inside a file or path on device."""
        res = self.shell(f"grep -n -E '{pattern}' '{remote_path}'", check=False)
        return [l for l in res.splitlines() if l.strip()]

    def fs_ls(self, remote_path: str) -> List[str]:
        """Lists files and directories on device."""
        res = self.shell(f"ls -la '{remote_path}'", check=False)
        return [l for l in res.splitlines() if l.strip()]
