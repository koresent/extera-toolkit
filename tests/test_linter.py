from extera_toolkit.linter import lint_path, lint_plugin_ast


def test_lint_unsigned_color_bug():
    buggy_source = """
__id__ = "test_color"
__name__ = "Test Color"

class MyPlugin:
    def on_plugin_load(self):
        paint.setColor(0xFF1E88E5)
"""
    issues = lint_plugin_ast(buggy_source)
    codes = [i["code"] for i in issues]
    assert "W002" in codes  # Unsigned color warning


def test_lint_missing_unload_with_hooks():
    leaking_source = """
__id__ = "test_hooks"
__name__ = "Test Hooks"

class MyPlugin:
    def on_plugin_load(self):
        self.hook_method(some_target, MyHook())
"""
    issues = lint_plugin_ast(leaking_source)
    codes = [i["code"] for i in issues]
    assert "W004" in codes  # Missing on_plugin_unload


def test_lint_valid_plugin(tmp_path):
    clean_source = """
__id__ = "clean_plugin"
__name__ = "Clean Plugin"
__version__ = "1.0.0"

class CleanPlugin:
    def on_plugin_load(self):
        self.hook_method(target, Hook())

    def on_plugin_unload(self):
        pass
"""
    clean_file = tmp_path / "clean.py"
    clean_file.write_text(clean_source, encoding="utf-8")

    res = lint_path(str(clean_file))
    assert res["success"] is True
    assert res["total_errors"] == 0
    assert res["total_issues"] == 0
