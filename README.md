# FAULTLINE

FAULTLINE is a small autonomous debugging agent for a hackathon demo. It uses Groq's OpenAI-compatible API to inspect a Python repository, run its tests, reason over the results, edit implementation code, and verify the fix.

## Run the prepared demo

From this directory:

### macOS / Linux:
```bash
# Optional: activate virtual environment
source .venv/bin/activate

# Set API key (or create a .env file from .env.example)
export GROQ_API_KEY="your-key"

# Run the CLI agent
python3 main.py --demo
```

### Windows (PowerShell):
```powershell
python -m pip install -r requirements.txt
$env:GROQ_API_KEY = "your-key"
python main.py --demo
```

You can also copy `.env.example` to `.env` and put the key there (`cp .env.example .env`). The demo contains two intentionally failing tests: tax is calculated from the wrong base, and `average([])` raises instead of returning `0.0`.

## Run against another small Python repository

```bash
python3 main.py --repo /path/to/repo --bug "Describe the failing behavior"
```

The agent can list/read files, run only `python -m unittest discover -v`, and edit existing implementation `.py` files inside the selected repository. Every edit is backed up in `.faultline_backups/`; tests are protected from edits.

## User Interface (Red & White Edition)

FAULTLINE includes a dedicated User Interface inside the `User_Interface` package with a high-contrast Red & White theme:

```bash
# Launch the Web UI (opens in browser at http://127.0.0.1:5050):
python3 user_interface.py
# or:
python3 main.py --ui

# Launch the native Tkinter Desktop GUI:
python3 user_interface.py --desktop
# or:
python3 main.py --desktop
```

Features included:
- Live step-by-step trace timeline with expandable tool payloads (`inspect_repo`, `run_tests`, `edit_file`)
- Real-time terminal trace stream and logs
- Visual code diff viewer with backup comparisons
- Instant unittest execution and one-click demo repository reset
- Offline simulation mode to evaluate the entire agent flow without an API key

## What the trace demonstrates

The terminal prints each dynamically selected tool call as `[STEP N]`, including the structured result. A typical run is: inspect files, read source/tests, run failing tests, edit the implementation, run tests again, and print a final report. The model—not a hardcoded sequence—selects the next tool based on the preceding result.

## Environment

- Python 3.10+
- `GROQ_API_KEY` required
- Optional `FAULTLINE_MODEL` or `--model` (default `openai/gpt-oss-20b`)

