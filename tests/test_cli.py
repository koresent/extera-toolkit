from extera_toolkit.cli import build_parser, main


def test_cli_parser_defaults():
    parser = build_parser()
    args = parser.parse_args(["status"])
    assert args.subcommand == "status"
    assert args.toon is False


def test_cli_parser_toon_flag():
    parser = build_parser()
    args = parser.parse_args(["status", "--toon"])
    assert args.subcommand == "status"
    assert args.toon is True


def test_cli_push_command_args():
    parser = build_parser()
    args = parser.parse_args(["push", "kanban_board/", "--clean"])
    assert args.subcommand == "push"
    assert args.path == "kanban_board/"
    assert args.clean is True


def test_cli_eval_command_args():
    parser = build_parser()
    args = parser.parse_args(["eval", "UserConfig.selectedAccount"])
    assert args.subcommand == "eval"
    assert args.expression == "UserConfig.selectedAccount"


def test_cli_ui_click_args():
    parser = build_parser()
    args = parser.parse_args(["ui", "click", "Telegram Kanban"])
    assert args.subcommand == "ui"
    assert args.ui_action == "click"
    assert args.query == "Telegram Kanban"


def test_cli_main_status(monkeypatch, capsys):
    monkeypatch.setattr(
        "extera_toolkit.manager.PluginManager.get_status",
        lambda self: {"device_connected": False, "plugins_count": 0},
    )
    code = main(["status", "--json"])
    assert code == 0
    captured = capsys.readouterr()
    assert '"device_connected":false' in captured.out or '"device_connected": false' in captured.out


def test_cli_connect_and_devices_args():
    parser = build_parser()
    args_conn = parser.parse_args(["connect", "192.168.1.50:5555"])
    assert args_conn.subcommand == "connect"
    assert args_conn.host_port == "192.168.1.50:5555"

    args_devs = parser.parse_args(["devices"])
    assert args_devs.subcommand == "devices"


def test_cli_inspect_args():
    parser = build_parser()
    args_cls = parser.parse_args(["inspect", "class", "org.telegram.ui.Cells.DialogCell"])
    assert args_cls.subcommand == "inspect"
    assert args_cls.inspect_action == "class"
    assert args_cls.name == "org.telegram.ui.Cells.DialogCell"


def test_cli_fs_and_crash_args():
    parser = build_parser()
    args_crash = parser.parse_args(["crash", "--tail", "25"])
    assert args_crash.subcommand == "crash"
    assert args_crash.tail == 25

    args_fs = parser.parse_args(["fs", "cat", "/sdcard/test.log"])
    assert args_fs.subcommand == "fs"
    assert args_fs.fs_action == "cat"
    assert args_fs.path == "/sdcard/test.log"


def test_cli_ui_swipe_args():
    parser = build_parser()
    args_swipe = parser.parse_args(["ui", "swipe", "down", "-d", "400"])
    assert args_swipe.subcommand == "ui"
    assert args_swipe.ui_action == "swipe"
    assert args_swipe.direction == "down"
    assert args_swipe.distance == 400
