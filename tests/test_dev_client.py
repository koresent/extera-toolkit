import json
import socket
import pytest
from extera_toolkit.dev_client import DevServerClient, DevServerError


class DummySocket:
    def __init__(self, responses):
        self.responses = responses
        self.sent_data = b""
        self.timeout = None

    def settimeout(self, val):
        self.timeout = val

    def connect(self, addr):
        pass

    def sendall(self, data):
        self.sent_data += data

    def recv(self, bufsize):
        if self.responses:
            return self.responses.pop(0)
        return b""

    def close(self):
        pass


def test_dev_client_ping(monkeypatch):
    client = DevServerClient()

    def mock_send_raw(payload):
        assert payload["@"] == "ping"
        return {"#": payload.get("#", "test-1"), "pong": True}

    monkeypatch.setattr(client, "send_raw_command", mock_send_raw)
    assert client.ping() is True


def test_dev_client_raw_command(monkeypatch):
    client = DevServerClient(auto_forward=False)

    dummy_response = json.dumps({"#": "test-req", "pong": True}).encode("utf-8") + b"\n"
    dummy_sock = DummySocket([dummy_response])

    monkeypatch.setattr(client, "_create_connection", lambda: dummy_sock)

    res = client.send_raw_command({"@": "ping", "#": "test-req"})
    assert res == {"#": "test-req", "pong": True}
    assert b'"@": "ping"' in dummy_sock.sent_data or b'"@":"ping"' in dummy_sock.sent_data


def test_dev_client_methods(monkeypatch):
    client = DevServerClient()
    calls = []

    def mock_send_raw(payload):
        calls.append(payload)
        cmd = payload["@"]
        if cmd == "get_plugins":
            return {"#": payload.get("#"), "plugins": [{"id": "kanban_board", "enabled": True}]}
        return {"#": payload.get("#"), "success": True}

    monkeypatch.setattr(client, "send_raw_command", mock_send_raw)

    plugins = client.get_plugins()
    assert len(plugins) == 1
    assert plugins[0]["id"] == "kanban_board"

    client.enable_plugin("kanban_board")
    assert calls[-1]["@"] == "enable_plugin"
    assert calls[-1]["plugin_id"] == "kanban_board"

    client.disable_plugin("kanban_board")
    assert calls[-1]["@"] == "disable_plugin"

    client.reload_plugin("kanban_board")
    assert calls[-1]["@"] == "reload_plugin"

    client.write_plugin("kanban_board", "print(1)")
    assert calls[-1]["@"] == "write_plugin"
    assert calls[-1]["content"] == "print(1)"

    client.remove_plugin("kanban_board")
    assert calls[-1]["@"] == "remove_plugin"
