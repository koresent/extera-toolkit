from extera_toolkit.interop import (
    generate_hook_snippet,
    generate_stub_code,
    search_catalog_classes,
)


def test_search_catalog_classes():
    matches = search_catalog_classes("DialogCell")
    assert len(matches) >= 1
    assert matches[0]["class"] == "org.telegram.ui.Cells.DialogCell"

    theme_matches = search_catalog_classes("Theme")
    assert any("ActionBar.Theme" in m["class"] for m in theme_matches)


def test_generate_hook_snippet():
    snippet = generate_hook_snippet(
        "org.telegram.ui.Cells.DialogCell",
        "onDraw",
        ["android.graphics.Canvas"],
    )
    assert "class OndrawHook(MethodHook):" in snippet
    assert "find_class('android.graphics.Canvas')" in snippet
    assert "find_class('org.telegram.ui.Cells.DialogCell').getDeclaredMethod('onDraw'" in snippet


def test_generate_stub_code():
    methods = [
        {"name": "onClick", "params": ["android.view.View"]},
    ]
    # Proxy mode
    proxy_stub = generate_stub_code("android.view.View.OnClickListener", methods, mode="proxy")
    assert "@dynamic_proxy(OnClickListener)" in proxy_stub
    assert "def onClick(self, arg0):" in proxy_stub

    # Subclass mode
    subclass_stub = generate_stub_code("android.widget.FrameLayout", methods, mode="subclass")
    assert "@java_subclass(FrameLayout)" in subclass_stub
    assert "@joverload('onClick', ['android.view.View'])" in subclass_stub
    assert "return super().onClick(arg0)" in subclass_stub
