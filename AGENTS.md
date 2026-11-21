# AGENTS.md — Extera Toolkit Operational Guide for AI Agents

This document defines the operational rules, interface contracts, diagnostic workflows, and anti-patterns for AI coding agents working with **Extera Toolkit** (`extera-toolkit` / `etk`).

---

## 1. Operating Environment & Philosophy

`extera-toolkit` is a CLI toolkit designed to test, debug, inspect, and deploy plugins for **exteraGram**, **Telegram**, and **AyuGram** over ADB and the built-in development server (`127.0.0.1:42690`).

### Preferred CLI Executable: `etk`
* **Always use `etk` instead of `extera-toolkit`**: The short executable alias `etk` is identical in behavior to `extera-toolkit`. AI agents must use `etk` in all shell commands to conserve prompt/completion tokens and reduce context footprint.

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
etk config --set-format toon
```
Once configured, all subsequent commands will automatically output in TOON format without needing explicit flags.

Alternatively, pass `--toon` explicitly:
```bash
etk status --toon
```

---

## 3. Core Commands & Workflows

### 3.1 Environment & Diagnostic Status
Before performing any action, verify device connectivity and dev server status:
```bash
etk status
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
etk push kanban_board/
```
* Use `--clean` when updating UI hooks or action bar items to disable the old instance first and prevent duplicate buttons:
  ```bash
  etk push kanban_board/ --clean
  ```

#### Clean Reload (`reload`)
If a plugin registers UI views or menu hooks, a standard reload may leave ghost views. Use `--clean` to trigger `on_plugin_unload` before re-enabling:
```bash
etk reload kanban_board --clean
```

---

### 3.3 Live Runtime Evaluation (`eval` & `exec`)

Instead of editing plugin code, deploying, and checking files, execute Python/Java code **directly inside the running Telegram process**:

```bash
etk eval "UserConfig.selectedAccount"
```
```bash
etk eval "MessagesController.getInstance(0).getTopicsController().getTopics(-1001234567890)"
```

Common pre-imported modules in eval scope:
* `MessagesController`, `MessagesStorage`, `SendMessagesHelper`, `UserConfig`, `SharedConfig`
* `AndroidUtilities`, `ApplicationLoader`, `NotificationCenter`
* `TLRPC`, `ConnectionsManager`
* `jclass`, `dynamic_proxy`, `jint`, `jlong`

To execute a multi-line diagnostic script from disk:
```bash
etk exec scratch_diag.py
```

---

### 3.4 UI Inspection & Interaction (`ui`)

#### Dump On-Screen Elements
Inspect active fragments, dialogs, bottom sheets, and buttons:
```bash
etk ui dump --clickable
```
Filter by label or keyword:
```bash
etk ui dump --filter "Kanban"
```
Returns structured elements with text, resource ID, bounds, and calculated center coordinates `[cx, cy]`.

#### Click an Element
Click an element by its visible text, content description, or resource ID:
```bash
etk ui click "Telegram Kanban"
```
```bash
etk ui click "action_bar_title"
```

#### Visual Verification (Screenshot)
When visual validation is explicitly required:
```bash
etk ui screenshot /tmp/board.png --bounds 0,100,1280,800
```

#### Gestures & Scrolling
Swipe or scroll lists and views:
```bash
etk ui swipe down
etk ui swipe left
```

---

### 3.5 Runtime Introspection (`inspect`)
Query methods, fields, and inheritance of any Java or Python class without guessing or reading outdated sources:
```bash
etk inspect class org.telegram.ui.Cells.DialogCell
```
Inspect a live object's fields:
```bash
etk inspect expr "MessagesController.getInstance(0)"
```

---

### 3.6 Java / Kotlin Interop & Class Discovery

#### Class & Method Search
Quickly find Telegram/Android classes without grepping entire source repositories:
```bash
etk search class DialogCell
```

#### Hook Overload Inspector
Inspect all overloads of a Java method and generate exact `hook_method` recipes:
```bash
etk hook-info org.telegram.ui.Cells.DialogCell onDraw
```

#### Stub Generator
Generate ready-to-paste Python code for Chaquopy subclasses or dynamic proxies:
```bash
etk stub android.view.View.OnClickListener --mode proxy
etk stub android.widget.FrameLayout --mode subclass
```

#### Signed Type & Color Conversion (`jtypes`)
Convert hex colors or unsigned numbers to Java signed 32-bit `jint` to avoid `OverflowError`:
```bash
etk jtypes color "#FF1E88E5"
etk jtypes to-signed "0xFFFFFFFF"
```

---

### 3.7 Telegram Runtime State & SQLite Database

#### Inspect Active Screen / Fragment Stack
Query currently displayed fragment, dialog ID, topic, and active bottom sheets:
```bash
etk runtime fragment
```

#### Query Internal SQLite Database
Directly inspect local SQLite tables (`messages`, `dialogs`, `topics`) via `MessagesStorage`:
```bash
etk db "SELECT mid, uid, message FROM messages ORDER BY date DESC LIMIT 10"
```

---

### 3.8 Static Analysis & Linter (`lint`)
Validate plugin code against common runtime traps before deployment:
```bash
etk lint kanban_board/
```
Catches:
* Unsigned color literals passed to Java methods without `to_jint`
* Leaked UI hooks without `on_plugin_unload` cleanup (prevents button duplication)
* Blocking `time.sleep` calls on UI thread
* Missing or malformed plugin metadata

---

### 3.9 Log Monitoring & Crash Traces (`logs` & `crash`)

Retrieve clean plugin logs:
```bash
etk logs --plugin kanban_board --tail 30
```
Inspect recent application crash traces:
```bash
etk crash --tail 50
```

---

### 3.10 Remote Filesystem (`fs`)
Read or search files in device sandbox or external storage without complex shell pipelines:
```bash
etk fs ls /sdcard/Android/data/org.telegram.messenger/files/
etk fs tail /sdcard/Download/plugin_debug.log -n 30
etk fs grep "Error" /sdcard/Download/plugin_debug.log
```

---

### 3.11 Device Connection & Clean Restart
Connect over Wi-Fi ADB:
```bash
etk connect 192.168.1.50:5555
```
Restart app:
```bash
etk restart
```

---

## 4. Strict Anti-Patterns for AI Agents

> [!CAUTION]
> Avoid the following anti-patterns observed in past sessions:

1. **NEVER write ad-hoc Python socket scripts (`python3 -c "import socket..."`)**:
   Use `etk dev ...`, `etk push`, or `etk eval`.
2. **NEVER guess screen tap coordinates (`adb shell input tap 1170 224`)**:
   Use `etk ui click "<label>"` or inspect coordinates with `etk ui dump --filter "<label>"`.
3. **NEVER use OCR (Tesseract / PIL) to verify if buttons or cards exist**:
   Use `etk ui dump --filter "<keyword>"`. It queries the Android Accessibility hierarchy directly and returns in milliseconds.
4. **NEVER dump unconstrained `adb logcat`**:
   Always filter with `etk logs --plugin <id> --tail <n>`.
5. **NEVER write debug values to `/sdcard/Download/*.txt`**:
   Use `self.logger.info(...)` or `etk eval "..."`.
