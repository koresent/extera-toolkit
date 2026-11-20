# AGENTS.md — Extera Toolkit Operational Guide for AI Agents

This document defines the operational rules, interface contracts, diagnostic workflows, and anti-patterns for AI coding agents working with **Extera Toolkit** (`extera-toolkit` / `tgplugin`).

---

## 1. Operating Environment & Philosophy

`extera-toolkit` is a CLI toolkit designed to test, debug, inspect, and deploy plugins for **exteraGram**, **Telegram**, and **AyuGram** over ADB and the built-in development server (`127.0.0.1:42690`).

### Core Design Principles
* **Single-Step CLI**: Replaces ad-hoc multi-step shell scripts with deterministic commands.
* **Runtime Introspection**: Test hypotheses against Telegram's runtime API via live `eval` / `exec` instead of writing print statements into plugin files.
* **Token Efficiency (TOON)**: Tabular and key-value formats minimize token overhead compared to verbose JSON dumps and raw Android logs.
* **Deterministic UI Automation**: Inspect on-screen elements by text or ID and tap their centers automatically — no coordinate guesswork or screenshot OCR.

---

## 2. Mandatory Output Format: TOON

While `extera-toolkit` supports human-readable text and JSON, **AI AGENTS MUST PREFER TOON (`--toon`)**.

### Enforcing TOON
Set persistent configuration at the beginning of your session:
```bash
tgplugin config --set-format toon
```
Once configured, all subsequent commands will automatically output in TOON format without needing explicit flags.

Alternatively, pass `--toon` explicitly:
```bash
tgplugin status --toon
```

---

## 3. Core Commands & Workflows

### 3.1 Environment & Diagnostic Status
Before performing any action, verify device connectivity and dev server status:
```bash
tgplugin status
```
Returns:
* `device_connected`: `true` / `false`
* `package`: Target Android package (e.g., `org.telegram.messenger` or `com.exteragram.messenger`)
* `pid`: Active process ID
* `dev_server_alive`: Whether TCP port 42690 is responding
* `plugins_count`: Number of loaded plugins

---

### 3.2 Deploying & Reloading Plugins

#### Deploy Plugin (`push`)
Validates Python syntax with `py_compile`, checks AST metadata (`__id__`, `__name__`), builds repository indices, and sends source code to the dev server:
```bash
tgplugin push kanban_board/
```
* Use `--clean` when updating UI hooks or action bar items to disable the old instance first and prevent duplicate buttons:
  ```bash
  tgplugin push kanban_board/ --clean
  ```

#### Clean Reload (`reload`)
If a plugin registers UI views or menu hooks, a standard reload may leave ghost views. Use `--clean` to trigger `on_plugin_unload` before re-enabling:
```bash
tgplugin reload kanban_board --clean
```

---

### 3.3 Live Runtime Evaluation (`eval` & `exec`)

Instead of editing plugin code, deploying, and checking files, execute Python/Java code **directly inside the running Telegram process**:

```bash
tgplugin eval "UserConfig.selectedAccount"
```
```bash
tgplugin eval "MessagesController.getInstance(0).getTopicsController().getTopics(-1001234567890)"
```

Common pre-imported modules in eval scope:
* `MessagesController`, `MessagesStorage`, `SendMessagesHelper`, `UserConfig`, `SharedConfig`
* `AndroidUtilities`, `ApplicationLoader`, `NotificationCenter`
* `TLRPC`, `ConnectionsManager`
* `jclass`, `dynamic_proxy`, `jint`, `jlong`

To execute a multi-line diagnostic script from disk:
```bash
tgplugin exec scratch_diag.py
```

---

### 3.4 UI Inspection & Interaction (`ui`)

#### Dump On-Screen Elements
Inspect active fragments, dialogs, bottom sheets, and buttons:
```bash
tgplugin ui dump --clickable
```
Filter by label or keyword:
```bash
tgplugin ui dump --filter "Kanban"
```
Returns structured elements with text, resource ID, bounds, and calculated center coordinates `[cx, cy]`.

#### Click an Element
Click an element by its visible text, content description, or resource ID:
```bash
tgplugin ui click "Telegram Kanban"
```
```bash
tgplugin ui click "action_bar_title"
```

#### Visual Verification (Screenshot)
When visual validation is explicitly required:
```bash
tgplugin ui screenshot /tmp/board.png --bounds 0,100,1280,800
```

#### Gestures & Scrolling
Swipe or scroll lists and views:
```bash
tgplugin ui swipe down
tgplugin ui swipe left
```

---

### 3.5 Runtime Introspection (`inspect`)
Query methods, fields, and inheritance of any Java or Python class without guessing or reading outdated sources:
```bash
tgplugin inspect class org.telegram.ui.Cells.DialogCell
```
Inspect a live object's fields:
```bash
tgplugin inspect expr "MessagesController.getInstance(0)"
```

---

### 3.6 Log Monitoring & Crash Traces (`logs` & `crash`)

Retrieve clean plugin logs:
```bash
tgplugin logs --plugin kanban_board --tail 30
```
Inspect recent application crash traces:
```bash
tgplugin crash --tail 50
```

---

### 3.7 Remote Filesystem (`fs`)
Read or search files in device sandbox or external storage without complex shell pipelines:
```bash
tgplugin fs ls /sdcard/Android/data/org.telegram.messenger/files/
tgplugin fs tail /sdcard/Download/plugin_debug.log -n 30
tgplugin fs grep "Error" /sdcard/Download/plugin_debug.log
```

---

### 3.8 Device Connection & Clean Restart
Connect over Wi-Fi ADB:
```bash
tgplugin connect 192.168.1.50:5555
```
Restart app:
```bash
tgplugin restart
```

---

## 4. Strict Anti-Patterns for AI Agents

> [!CAUTION]
> Avoid the following anti-patterns observed in past sessions:

1. **NEVER write ad-hoc Python socket scripts (`python3 -c "import socket..."`)**:
   Use `tgplugin dev ...`, `tgplugin push`, or `tgplugin eval`.
2. **NEVER guess screen tap coordinates (`adb shell input tap 1170 224`)**:
   Use `tgplugin ui click "<label>"` or inspect coordinates with `tgplugin ui dump --filter "<label>"`.
3. **NEVER use OCR (Tesseract / PIL) to verify if buttons or cards exist**:
   Use `tgplugin ui dump --filter "<keyword>"`. It queries the Android Accessibility hierarchy directly and returns in milliseconds.
4. **NEVER dump unconstrained `adb logcat`**:
   Always filter with `tgplugin logs --plugin <id> --tail <n>`.
5. **NEVER write debug values to `/sdcard/Download/*.txt`**:
   Use `self.logger.info(...)` or `tgplugin eval "..."`.
