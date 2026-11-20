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


def test_cli_jtypes_args():
    parser = build_parser()
    args_sign = parser.parse_args(["jtypes", "to-signed", "0xFFFFFFFF"])
    assert args_sign.subcommand == "jtypes"
    assert args_sign.jtypes_action == "to-signed"
    assert args_sign.value == "0xFFFFFFFF"

    args_color = parser.parse_args(["jtypes", "color", "#FF1E88E5"])
    assert args_color.subcommand == "jtypes"
    assert args_color.jtypes_action == "color"


def test_cli_search_and_hook_args():
    parser = build_parser()
    args_srch = parser.parse_args(["search", "class", "DialogCell"])
    assert args_srch.subcommand == "search"
    assert args_srch.search_action == "class"
    assert args_srch.query == "DialogCell"

    args_hook = parser.parse_args(["hook-info", "org.telegram.ui.Cells.DialogCell", "onDraw"])
    assert args_hook.subcommand == "hook-info"
    assert args_hook.class_name == "org.telegram.ui.Cells.DialogCell"
    assert args_hook.method_name == "onDraw"


def test_cli_stub_runtime_db_lint_args():
    parser = build_parser()
    args_stub = parser.parse_args(["stub", "android.view.View.OnClickListener", "--mode", "proxy"])
    assert args_stub.subcommand == "stub"
    assert args_stub.mode == "proxy"

    args_rt = parser.parse_args(["runtime", "fragment"])
    assert args_rt.subcommand == "runtime"
    assert args_rt.runtime_action == "fragment"

    args_db = parser.parse_args(["db", "SELECT * FROM dialogs LIMIT 5", "--limit", "5"])
    assert args_db.subcommand == "db"
    assert "SELECT" in args_db.query
    assert args_db.limit == 5

    args_lint = parser.parse_args(["lint", "kanban_board/"])
    assert args_lint.subcommand == "lint"
    assert args_lint.path == "kanban_board/"
