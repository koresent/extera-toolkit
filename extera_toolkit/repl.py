import json
import socket
import threading
import time
import traceback
from typing import Any, Dict, Optional

from .adb import AdbController
from .dev_client import DevServerClient, DevServerError

EVAL_PLUGIN_ID = "__extera_toolkit_eval_probe__"


def _build_probe_source(code_snippet: str, host_port: int, is_eval: bool = True) -> str:
    """Generates source code for the ephemeral probe plugin."""
    mode = "eval" if is_eval else "exec"
    source = f'''# -*- coding: utf-8 -*-
# Auto-generated ephemeral evaluation probe for extera-toolkit
import sys
import io
import json
import socket
import traceback
from base_plugin import BasePlugin

__id__ = "{EVAL_PLUGIN_ID}"
__name__ = "Evaluation Probe"
__version__ = "0.0.1"

class EvalProbePlugin(BasePlugin):
    def on_plugin_load(self):
        output_buffer = io.StringIO()
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = output_buffer
        sys.stderr = output_buffer
        
        result_val = None
        error_val = None
        
        try:
            # Common imports made available in eval scope
            from org.telegram.messenger import (
                AndroidUtilities,
                ApplicationLoader,
                FileLog,
                LocaleController,
                MessagesController,
                MessagesStorage,
                NotificationCenter,
                SendMessagesHelper,
                SharedConfig,
                UserConfig,
            )
            from org.telegram.tgnet import ConnectionsManager, TLRPC
            from java import jclass, dynamic_proxy, jint, jlong
        except Exception:
            pass

        try:
            scope = locals()
            code_str = {repr(code_snippet)}
            if "{mode}" == "eval":
                result_val = eval(code_str, globals(), scope)
            else:
                exec(code_str, globals(), scope)
                result_val = scope.get("result", None)
        except Exception:
            error_val = traceback.format_exc()
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        captured_stdout = output_buffer.getvalue()
        
        # Serialize result safely
        payload = {{
            "success": error_val is None,
            "stdout": captured_stdout,
            "error": error_val,
            "result_repr": repr(result_val) if result_val is not None else None,
            "result_str": str(result_val) if result_val is not None else None,
        }}
        if isinstance(result_val, (dict, list, int, float, bool, str, type(None))):
            payload["result"] = result_val

        # Transmit back to host
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3.0)
            s.connect(("127.0.0.1", {host_port}))
            s.sendall(json.dumps(payload, ensure_ascii=False).encode("utf-8") + b"\\n")
            s.close()
        except Exception:
            try:
                with open("/sdcard/Download/__extera_eval_fallback.json", "w") as f:
                    json.dumps(payload, f)
            except Exception:
                pass
'''
    return source


class RuntimeEvaluator:
    """Executes arbitrary Python/Java expressions inside running Telegram process via DevServer."""

    def __init__(
        self,
        dev_client: Optional[DevServerClient] = None,
        adb_controller: Optional[AdbController] = None,
        listen_port: int = 42699,
        timeout: float = 6.0,
    ):
        self.adb = adb_controller or AdbController()
        self.dev = dev_client or DevServerClient(adb_controller=self.adb)
        self.listen_port = listen_port
        self.timeout = timeout

    def evaluate(self, snippet: str, is_eval: bool = True) -> Dict[str, Any]:
        """Evaluates expression or executes code in Telegram runtime and returns result."""
        # 1. Setup reverse port so phone can connect back to host
        try:
            self.adb.ensure_reverse(self.listen_port, self.listen_port)
        except Exception:
            pass

        result_container: Dict[str, Any] = {}
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.settimeout(self.timeout)
        server_sock.bind(("127.0.0.1", self.listen_port))
        server_sock.listen(1)

        def _listener():
            try:
                conn, _ = server_sock.accept()
                conn.settimeout(2.0)
                data = b""
                while True:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                    if b"\n" in chunk:
                        break
                conn.close()
                if data:
                    parsed = json.loads(data.decode("utf-8", errors="replace").strip())
                    result_container.update(parsed)
            except Exception:
                pass

        listen_thread = threading.Thread(target=_listener, daemon=True)
        listen_thread.start()

        probe_code = _build_probe_source(snippet, self.listen_port, is_eval=is_eval)

        try:
            # 2. Write probe plugin to dev server
            self.dev.write_plugin(EVAL_PLUGIN_ID, probe_code)

            # Wait for listener thread
            listen_thread.join(timeout=self.timeout)

            # Fallback if listener didn't catch (e.g. adb reverse issue)
            if not result_container:
                try:
                    fallback_content = self.adb.shell("cat /sdcard/Download/__extera_eval_fallback.json", check=False)
                    if fallback_content:
                        result_container.update(json.loads(fallback_content))
                        self.adb.shell("rm -f /sdcard/Download/__extera_eval_fallback.json", check=False)
                except Exception:
                    pass

            if not result_container:
                return {
                    "success": False,
                    "error": f"Evaluation timed out after {self.timeout}s without response from app runtime.",
                }
            return result_container
        finally:
            try:
                server_sock.close()
            except Exception:
                pass
            # Clean up ephemeral probe
            try:
                self.dev.remove_plugin(EVAL_PLUGIN_ID)
            except Exception:
                pass
