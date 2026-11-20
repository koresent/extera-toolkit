import tempfile
from pathlib import Path
import pytest
from extera_toolkit.manager import (
    PluginCompilationError,
    PluginManager,
    PluginMetadataError,
    extract_plugin_metadata,
    validate_python_source,
)


def test_extract_plugin_metadata():
    valid_source = """
__id__ = "kanban_board"
__name__ = "Telegram Kanban"
__version__ = "1.0.1"
__author__ = "@koresent"
"""
    meta = extract_plugin_metadata(valid_source)
    assert meta["__id__"] == "kanban_board"
    assert meta["__name__"] == "Telegram Kanban"
    assert meta["__version__"] == "1.0.1"
    assert meta["__author__"] == "@koresent"


def test_extract_plugin_metadata_missing_id():
    invalid_source = """
__name__ = "No ID Plugin"
"""
    with pytest.raises(PluginMetadataError):
        extract_plugin_metadata(invalid_source)


def test_validate_python_source(tmp_path):
    good_file = tmp_path / "good.py"
    good_file.write_text("a = 1 + 2\n")
    validate_python_source(good_file)

    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def broken_syntax(\n")
    with pytest.raises(PluginCompilationError):
        validate_python_source(bad_file)


def test_plugin_manager_push(monkeypatch, tmp_path):
    plugin_file = tmp_path / "test_plug.py"
    plugin_file.write_text('__id__ = "test_plug"\n__name__ = "Test Plugin"\n')

    mgr = PluginManager()
    written = {}

    def mock_write(pid, content):
        written["pid"] = pid
        written["content"] = content
        return {"success": True}

    monkeypatch.setattr(mgr.dev, "write_plugin", mock_write)

    res = mgr.push(str(plugin_file), build_index=False)
    assert res["success"] is True
    assert res["plugin_id"] == "test_plug"
    assert written["pid"] == "test_plug"
    assert "__name__" in written["content"]


def test_plugin_manager_clean_reload(monkeypatch):
    mgr = PluginManager()
    sequence = []

    monkeypatch.setattr(mgr.dev, "disable_plugin", lambda pid: sequence.append(f"disable_{pid}"))
    monkeypatch.setattr(mgr.dev, "enable_plugin", lambda pid: sequence.append(f"enable_{pid}"))

    res = mgr.clean_reload("kanban_board")
    assert res["success"] is True
    assert sequence == ["disable_kanban_board", "enable_kanban_board"]
