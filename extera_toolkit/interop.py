from typing import Any, Dict, List, Optional

COMMON_TELEGRAM_CLASSES = [
    # Core Activities & Fragments
    "org.telegram.ui.LaunchActivity",
    "org.telegram.ui.ChatActivity",
    "org.telegram.ui.DialogsActivity",
    "org.telegram.ui.ProfileActivity",
    "org.telegram.ui.ChannelEditActivity",
    "org.telegram.ui.GroupCreateActivity",
    # Action Bar & UI Components
    "org.telegram.ui.ActionBar.Theme",
    "org.telegram.ui.ActionBar.ActionBar",
    "org.telegram.ui.ActionBar.ActionBarMenu",
    "org.telegram.ui.ActionBar.ActionBarMenuItem",
    "org.telegram.ui.ActionBar.BottomSheet",
    "org.telegram.ui.ActionBar.AlertDialog",
    "org.telegram.ui.ActionBar.BaseFragment",
    # Cells
    "org.telegram.ui.Cells.DialogCell",
    "org.telegram.ui.Cells.ChatMessageCell",
    "org.telegram.ui.Cells.TextCell",
    "org.telegram.ui.Cells.HeaderCell",
    "org.telegram.ui.Cells.UserCell",
    # Components & Utilities
    "org.telegram.ui.Components.AvatarDrawable",
    "org.telegram.ui.Components.BulletinFactory",
    "org.telegram.ui.Components.RecyclerListView",
    "org.telegram.ui.Components.BackupImageView",
    "org.telegram.ui.Components.EditTextBoldCursor",
    "org.telegram.ui.Components.LayoutHelper",
    # Controllers & Managers
    "org.telegram.messenger.AndroidUtilities",
    "org.telegram.messenger.ApplicationLoader",
    "org.telegram.messenger.MessagesController",
    "org.telegram.messenger.MessagesStorage",
    "org.telegram.messenger.SendMessagesHelper",
    "org.telegram.messenger.NotificationCenter",
    "org.telegram.messenger.UserConfig",
    "org.telegram.messenger.SharedConfig",
    "org.telegram.messenger.MessageObject",
    "org.telegram.messenger.TopicsController",
    "org.telegram.messenger.FileLog",
    "org.telegram.messenger.LocaleController",
    # TGNet & Protocol
    "org.telegram.tgnet.TLRPC",
    "org.telegram.tgnet.ConnectionsManager",
    # Plugin Framework
    "base_plugin.BasePlugin",
    "base_plugin.MethodHook",
    "base_plugin.MethodReplacement",
    "base_plugin.BaseHook",
    # Common Android Views
    "android.view.View",
    "android.view.ViewGroup",
    "android.widget.TextView",
    "android.widget.ImageView",
    "android.widget.LinearLayout",
    "android.widget.FrameLayout",
    "android.widget.ScrollView",
    "android.graphics.Canvas",
    "android.graphics.Paint",
    "android.graphics.Color",
]


def search_catalog_classes(query: str) -> List[Dict[str, str]]:
    """Filters common known Telegram / Android classes matching query."""
    q = query.lower().strip()
    matches = []
    for full_name in COMMON_TELEGRAM_CLASSES:
        simple_name = full_name.split(".")[-1]
        if q in full_name.lower():
            matches.append({
                "class": full_name,
                "name": simple_name,
                "package": full_name.rsplit(".", 1)[0] if "." in full_name else "",
            })
    return matches


def generate_hook_snippet(class_name: str, method_name: str, params: List[str]) -> str:
    """Generates ready-to-paste Python code for hook_method."""
    param_types_str = ", ".join([f"find_class('{p}')" if "." in p else f"'{p}'" for p in params])
    if param_types_str:
        get_method_call = f"find_class('{class_name}').getDeclaredMethod('{method_name}', {param_types_str})"
    else:
        get_method_call = f"find_class('{class_name}').getDeclaredMethod('{method_name}')"

    snippet = f"""from hook_utils import find_class
from base_plugin import MethodHook

class {method_name.capitalize()}Hook(MethodHook):
    def before_hooked_method(self, param):
        pass

    def after_hooked_method(self, param):
        result = param.getResult()

# In on_plugin_load:
target_method = {get_method_call}
self.hook_method(target_method, {method_name.capitalize()}Hook())
"""
    return snippet


def generate_stub_code(class_name: str, methods: List[Dict[str, Any]], mode: str = "subclass") -> str:
    """Generates Python stub for a Java class or interface."""
    short_name = class_name.split(".")[-1]
    pkg = class_name.rsplit(".", 1)[0] if "." in class_name else ""

    lines = []
    if mode == "proxy":
        lines.append("from java import dynamic_proxy")
        lines.append(f"from {pkg} import {short_name}\n")
        lines.append(f"@dynamic_proxy({short_name})")
        lines.append(f"class My{short_name}Proxy:")
        if not methods:
            lines.append("    pass\n")
        else:
            for m in methods:
                name = m.get("name", "method")
                params = m.get("params", [])
                p_args = ", ".join(["self"] + [f"arg{i}" for i in range(len(params))])
                lines.append(f"    def {name}({p_args}):")
                lines.append("        pass\n")
    else:  # subclass
        lines.append("from extera_utils.classes import Base, java_subclass, joverload")
        lines.append(f"from {pkg} import {short_name}\n")
        lines.append(f"@java_subclass({short_name})")
        lines.append(f"class Custom{short_name}(Base):")
        if not methods:
            lines.append("    pass\n")
        else:
            for m in methods:
                name = m.get("name", "method")
                params = m.get("params", [])
                param_types = [repr(p) for p in params]
                p_args = ", ".join(["self"] + [f"arg{i}" for i in range(len(params))])
                super_args = ", ".join([f"arg{i}" for i in range(len(params))])
                lines.append(f"    @joverload({repr(name)}, [{', '.join(param_types)}])")
                lines.append(f"    def {name}({p_args}):")
                lines.append(f"        return super().{name}({super_args})\n")

    return "\n".join(lines)
