import argparse
import sys
from typing import Any, List, Optional

from .adb import AdbController, AdbError
from .dev_client import DevServerClient, DevServerError
from .formatters import get_default_format, output_result, set_default_format
from .logs import LogMonitor
from .manager import PluginManager
from .repl import RuntimeEvaluator
from .ui import UIInspector


def build_parser() -> argparse.ArgumentParser:
    format_parser = argparse.ArgumentParser(add_help=False)
    format_parser.add_argument("--toon", action="store_true", help="Force TOON format (recommended for LLM agents).")
    format_parser.add_argument("--json", action="store_true", help="Force compact JSON format.")
    format_parser.add_argument("--format", choices=["toon", "json", "json-pretty", "text"], help="Explicit output format.")

    parser = argparse.ArgumentParser(
        prog="extera-toolkit",
        parents=[format_parser],
        description="Development, debugging, and inspection toolkit for Telegram and exteraGram plugins.",
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    p_config = subparsers.add_parser("config", parents=[format_parser], help="Manage persistent settings.")
    p_config.add_argument("--set-format", choices=["toon", "json", "json-pretty", "text"], help="Set default format.")
    p_config.add_argument("--get-format", action="store_true", help="Print active default format.")

    subparsers.add_parser("status", parents=[format_parser], help="Show environment diagnostic status (ADB, package, PID, dev-server, plugins).")

    p_push = subparsers.add_parser("push", parents=[format_parser], help="Validate and deploy plugin to device via dev-server.")
    p_push.add_argument("path", help="Path to plugin source file (.py) or directory.")
    p_push.add_argument("--clean", action="store_true", help="Perform clean reload (disable before push to prune hooks).")
    p_push.add_argument("--no-index", action="store_true", help="Skip running build_index.py.")

    p_reload = subparsers.add_parser("reload", parents=[format_parser], help="Reload an installed plugin.")
    p_reload.add_argument("plugin_id", help="ID of plugin to reload.")
    p_reload.add_argument("--clean", action="store_true", help="Disable, brief wait, and enable to clean hooks.")

    p_eval = subparsers.add_parser("eval", parents=[format_parser], help="Evaluate Python/Java expression in live Telegram runtime.")
    p_eval.add_argument("expression", help="Expression or code string to evaluate.")

    p_exec = subparsers.add_parser("exec", parents=[format_parser], help="Execute Python script in live Telegram runtime.")
    p_exec.add_argument("script_path", help="Path to Python script file to execute inside app.")

    p_logs = subparsers.add_parser("logs", parents=[format_parser], help="Read filtered plugin and app logcat.")
    p_logs.add_argument("--plugin", "-p", help="Filter by plugin ID (reads plugin.<id> tag).")
    p_logs.add_argument("--tail", "-n", type=int, default=30, help="Number of recent log lines to retrieve (default: 30).")
    p_logs.add_argument("--level", "-l", choices=["V", "D", "I", "W", "E"], default="D", help="Log priority level.")
    p_logs.add_argument("--grep", "-g", help="Regex or substring filter for log lines.")
    p_logs.add_argument("--clear", action="store_true", help="Clear logcat buffer.")

    p_ui = subparsers.add_parser("ui", parents=[format_parser], help="Inspect and interact with Telegram UI on screen.")
    ui_subparsers = p_ui.add_subparsers(dest="ui_action", help="UI action to perform")

    p_ui_dump = ui_subparsers.add_parser("dump", parents=[format_parser], help="Dump on-screen UI elements with bounds and centers.")
    p_ui_dump.add_argument("--filter", "-f", help="Filter elements by text, resource ID, or content-desc.")
    p_ui_dump.add_argument("--clickable", "-c", action="store_true", help="Include only clickable elements.")

    p_ui_click = ui_subparsers.add_parser("click", parents=[format_parser], help="Click an on-screen element by text, ID, or description.")
    p_ui_click.add_argument("query", help="Text, description, or resource ID of element to click.")
    p_ui_click.add_argument("--index", "-i", type=int, default=0, help="Match index if multiple elements match (default: 0).")

    p_ui_screen = ui_subparsers.add_parser("screenshot", parents=[format_parser], help="Capture screen image.")
    p_ui_screen.add_argument("output", nargs="?", help="Local destination file path.")
    p_ui_screen.add_argument("--bounds", help="Crop bounds as 'x1,y1,x2,y2'.")

    p_dev = subparsers.add_parser("dev", parents=[format_parser], help="Direct low-level dev server RPC commands.")
    dev_subparsers = p_dev.add_subparsers(dest="dev_action", help="Dev server RPC action")
    dev_subparsers.add_parser("ping", help="Ping dev server.")
    dev_subparsers.add_parser("list", help="List plugins loaded by dev server.")
    
    p_dev_en = dev_subparsers.add_parser("enable", parents=[format_parser], help="Enable a plugin.")
    p_dev_en.add_argument("plugin_id", help="Plugin ID.")

    p_dev_dis = dev_subparsers.add_parser("disable", parents=[format_parser], help="Disable a plugin.")
    p_dev_dis.add_argument("plugin_id", help="Plugin ID.")

    p_dev_rel = dev_subparsers.add_parser("reload", parents=[format_parser], help="Reload a plugin.")
    p_dev_rel.add_argument("plugin_id", help="Plugin ID.")

    p_dev_rm = dev_subparsers.add_parser("remove", parents=[format_parser], help="Remove a plugin.")
    p_dev_rm.add_argument("plugin_id", help="Plugin ID.")

    p_restart = subparsers.add_parser("restart", parents=[format_parser], help="Restart Telegram/exteraGram app cleanly.")
    p_restart.add_argument("--package", help="Package name (autodetected if omitted).")

    return parser


def handle_config(args: Any) -> None:
    if args.set_format:
        set_default_format(args.set_format)
        output_result({"success": True, "default_format": args.set_format}, args)
    elif args.get_format:
        fmt = get_default_format() or "text (unset)"
        output_result({"default_format": fmt}, args)
    else:
        output_result({"current_resolved_format": get_default_format() or "text"}, args)


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if not args.subcommand:
        parser.print_help()
        return 0

    adb = AdbController()
    dev = DevServerClient(adb_controller=adb)
    mgr = PluginManager(dev_client=dev, adb_controller=adb)

    try:
        if args.subcommand == "config":
            handle_config(args)
            return 0

        elif args.subcommand == "status":
            res = mgr.get_status()
            output_result(res, args)
            return 0

        elif args.subcommand == "push":
            res = mgr.push(args.path, clean_reload=args.clean, build_index=not args.no_index)
            output_result(res, args)
            return 0

        elif args.subcommand == "reload":
            if args.clean:
                res = mgr.clean_reload(args.plugin_id)
            else:
                res = dev.reload_plugin(args.plugin_id)
            output_result(res, args)
            return 0

        elif args.subcommand == "eval":
            evaluator = RuntimeEvaluator(dev_client=dev, adb_controller=adb)
            res = evaluator.evaluate(args.expression, is_eval=True)
            output_result(res, args)
            return 0 if res.get("success", False) else 1

        elif args.subcommand == "exec":
            from pathlib import Path
            code = Path(args.script_path).read_text(encoding="utf-8")
            evaluator = RuntimeEvaluator(dev_client=dev, adb_controller=adb)
            res = evaluator.evaluate(code, is_eval=False)
            output_result(res, args)
            return 0 if res.get("success", False) else 1

        elif args.subcommand == "logs":
            monitor = LogMonitor(adb_controller=adb)
            if args.clear:
                monitor.clear()
                output_result({"cleared": True}, args)
                return 0
            logs = monitor.get_logs(
                plugin_id=args.plugin,
                level=args.level,
                tail=args.tail,
                grep_pattern=args.grep,
            )
            output_result(logs, args)
            return 0

        elif args.subcommand == "ui":
            ui = UIInspector(adb_controller=adb)
            if args.ui_action == "dump":
                elements = ui.dump(filter_text=args.filter, clickable_only=args.clickable)
                output_result(elements, args)
                return 0
            elif args.ui_action == "click":
                res = ui.click(args.query, index=args.index)
                output_result(res, args)
                return 0 if res.get("success", False) else 1
            elif args.ui_action == "screenshot":
                bounds_tuple = None
                if args.bounds:
                    parts = [int(p.strip()) for p in args.bounds.split(",")]
                    if len(parts) == 4:
                        bounds_tuple = (parts[0], parts[1], parts[2], parts[3])
                res = ui.screenshot(output_path=args.output, crop_bounds=bounds_tuple)
                output_result(res, args)
                return 0
            else:
                parser.parse_args(["ui", "--help"])
                return 0

        elif args.subcommand == "dev":
            if args.dev_action == "ping":
                alive = dev.ping()
                output_result({"ping": alive}, args)
                return 0 if alive else 1
            elif args.dev_action == "list":
                plugins = dev.get_plugins()
                output_result(plugins, args)
                return 0
            elif args.dev_action == "enable":
                res = dev.enable_plugin(args.plugin_id)
                output_result(res, args)
                return 0
            elif args.dev_action == "disable":
                res = dev.disable_plugin(args.plugin_id)
                output_result(res, args)
                return 0
            elif args.dev_action == "reload":
                res = dev.reload_plugin(args.plugin_id)
                output_result(res, args)
                return 0
            elif args.dev_action == "remove":
                res = dev.remove_plugin(args.plugin_id)
                output_result(res, args)
                return 0
            else:
                parser.parse_args(["dev", "--help"])
                return 0

        elif args.subcommand == "restart":
            adb.restart_app(package_name=args.package)
            output_result({"restarted": True, "package": args.package or "autodetected"}, args)
            return 0

    except Exception as exc:
        output_result({"success": False, "error": str(exc)}, args)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
