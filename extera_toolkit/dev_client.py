import json
import socket
import time
import uuid
from typing import Any, Dict, List, Optional

from .adb import AdbController, AdbError


class DevServerError(Exception):
    """Raised when dev server communication fails."""
    pass


class DevServerClient:
    """TCP JSON-RPC client for exteraGram's built-in development server (default port 42690)."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 42690,
        timeout: float = 5.0,
        auto_forward: bool = True,
        adb_controller: Optional[AdbController] = None,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.auto_forward = auto_forward
        self.adb = adb_controller or AdbController()

    def _create_connection(self) -> socket.socket:
        """Connects to dev server, automatically attempting ADB forward if connection fails."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((self.host, self.port))
            return sock
        except (ConnectionRefusedError, socket.timeout, OSError) as exc:
            if self.auto_forward:
                try:
                    self.adb.ensure_forward(self.port, self.port)
                    # Retry once after forward
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(self.timeout)
                    sock.connect((self.host, self.port))
                    return sock
                except Exception as inner_exc:
                    raise DevServerError(
                        f"Cannot connect to dev server at {self.host}:{self.port} (auto-forward failed: {inner_exc})"
                    ) from inner_exc
            raise DevServerError(
                f"Cannot connect to dev server at {self.host}:{self.port}. "
                f"Make sure exteraGram dev server is enabled in settings and ADB forward is active."
            ) from exc

    def send_raw_command(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Sends a JSON-RPC message and reads the response matching '#' id."""
        req_id = payload.get("#") or f"req-{uuid.uuid4().hex[:8]}"
        payload["#"] = req_id

        sock = self._create_connection()
        try:
            req_data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
            sock.sendall(req_data)

            # Read until full JSON response matching request id
            buffer = ""
            start_time = time.time()
            decoder = json.JSONDecoder()

            while time.time() - start_time < self.timeout:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")

                # Try parsing JSON objects from buffer
                stripped = buffer.strip()
                if stripped:
                    try:
                        # Attempt direct decode
                        parsed, _ = decoder.raw_decode(stripped)
                        if isinstance(parsed, dict) and parsed.get("#") == req_id:
                            return parsed
                    except json.JSONDecodeError:
                        # Maybe multiple JSON objects or partial
                        idx = 0
                        while idx < len(stripped):
                            try:
                                parsed, end_idx = decoder.raw_decode(stripped[idx:])
                                if isinstance(parsed, dict) and parsed.get("#") == req_id:
                                    return parsed
                                idx += end_idx
                            except json.JSONDecodeError:
                                break

            raise DevServerError(f"Timeout waiting for response to request #{req_id} (received: {buffer[:200]}...)")
        finally:
            sock.close()

    def ping(self) -> bool:
        """Tests connection to dev server."""
        try:
            res = self.send_raw_command({"@": "ping"})
            return bool(res.get("pong", False))
        except Exception:
            return False

    def get_plugins(self) -> List[Dict[str, Any]]:
        """Retrieves list of loaded plugins and their state."""
        res = self.send_raw_command({"@": "get_plugins"})
        plugins = res.get("plugins") or res.get("data")
        if isinstance(plugins, list):
            return plugins
        # Some versions return dictionary of id -> info
        if isinstance(plugins, dict):
            return [{"id": k, **v} if isinstance(v, dict) else {"id": k, "value": v} for k, v in plugins.items()]
        return []

    def enable_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Enables an installed plugin."""
        return self.send_raw_command({"@": "enable_plugin", "plugin_id": plugin_id})

    def disable_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Disables an installed plugin."""
        return self.send_raw_command({"@": "disable_plugin", "plugin_id": plugin_id})

    def reload_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Reloads a plugin in runtime."""
        return self.send_raw_command({"@": "reload_plugin", "plugin_id": plugin_id})

    def write_plugin(self, plugin_id: str, content: str) -> Dict[str, Any]:
        """Installs or updates a plugin's Python source code and reloads it."""
        return self.send_raw_command({
            "@": "write_plugin",
            "plugin_id": plugin_id,
            "content": content,
        })

    def remove_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Deletes an installed plugin from device."""
        return self.send_raw_command({"@": "remove_plugin", "plugin_id": plugin_id})

    def start_debugger(self, host: str = "127.0.0.1", port: int = 5678, platform: str = "vscode") -> Dict[str, Any]:
        """Starts remote debugger attach endpoint."""
        return self.send_raw_command({
            "@": "start_debugger",
            "host": host,
            "port": port,
            "platform": platform,
        })

    def stop_debugger(self, platform: str = "vscode") -> Dict[str, Any]:
        """Stops remote debugger."""
        return self.send_raw_command({
            "@": "stop_debugger",
            "platform": platform,
        })
