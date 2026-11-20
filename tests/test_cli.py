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
