import argparse
import tempfile
from pathlib import Path
from extera_toolkit.formatters import (
    dump_data,
    get_default_format,
    resolve_format,
    set_default_format,
    to_toon,
)


def test_formatters_dump_data():
    sample = {"name": "Telegram Kanban", "version": "1.0.1", "active": True}
    
    json_out = dump_data(sample, fmt="json")
    assert '"name":"Telegram Kanban"' in json_out

    pretty_out = dump_data(sample, fmt="json-pretty")
    assert '\n  "name": "Telegram Kanban"' in pretty_out

    toon_out = to_toon(sample)
    assert "Telegram Kanban" in toon_out


def test_formatters_resolve_format():
    args_toon = argparse.Namespace(toon=True, json=False, format=None)
    assert resolve_format(args_toon) == "toon"

    args_json = argparse.Namespace(toon=False, json=True, format=None)
    assert resolve_format(args_json) == "json"

    args_explicit = argparse.Namespace(toon=False, json=False, format="json-pretty")
    assert resolve_format(args_explicit) == "json-pretty"


def test_persistent_format_config(monkeypatch, tmp_path):
    test_file = tmp_path / "default_format"
    monkeypatch.setattr("extera_toolkit.formatters.DEFAULT_FORMAT_FILE", test_file)

    assert get_default_format() is None

    set_default_format("toon")
    assert test_file.read_text().strip() == "toon"
    assert get_default_format() == "toon"

    args_empty = argparse.Namespace(toon=False, json=False, format=None)
    assert resolve_format(args_empty) == "toon"
