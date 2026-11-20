from extera_toolkit.ui import UIInspector, parse_bounds, parse_ui_hierarchy

SAMPLE_HIERARCHY_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="org.telegram.messenger" bounds="[0,0][1280,2400]">
    <node index="0" text="Telegram Kanban" resource-id="org.telegram.messenger:id/action_bar_title" class="android.widget.TextView" package="org.telegram.messenger" content-desc="" clickable="true" enabled="true" bounds="[100,150][600,250]" />
    <node index="1" text="" resource-id="org.telegram.messenger:id/menu_item_kanban" class="android.widget.ImageView" package="org.telegram.messenger" content-desc="Open Board" clickable="true" enabled="true" bounds="[1150,180][1250,260]" />
    <node index="2" text="In Progress" resource-id="" class="android.widget.TextView" package="org.telegram.messenger" content-desc="" clickable="false" enabled="true" bounds="[50,300][350,360]" />
  </node>
</hierarchy>
"""


def test_parse_bounds():
    assert parse_bounds("[100,200][300,400]") == (100, 200, 300, 400)
    assert parse_bounds("invalid") is None


def test_parse_ui_hierarchy():
    elements = parse_ui_hierarchy(SAMPLE_HIERARCHY_XML)
    assert len(elements) == 3

    title_elem = elements[0]
    assert title_elem["text"] == "Telegram Kanban"
    assert title_elem["id"] == "action_bar_title"
    assert title_elem["clickable"] is True
    assert title_elem["center"] == [350, 200]
    assert title_elem["bounds"] == [100, 150, 600, 250]

    btn_elem = elements[1]
    assert btn_elem["desc"] == "Open Board"
    assert btn_elem["id"] == "menu_item_kanban"
    assert btn_elem["center"] == [1200, 220]


def test_ui_inspector_dump_and_click(monkeypatch):
    inspector = UIInspector()

    monkeypatch.setattr(inspector.adb, "dump_window_hierarchy", lambda: SAMPLE_HIERARCHY_XML)

    tapped_coords = []
    monkeypatch.setattr(inspector.adb, "input_tap", lambda x, y: tapped_coords.append((x, y)))

    all_elems = inspector.dump()
    assert len(all_elems) == 3

    clickable_elems = inspector.dump(clickable_only=True)
    assert len(clickable_elems) == 2

    filtered = inspector.dump(filter_text="Board")
    assert len(filtered) == 1
    assert filtered[0]["desc"] == "Open Board"

    res = inspector.click("Open Board")
    assert res["success"] is True
    assert tapped_coords == [(1200, 220)]

    fail_res = inspector.click("NonExistentButton")
    assert fail_res["success"] is False
    assert "not found" in fail_res["error"]
