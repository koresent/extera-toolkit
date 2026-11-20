import ast
import os
import py_compile
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .adb import AdbController, AdbError
from .dev_client import DevServerClient, DevServerError


class PluginMetadataError(Exception):
    """Raised when plugin metadata cannot be extracted or is invalid."""
    pass


class PluginCompilationError(Exception):
    """Raised when plugin fails syntax compilation."""
    pass


def extract_plugin_metadata(source_code: str) -> Dict[str, Any]:
    """Extracts top-level __id__, __name__, __version__, etc. using AST."""
    try:
        tree = ast.parse(source_code)
    except SyntaxError as exc:
        raise PluginCompilationError(f"Syntax error in plugin source: {exc}") from exc

    metadata: Dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.startswith("__") and target.id.endswith("__"):
                    try:
                        metadata[target.id] = ast.literal_eval(node.value)
                    except Exception:
                        pass

    if "__id__" not in metadata:
        raise PluginMetadataError("Plugin is missing required '__id__' top-level definition.")
    return metadata


def validate_python_source(file_path: Path) -> None:
    """Checks Python syntax with py_compile."""
    try:
        py_compile.compile(str(file_path), doraise=True)
    except py_compile.PyCompileError as exc:
        raise PluginCompilationError(f"Compilation failed for '{file_path}':\n{exc.msg}") from exc


class PluginManager:
    """Manages plugin deployment, lifecycle, and inspection."""

    def __init__(
        self,
        dev_client: Optional[DevServerClient] = None,
        adb_controller: Optional[AdbController] = None,
    ):
        self.adb = adb_controller or AdbController()
        self.dev = dev_client or DevServerClient(adb_controller=self.adb)

    def push(
        self,
        plugin_path: str,
        clean_reload: bool = False,
        build_index: bool = True,
    ) -> Dict[str, Any]:
        """Validates, prepares, and deploys a plugin via dev server."""
        path = Path(plugin_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Plugin path does not exist: {path}")

        # If directory, find main .py file or folder name
        if path.is_dir():
            candidates = list(path.glob("*.py"))
            if not candidates:
                raise FileNotFoundError(f"No .py files found in directory '{path}'")
            # Prefer file with same name as directory
            match = [c for c in candidates if c.stem == path.name]
            target_file = match[0] if match else candidates[0]
        else:
            target_file = path

        # 1. Syntax check
        validate_python_source(target_file)

        # 2. Extract metadata
        content = target_file.read_text(encoding="utf-8")
        meta = extract_plugin_metadata(content)
        plugin_id = meta["__id__"]

        # 3. Clean reload if requested (prevents duplicate hooks)
        if clean_reload:
            try:
                self.dev.disable_plugin(plugin_id)
                time.sleep(0.3)
            except Exception:
                pass

        # 4. Deploy via dev-server write_plugin
        res = self.dev.write_plugin(plugin_id, content)

        # 5. Check if repository build_index exists in parent dirs and run it
        if build_index:
            curr = target_file.parent
            for _ in range(3):
                idx_script = curr / "build_index.py"
                if idx_script.is_file():
                    try:
                        subprocess.run(["python3", str(idx_script)], cwd=str(curr), capture_output=True, timeout=10)
                    except Exception:
                        pass
                    break
                curr = curr.parent

        return {
            "success": True,
            "plugin_id": plugin_id,
            "name": meta.get("__name__", plugin_id),
            "version": meta.get("__version__", "1.0"),
            "file": str(target_file),
            "response": res,
        }

    def clean_reload(self, plugin_id: str) -> Dict[str, Any]:
        """Performs a clean cycle: disable -> wait -> reload/enable to prune lingering hooks."""
        disable_res = self.dev.disable_plugin(plugin_id)
        time.sleep(0.3)
        enable_res = self.dev.enable_plugin(plugin_id)
        return {
            "success": True,
            "plugin_id": plugin_id,
            "disable": disable_res,
            "enable": enable_res,
        }

    def list_plugins(self) -> List[Dict[str, Any]]:
        """Lists plugins from dev server."""
        return self.dev.get_plugins()

    def get_status(self) -> Dict[str, Any]:
        """Gathers full environment diagnostic status."""
        devices = []
        try:
            devices = self.adb.list_devices()
        except Exception:
            pass

        authorized_dev = [d for d in devices if d.get("status") == "device"]
        has_device = len(authorized_dev) > 0

        pkg = None
        pid = None
        if has_device:
            try:
                pkg = self.adb.autodetect_package()
                if pkg:
                    pid = self.adb.get_app_pid(pkg)
            except Exception:
                pass

        dev_server_alive = False
        plugins: List[Dict[str, Any]] = []
        if has_device:
            try:
                dev_server_alive = self.dev.ping()
                if dev_server_alive:
                    plugins = self.dev.get_plugins()
            except Exception:
                pass

        return {
            "device_connected": has_device,
            "devices": devices,
            "package": pkg,
            "pid": pid,
            "dev_server_alive": dev_server_alive,
            "plugins_count": len(plugins),
            "plugins": plugins,
        }
