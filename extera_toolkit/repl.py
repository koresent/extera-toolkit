import json
import socket
import threading
import time
import traceback
from typing import Any, Dict, List, Optional, Union

from .adb import AdbController
from .dev_client import DevServerClient, DevServerError
from .interop import generate_hook_snippet, generate_stub_code, search_catalog_classes

EVAL_PLUGIN_ID = "__extera_toolkit_eval_probe__"


def _build_probe_source(code_snippet: str, host_port: int, is_eval: bool = True) -> str:
    """Generates source code for the ephemeral probe plugin."""
    mode = "eval" if is_eval else "exec"
    source = f'''# -*- coding: utf-8 -*-
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
        
        payload = {{
            "success": error_val is None,
            "stdout": captured_stdout,
            "error": error_val,
            "result_repr": repr(result_val) if result_val is not None else None,
            "result_str": str(result_val) if result_val is not None else None,
        }}
        if isinstance(result_val, (dict, list, int, float, bool, str, type(None))):
            payload["result"] = result_val

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
            self.dev.write_plugin(EVAL_PLUGIN_ID, probe_code)
            listen_thread.join(timeout=self.timeout)

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
            try:
                self.dev.remove_plugin(EVAL_PLUGIN_ID)
            except Exception:
                pass

    def inspect_class(self, class_name: str) -> Dict[str, Any]:
        """Introspects fields, methods, and hierarchy of a Java or Python class in Telegram runtime."""
        code = f"""
def _do_inspect():
    target = {repr(class_name)}
    cls = None
    try:
        from hook_utils import find_class
        cls = find_class(target)
    except Exception:
        pass
    if cls is None:
        try:
            from java.lang import Class
            cls = Class.forName(target)
        except Exception:
            pass
    if cls is None:
        import importlib
        parts = target.rsplit(".", 1)
        if len(parts) == 2:
            mod = importlib.import_module(parts[0])
            cls = getattr(mod, parts[1], None)
        else:
            cls = globals().get(target)

    if cls is None:
        return {{"error": f"Class '{{target}}' could not be resolved."}}

    out = {{"class": str(target)}}
    if hasattr(cls, "getDeclaredMethods"):
        out["is_java"] = True
        sup = cls.getSuperclass()
        out["superclass"] = sup.getName() if sup else None

        fields = []
        for f in cls.getDeclaredFields():
            fields.append({{"name": str(f.getName()), "type": str(f.getType().getSimpleName())}})
        out["fields"] = sorted(fields, key=lambda x: x["name"])

        methods = []
        for m in cls.getDeclaredMethods():
            params = [str(p.getSimpleName()) for p in m.getParameterTypes()]
            methods.append({{"name": str(m.getName()), "returns": str(m.getReturnType().getSimpleName()), "params": params}})
        out["methods"] = sorted(methods, key=lambda x: x["name"])
    else:
        out["is_java"] = False
        out["doc"] = getattr(cls, "__doc__", "")
        out["attributes"] = [a for a in dir(cls) if not a.startswith("__")]

    return out

result = _do_inspect()
"""
        return self.evaluate(code, is_eval=False)

    def inspect_object(self, expression: str) -> Dict[str, Any]:
        """Introspects an object's fields and runtime values inside Telegram runtime."""
        code = f"""
def _do_inspect_obj():
    val = eval({repr(expression)})
    out = {{"repr": repr(val), "type": type(val).__name__}}
    if hasattr(val, "getClass"):
        jcls = val.getClass()
        out["java_class"] = jcls.getName()
        fields = {{}}
        for f in jcls.getDeclaredFields():
            f.setAccessible(True)
            try:
                fields[str(f.getName())] = str(f.get(val))
            except Exception as e:
                fields[str(f.getName())] = f"<error: {{e}}>"
        out["fields"] = fields
    elif isinstance(val, dict):
        out["keys"] = list(val.keys())
    elif isinstance(val, (list, tuple)):
        out["length"] = len(val)
    return out

result = _do_inspect_obj()
"""
        return self.evaluate(code, is_eval=False)

    def search_classes(self, query: str) -> List[Dict[str, str]]:
        """Finds classes matching query from both standard Telegram catalog and live runtime."""
        catalog_matches = search_catalog_classes(query)
        # Try runtime lookup if dev server is alive
        if self.dev.ping():
            probe_code = f"""
def _search_runtime_classes():
    q = {repr(query.lower())}
    results = []
    try:
        from org.telegram.messenger import ApplicationLoader
        ctx = ApplicationLoader.applicationContext
        cl = ctx.getClassLoader()
        # Probe common Telegram packages dynamically
        common = [
            "org.telegram.ui.Cells",
            "org.telegram.ui.Components",
            "org.telegram.ui.ActionBar",
            "org.telegram.ui",
            "org.telegram.messenger",
            "org.telegram.tgnet",
        ]
    except Exception:
        pass
    return results

result = _search_runtime_classes()
"""
            try:
                rt_res = self.evaluate(probe_code, is_eval=False)
                if rt_res.get("success") and isinstance(rt_res.get("result"), list):
                    for item in rt_res["result"]:
                        if item not in catalog_matches:
                            catalog_matches.append(item)
            except Exception:
                pass
        return catalog_matches

    def get_hook_info(self, class_name: str, method_name: str) -> Dict[str, Any]:
        """Inspects all overloads of a method and generates hook_method recipes."""
        insp = self.inspect_class(class_name)
        if not insp.get("success", False) or "result" not in insp:
            return {"success": False, "error": insp.get("error", "Class inspection failed")}

        cls_data = insp["result"]
        methods = cls_data.get("methods", [])
        matched = [m for m in methods if m.get("name") == method_name]

        if not matched:
            return {
                "success": False,
                "error": f"Method '{method_name}' not found on class '{class_name}'.",
                "available_methods": [m.get("name") for m in methods[:25]],
            }

        overloads = []
        for m in matched:
            params = m.get("params", [])
            snippet = generate_hook_snippet(class_name, method_name, params)
            overloads.append({
                "name": method_name,
                "returns": m.get("returns"),
                "params": params,
                "hook_snippet": snippet,
            })

        return {
            "success": True,
            "class": class_name,
            "method": method_name,
            "overloads_count": len(overloads),
            "overloads": overloads,
        }

    def generate_stub(self, class_name: str, mode: str = "subclass") -> str:
        """Inspects class methods and generates a Python Chaquopy subclass or proxy skeleton."""
        insp = self.inspect_class(class_name)
        methods = []
        if insp.get("success") and "result" in insp:
            methods = insp["result"].get("methods", [])
        return generate_stub_code(class_name, methods, mode=mode)

    def get_active_fragment(self) -> Dict[str, Any]:
        """Inspects the currently active Telegram fragment, dialog ID, topic, and visible popups."""
        code = """
def _get_frag_info():
    out = {}
    try:
        from org.telegram.ui import LaunchActivity
        act = LaunchActivity.instance
        if not act:
            return {"error": "LaunchActivity instance is not available."}

        layout = act.getActionBarLayout()
        if not layout:
            return {"error": "ActionBarLayout is not available."}

        frag = layout.getLastFragment()
        if not frag:
            return {"error": "No active fragment on stack."}

        out["class"] = frag.getClass().getName()
        out["name"] = frag.getClass().getSimpleName()

        for field_name in ["currentDialogId", "dialog_id", "currentAccount", "topicId", "topic_id", "chatMode"]:
            if hasattr(frag, field_name):
                try:
                    val = getattr(frag, field_name)
                    out[field_name] = str(val)
                except Exception:
                    pass

        visible_dialog = getattr(frag, "visibleDialog", None)
        if visible_dialog:
            out["visible_dialog"] = visible_dialog.getClass().getSimpleName()
    except Exception as exc:
        return {"error": str(exc)}
    return out

result = _get_frag_info()
"""
        return self.evaluate(code, is_eval=False)

    def query_database(self, sql_query: str, limit: int = 50) -> Dict[str, Any]:
        """Executes a SQL query against Telegram MessagesStorage local SQLite database."""
        code = f"""
def _exec_sql():
    sql = {repr(sql_query.strip())}
    try:
        from org.telegram.messenger import MessagesStorage
        storage = MessagesStorage.getInstance(0)
        db = storage.getDatabase()
        if not db:
            return {{"error": "MessagesStorage database is closed or unavailable."}}

        cursor = db.queryFinalized(sql)
        columns = []
        rows = []
        try:
            col_count = cursor.getColumnCount()
            for i in range(col_count):
                columns.append(str(cursor.getColumnName(i)))

            while cursor.next() and len(rows) < {limit}:
                row = []
                for i in range(col_count):
                    try:
                        row.append(str(cursor.stringValue(i)))
                    except Exception:
                        row.append("<blob>")
                rows.append(row)
        finally:
            cursor.dispose()

        return {{"query": sql, "columns": columns, "rows": rows, "count": len(rows)}}
    except Exception as exc:
        return {{"error": str(exc)}}

result = _exec_sql()
"""
        return self.evaluate(code, is_eval=False)
