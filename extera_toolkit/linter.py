import ast
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

COLOR_METHODS = {
    "setcolor",
    "settextcolor",
    "setbackgroundcolor",
    "sethinttextcolor",
    "setdividercolor",
    "setshadowcolor",
}

ID_REGEX = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{1,31}$")


class LintIssue:
    def __init__(self, code: str, message: str, line: int = 1, severity: str = "warning"):
        self.code = code
        self.message = message
        self.line = line
        self.severity = severity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "line": self.line,
            "message": self.message,
        }


def lint_plugin_ast(source_code: str, file_path: str = "<source>") -> List[Dict[str, Any]]:
    """Analyzes plugin source code for common Chaquopy/exteraGram runtime traps."""
    issues: List[LintIssue] = []

    try:
        tree = ast.parse(source_code)
    except SyntaxError as exc:
        return [LintIssue("E001", f"Syntax error: {exc}", line=exc.lineno or 1, severity="error").to_dict()]

    metadata: Dict[str, Any] = {}
    has_plugin_class = False
    has_on_unload = False
    registers_hooks = False

    for node in tree.body:
        # Check metadata assignments
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.startswith("__") and target.id.endswith("__"):
                    try:
                        metadata[target.id] = ast.literal_eval(node.value)
                    except Exception:
                        pass

        # Check plugin class definitions
        if isinstance(node, ast.ClassDef):
            has_plugin_class = True
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "on_plugin_unload":
                    has_on_unload = True

    # Validate metadata
    if "__id__" not in metadata:
        issues.append(LintIssue("E002", "Missing required '__id__' top-level metadata.", severity="error"))
    else:
        pid = str(metadata["__id__"])
        if not ID_REGEX.match(pid):
            issues.append(LintIssue(
                "E003",
                f"Invalid '__id__' format '{pid}'. Must be 2-32 chars, start with a letter, and contain only [a-zA-Z0-9_-].",
                severity="error",
            ))

    if "__name__" not in metadata:
        issues.append(LintIssue("W001", "Missing recommended '__name__' top-level metadata.", severity="warning"))

    if "__requirements__" in metadata and not isinstance(metadata["__requirements__"], list):
        issues.append(LintIssue("E004", "'__requirements__' must be a list of strings.", severity="error"))

    # AST visitor to inspect method calls
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            call_name = ""
            if isinstance(node.func, ast.Attribute):
                call_name = node.func.attr
            elif isinstance(node.func, ast.Name):
                call_name = node.func.id

            # Check for hook registration
            if call_name in ("hook_method", "hook_all_methods", "add_menu_item"):
                registers_hooks = True

            # Check for unsigned 32-bit color literal passed directly to Java color methods
            if call_name.lower() in COLOR_METHODS:
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, int):
                        # Java signed int boundary: 0x7FFFFFFF (2147483647)
                        if arg.value > 0x7FFFFFFF:
                            issues.append(LintIssue(
                                "W002",
                                f"Unsigned color literal 0x{arg.value:X} in '{call_name}()'. "
                                "Java requires signed 32-bit int (-2147483648..2147483647). "
                                "Wrap with to_jint(...) or to_signed32(...) to prevent Chaquopy OverflowError.",
                                line=node.lineno,
                                severity="warning",
                            ))

            # Check for blocking sleep in main thread
            if call_name == "sleep" and isinstance(getattr(node, "func", None), ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "time":
                    issues.append(LintIssue(
                        "W003",
                        "time.sleep() detected. Blocking the main thread causes Android ANR. "
                        "Use AndroidUtilities.runOnUIThread(...) or background threads.",
                        line=node.lineno,
                        severity="warning",
                    ))

    # Check for hook leak (registers hooks but does not clean up in on_plugin_unload)
    if registers_hooks and not has_on_unload:
        issues.append(LintIssue(
            "W004",
            "Plugin registers hooks or UI items but does not define 'on_plugin_unload()'. "
            "Lingering hooks cause duplicate buttons and memory leaks on hot-reload.",
            severity="warning",
        ))

    return [i.to_dict() for i in issues]


def lint_path(target_path: str) -> Dict[str, Any]:
    """Runs linter on a single plugin file or directory of plugins."""
    path = Path(target_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")

    files_to_lint = []
    if path.is_file():
        files_to_lint.append(path)
    else:
        files_to_lint.extend(list(path.glob("**/*.py")))

    results = []
    total_issues = 0
    total_errors = 0

    for f in files_to_lint:
        try:
            content = f.read_text(encoding="utf-8")
            issues = lint_plugin_ast(content, file_path=str(f))
            error_count = sum(1 for i in issues if i["severity"] == "error")
            total_issues += len(issues)
            total_errors += error_count
            results.append({
                "file": str(f),
                "issues_count": len(issues),
                "issues": issues,
            })
        except Exception as exc:
            results.append({
                "file": str(f),
                "error": str(exc),
            })
            total_errors += 1

    return {
        "success": total_errors == 0,
        "files_checked": len(files_to_lint),
        "total_issues": total_issues,
        "total_errors": total_errors,
        "results": results,
    }
