# FAULTLINE User Interface (Red & White Theme)

A modern, high-contrast **Red and White** interface for **FAULTLINE**, the autonomous Python debugging agent.

## Features

- **Red & White Design System**: Crisp white background, cardinal and crimson red accents, ruby badges, sleek border highlights, and high-contrast carbon terminal viewer.
- **Dual Interface**:
  1. **Web UI**: Modern, responsive SPA with live Server-Sent Events (SSE) streaming, animated step timeline, and zero extra dependencies (powered by Python's built-in `http.server`).
  2. **Native Desktop GUI**: Cross-platform Tkinter GUI styled in matching Red & White colors.
- **Real-Time Step-by-Step Execution**:
  - Live timeline displaying `[STEP 1]`, `[STEP 2]`, ... with tool call cards (`inspect_repo`, `run_tests`, `edit_file`).
  - Expandable payloads showing JSON arguments and execution results.
- **Visual Code Diff Viewer**:
  - Automatically compares the modified file with backups generated in `.faultline_backups/`.
  - Color-coded additions (+) and removals (-).
- **Integrated Test Runner**:
  - One-click execution of `python -m unittest discover -v` to inspect test results at any time.
- **Demo Mode & Safe Reset**:
  - Toggle between **Prepared Demo (2 Bugs)** and **Custom Repository**.
  - One-click **Reset Demo** button to revert `demo_repo/calculator.py` back to its original buggy baseline for repeated testing.
- **Simulate Demo Run**:
  - Test and evaluate the full observe-reason-edit-verify workflow even without a Groq API key!

---

## Quick Start

### 1. Launch the Web UI (Default)

From the project root:

```bash
python3 user_interface.py
```

Or using `main.py`:

```bash
python3 main.py --ui
```

Or run directly from the package:

```bash
python3 User_Interface/app.py
```

This will automatically open your default browser at `http://127.0.0.1:5050`.

### 2. Launch the Native Desktop GUI (Tkinter)

```bash
python3 user_interface.py --desktop
```

Or:

```bash
python3 main.py --desktop
```

---

## Options & Arguments

| Argument | Description | Default |
|---|---|---|
| `--port PORT` | Port for the Web UI server | `5050` |
| `--host HOST` | Host address | `127.0.0.1` |
| `--no-browser`| Start web server without automatically opening browser | `False` |
| `--desktop`   | Launch native Tkinter GUI instead of Web UI | `False` |
