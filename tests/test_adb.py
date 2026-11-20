import subprocess
import pytest
from extera_toolkit.adb import AdbController, AdbError


def test_adb_base_cmd():
    adb = AdbController(adb_path="/usr/bin/adb", device_id="device123")
    assert adb._base_cmd() == ["/usr/bin/adb", "-s", "device123"]


def test_list_devices(monkeypatch):
    sample_output = """List of devices attached
device123              device product:oriole model:Pixel_6 device:oriole transport_id:1
emulator-5554          offline
"""
    adb = AdbController()

    def mock_run_cmd(args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=0, stdout=sample_output, stderr="")

    monkeypatch.setattr(adb, "run_cmd", mock_run_cmd)

    devices = adb.list_devices()
    assert len(devices) == 2
    assert devices[0]["id"] == "device123"
    assert devices[0]["status"] == "device"
    assert devices[1]["id"] == "emulator-5554"
    assert devices[1]["status"] == "offline"
    assert adb.check_connection() is True


def test_autodetect_package(monkeypatch):
    adb = AdbController()

    def mock_shell(cmd, **kwargs):
        if cmd == "pm list packages":
            return "package:com.android.chrome\npackage:org.telegram.messenger\npackage:com.google.android.youtube\n"
        return ""

    monkeypatch.setattr(adb, "shell", mock_shell)

    pkg = adb.autodetect_package()
    assert pkg == "org.telegram.messenger"


def test_get_app_pid(monkeypatch):
    adb = AdbController()

    def mock_autodetect():
        return "org.telegram.messenger"

    def mock_shell(cmd, **kwargs):
        if "pidof" in cmd:
            return "32627\n"
        return ""

    monkeypatch.setattr(adb, "autodetect_package", mock_autodetect)
    monkeypatch.setattr(adb, "shell", mock_shell)

    pid = adb.get_app_pid()
    assert pid == 32627


def test_ensure_forward(monkeypatch):
    adb = AdbController()
    called_cmds = []

    def mock_run_cmd(args, **kwargs):
        called_cmds.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="42690\n", stderr="")

    monkeypatch.setattr(adb, "run_cmd", mock_run_cmd)

    adb.ensure_forward(42690, 42690)
    assert called_cmds == [["forward", "tcp:42690", "tcp:42690"]]
