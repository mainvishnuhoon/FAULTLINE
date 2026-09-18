"""FAULTLINE Web User Interface - Red & White Theme.

Lightweight, zero-dependency web server and real-time controller for FAULTLINE.
"""

from __future__ import annotations

import difflib
import json
import os
import queue
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

# Ensure root directory is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from agent import Agent, AgentResult, AgentState, SYSTEM_PROMPT
    from main import build_registry, load_dotenv
    from registry import ToolRegistry
    from state import format_report
    from tools import DemoTools
except ImportError:
    Agent = None
    SYSTEM_PROMPT = "You are an autonomous Python debugging agent."
    build_registry = None
    load_dotenv = None
    ToolRegistry = None
    DemoTools = None

    class AgentState:  # type: ignore[no-redef]
        def __init__(self, bug_report: str = "", repo_root: str = "") -> None:
            self.bug_report = bug_report
            self.repo_root = repo_root
            self.files_inspected: list[str] = []
            self.files_changed: list[str] = []
            self.tests_run: int = 0
            self.history: list[Any] = []

    class AgentResult:  # type: ignore[no-redef]
        def __init__(self, final_message: str = "", state: Any = None, verification_passed: bool = False) -> None:
            self.final_message = final_message
            self.state = state
            self.verification_passed = verification_passed

    def format_report(result: Any) -> str:  # type: ignore[no-redef]
        status = "PASSED" if getattr(result, "verification_passed", False) else "INCOMPLETE"
        return f"[FAULTLINE REPORT]\nStatus: {status}\n{getattr(result, 'final_message', '')}"


def _local_load_dotenv(env_path: Path) -> None:
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))

BUGGY_CALCULATOR_CODE = '''"""Tiny intentionally buggy calculator used by the FAULTLINE demo."""


def calculate_total(price: float, discount_percent: float, tax_rate: float) -> float:
    """Return the final price after discount and tax."""
    # BUG: tax is applied to the original price before the discount.
    tax = price * tax_rate
    discounted_price = price - (price * discount_percent / 100)
    return round(discounted_price + tax, 2)


def average(values: list[float]) -> float:
    """Return the arithmetic mean, or zero when there are no values."""
    # BUG: the empty-list contract is not handled.
    return sum(values) / len(values)
'''

FIXED_CALCULATOR_CODE = '''"""Tiny intentionally buggy calculator used by the FAULTLINE demo."""


def calculate_total(price: float, discount_percent: float, tax_rate: float) -> float:
    """Return the final price after discount and tax."""
    discounted_price = price - (price * discount_percent / 100)
    tax = discounted_price * tax_rate
    return round(discounted_price + tax, 2)


def average(values: list[float]) -> float:
    """Return the arithmetic mean, or zero when there are no values."""
    if not values:
        return 0.0
    return sum(values) / len(values)
'''


class AgentRunner:
    """Manages agent execution in a background thread with real-time event distribution."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.is_running = False
        self.stop_requested = False
        self.worker_thread: threading.Thread | None = None
        self.subscribers: list[queue.Queue] = []
        self.latest_status: dict[str, Any] = {
            "is_running": False,
            "verification_passed": False,
            "steps": 0,
            "max_steps": 12,
            "trace": [],
            "terminal_logs": [],
            "final_message": "",
            "report": "",
            "repo_root": str(PROJECT_ROOT / "demo_repo"),
            "bug_report": (
                "The calculator's total calculation is wrong for discounted items, and its "
                "average helper crashes for an empty list. Investigate and fix both implementation bugs."
            ),
            "model": "openai/gpt-oss-20b",
            "files_inspected": [],
            "files_changed": [],
            "tests_run": 0,
        }

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=100)
        with self.lock:
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self.lock:
            if q in self.subscribers:
                self.subscribers.remove(q)

    def publish(self, event_type: str, data: Any) -> None:
        with self.lock:
            dead_queues = []
            for q in self.subscribers:
                try:
                    q.put_nowait({"event": event_type, "data": data})
                except queue.Full:
                    dead_queues.append(q)
            for q in dead_queues:
                if q in self.subscribers:
                    self.subscribers.remove(q)

    def log(self, line: str) -> None:
        with self.lock:
            self.latest_status["terminal_logs"].append(line)
            if len(self.latest_status["terminal_logs"]) > 500:
                self.latest_status["terminal_logs"].pop(0)
        self.publish("log", {"line": line})

    def request_stop(self) -> None:
        self.stop_requested = True
        self.log("[SYSTEM] Stop requested by user.")

    def reset_status(self, repo_root: str, bug_report: str, model: str, max_steps: int) -> None:
        with self.lock:
            self.stop_requested = False
            self.latest_status = {
                "is_running": True,
                "verification_passed": False,
                "steps": 0,
                "max_steps": max_steps,
                "trace": [],
                "terminal_logs": [],
                "final_message": "",
                "report": "",
                "repo_root": repo_root,
                "bug_report": bug_report,
                "model": model,
                "files_inspected": [],
                "files_changed": [],
                "tests_run": 0,
            }
        self.publish("status", self.latest_status)

    def start_run(
        self,
        repo_root: str,
        bug_report: str,
        model: str,
        max_steps: int,
        api_key: str | None = None,
        simulate: bool = False,
    ) -> bool:
        with self.lock:
            if self.is_running:
                return False
            self.is_running = True

        if api_key:
            os.environ["GROQ_API_KEY"] = api_key

        self.reset_status(repo_root, bug_report, model, max_steps)

        def worker() -> None:
            try:
                if simulate:
                    self._run_simulation(repo_root, bug_report, max_steps)
                else:
                    self._run_real_agent(repo_root, bug_report, model, max_steps)
            except Exception as exc:
                self.log(f"[ERROR] Agent run failed: {type(exc).__name__}: {exc}")
                with self.lock:
                    self.latest_status["final_message"] = f"Error: {exc}"
                    self.latest_status["is_running"] = False
                self.publish("error", {"message": str(exc)})
            finally:
                with self.lock:
                    self.is_running = False
                    self.latest_status["is_running"] = False
                self.publish("finished", self.latest_status)

        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()
        return True

    def _run_simulation(self, repo_root_str: str, bug_report: str, max_steps: int) -> None:
        repo_root = Path(repo_root_str).resolve()
        tools = DemoTools(repo_root)
        registry = build_registry(repo_root)

        self.log(f"============================================================")
        self.log(f"  FAULTLINE Autonomous Debugging Agent (SIMULATION MODE)")
        self.log(f"  Repository: {repo_root}")
        self.log(f"  Bug: {bug_report}")
        self.log(f"============================================================")
        time.sleep(0.8)

        steps = 0
        state = AgentState(bug_report=bug_report, repo_root=str(repo_root))
        verification_passed = False

        # Step 1: inspect_repo list
        if self.stop_requested:
            return
        steps += 1
        tool_name = "inspect_repo"
        tool_args = {"action": "list"}
        self.log(f"\n[STEP {steps}]\nTool: {tool_name}\nArguments: {json.dumps(tool_args)}")
        result = tools.inspect_repo(action="list")
        self._record_step(steps, tool_name, tool_args, result, state)
        self.log(f"Result: {json.dumps(result, indent=2)}")
        time.sleep(1.2)

        # Step 2: run_tests (expect failure)
        if self.stop_requested:
            return
        steps += 1
        tool_name = "run_tests"
        tool_args = {}
        self.log(f"\n[STEP {steps}]\nTool: {tool_name}\nArguments: {{}}")
        result = tools.run_tests()
        self._record_step(steps, tool_name, tool_args, result, state)
        self.log(f"Result (Exit code {result.get('exit_code')}): \n{result.get('output')}")
        time.sleep(1.4)

        # Step 3: inspect_repo read calculator.py
        if self.stop_requested:
            return
        steps += 1
        tool_name = "inspect_repo"
        tool_args = {"action": "read", "path": "calculator.py"}
        self.log(f"\n[STEP {steps}]\nTool: {tool_name}\nArguments: {json.dumps(tool_args)}")
        result = tools.inspect_repo(action="read", path="calculator.py")
        self._record_step(steps, tool_name, tool_args, result, state)
        self.log(f"Result: Successfully read calculator.py ({len(result.get('content', ''))} bytes)")
        time.sleep(1.2)

        # Step 4: edit_file
        if self.stop_requested:
            return
        steps += 1
        tool_name = "edit_file"
        tool_args = {"path": "calculator.py", "content": FIXED_CALCULATOR_CODE}
        self.log(f"\n[STEP {steps}]\nTool: {tool_name}\nArguments: editing calculator.py to patch discount tax base and zero-length average...")
        result = tools.edit_file(path="calculator.py", content=FIXED_CALCULATOR_CODE)
        self._record_step(steps, tool_name, {"path": "calculator.py", "content": "..."}, result, state)
        self.log(f"Result: {json.dumps(result, indent=2)}")
        time.sleep(1.3)

        # Step 5: run_tests again (verification)
        if self.stop_requested:
            return
        steps += 1
        tool_name = "run_tests"
        tool_args = {}
        self.log(f"\n[STEP {steps}]\nTool: {tool_name}\nArguments: {{}}")
        result = tools.run_tests()
        if result.get("passed"):
            verification_passed = True
        self._record_step(steps, tool_name, tool_args, result, state)
        self.log(f"Result (Exit code {result.get('exit_code')}): \n{result.get('output')}")
        time.sleep(0.8)

        final_msg = (
            "Investigated the repository and identified two bugs in calculator.py: "
            "1) tax was applied to the initial price before the discount; "
            "2) average([]) raised ZeroDivisionError for empty lists. "
            "Replaced calculator.py with corrected logic and verified with unit test suite. "
            "All tests are passing."
        )
        agent_result = AgentResult(
            final_message=final_msg,
            state=state,
            verification_passed=verification_passed,
        )
        report = format_report(agent_result)
        self.log(f"\n{report}")

        with self.lock:
            self.latest_status["verification_passed"] = verification_passed
            self.latest_status["final_message"] = final_msg
            self.latest_status["report"] = report

    def _run_real_agent(self, repo_root_str: str, bug_report: str, model: str, max_steps: int) -> None:
        repo_root = Path(repo_root_str).resolve()
        registry = build_registry(repo_root)

        self.log(f"============================================================")
        self.log(f"  FAULTLINE Autonomous Debugging Agent (LIVE GROQ API)")
        self.log(f"  Repository: {repo_root}")
        self.log(f"  Model: {model}")
        self.log(f"  Bug: {bug_report}")
        self.log(f"============================================================")

        agent = Agent(registry, bug_report, str(repo_root), model=model, max_steps=max_steps)

        # Custom streaming execution
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Repository root: {agent.state.repo_root}\n"
                    f"Bug report: {agent.state.bug_report}\n"
                    "Begin by investigating the repository."
                ),
            },
        ]
        final_message = "The agent stopped before producing a final explanation."
        verification_passed = False

        for _ in range(agent.max_steps):
            if self.stop_requested:
                self.log("[SYSTEM] Execution stopped by user.")
                final_message = "Execution cancelled by user."
                break

            response = agent.client.chat.completions.create(
                model=agent.model,
                messages=messages,
                tools=agent.registry.openai_schemas(),
                tool_choice="auto",
                temperature=0,
            )
            message = response.choices[0].message
            tool_calls = message.tool_calls or []

            assistant_message: dict[str, Any] = {
                "role": "assistant",
                "content": message.content or None,
            }
            if tool_calls:
                assistant_message["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in tool_calls
                ]
            messages.append(assistant_message)

            if message.content:
                self.log(f"\n[AGENT REASONING]\n{message.content}")

            if not tool_calls:
                final_message = message.content or final_message
                break

            for call in tool_calls:
                if self.stop_requested:
                    break
                agent.state.steps += 1
                tool_name = call.function.name
                raw_arguments = call.function.arguments

                parsed_args = {}
                try:
                    parsed_args = json.loads(raw_arguments or "{}")
                except Exception:
                    pass

                self.log(f"\n[STEP {agent.state.steps}]\nTool: {tool_name}\nArguments: {raw_arguments}")

                result = agent.registry.execute(tool_name, raw_arguments)
                agent._record_observation(tool_name, result)
                agent.state.trace.append(
                    {"step": agent.state.steps, "tool": tool_name, "result": result}
                )

                compact = json.dumps(result, indent=2, ensure_ascii=False)
                if len(compact) > 7000:
                    compact = compact[:7000] + "\n... output truncated ..."
                self.log(f"Result: {compact}")

                self._record_step(agent.state.steps, tool_name, parsed_args, result, agent.state)

                if tool_name == "run_tests" and result.get("passed"):
                    verification_passed = True
                    with self.lock:
                        self.latest_status["verification_passed"] = True

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )

        res = AgentResult(
            final_message=final_message,
            state=agent.state,
            verification_passed=verification_passed,
        )
        report = format_report(res)
        self.log(f"\n{report}")

        with self.lock:
            self.latest_status["verification_passed"] = verification_passed
            self.latest_status["final_message"] = final_message
            self.latest_status["report"] = report

    def _record_step(
        self,
        step_num: int,
        tool_name: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
        state: AgentState,
    ) -> None:
        if tool_name == "inspect_repo":
            for path in result.get("files", []):
                if path not in state.files_inspected:
                    state.files_inspected.append(path)
            path = result.get("path")
            if path and path not in state.files_inspected:
                state.files_inspected.append(path)
        elif tool_name == "edit_file" and result.get("ok"):
            path = result.get("path")
            if path and path not in state.files_changed:
                state.files_changed.append(path)
        elif tool_name == "run_tests":
            state.tests_run += 1

        step_data = {
            "step": step_num,
            "tool": tool_name,
            "arguments": arguments,
            "result": result,
            "timestamp": time.strftime("%H:%M:%S"),
        }
        with self.lock:
            self.latest_status["steps"] = step_num
            self.latest_status["trace"].append(step_data)
            self.latest_status["files_inspected"] = list(state.files_inspected)
            self.latest_status["files_changed"] = list(state.files_changed)
            self.latest_status["tests_run"] = state.tests_run
        self.publish("step", step_data)


runner = AgentRunner()


def get_diff_data(repo_root: Path) -> dict[str, Any]:
    """Calculate diff between current implementation and latest backup."""
    calc_path = repo_root / "calculator.py"
    backups_dir = repo_root / ".faultline_backups"

    if not calc_path.exists():
        return {"has_diff": False, "diff": "File not found: calculator.py"}

    current_code = calc_path.read_text(encoding="utf-8")
    original_code = BUGGY_CALCULATOR_CODE

    # Check if there is a backup
    backup_file = None
    if backups_dir.exists():
        bak_files = sorted(backups_dir.glob("*.bak"), reverse=True)
        if bak_files:
            backup_file = bak_files[0]
            try:
                original_code = backup_file.read_text(encoding="utf-8")
            except Exception:
                pass

    diff = list(
        difflib.unified_diff(
            original_code.splitlines(keepends=True),
            current_code.splitlines(keepends=True),
            fromfile="Original / Backup (calculator.py)",
            tofile="Current Working Copy (calculator.py)",
        )
    )

    diff_text = "".join(diff)
    return {
        "has_diff": bool(diff_text.strip()),
        "diff_text": diff_text,
        "backup_file": backup_file.name if backup_file else None,
        "current_code": current_code,
        "original_code": original_code,
    }


class FaultlineHttpHandler(BaseHTTPRequestHandler):
    """Zero-dependency HTTP request handler for the FAULTLINE UI."""

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy HTTP request logging in terminal
        pass

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path in {"/", "/index.html"}:
            self._serve_index()
        elif path == "/api/config":
            key = os.getenv("GROQ_API_KEY", "")
            self._send_json({
                "has_api_key": bool(key),
                "api_key": key,
                "model": os.getenv("FAULTLINE_MODEL", "openai/gpt-oss-20b"),
            })
        elif path == "/api/status":
            self._send_json(runner.latest_status)
        elif path == "/api/diff":
            repo = PROJECT_ROOT / "demo_repo"
            params = parse_qs(parsed.query)
            if "repo" in params:
                repo = Path(params["repo"][0]).resolve()
            self._send_json(get_diff_data(repo))
        elif path == "/api/file":
            params = parse_qs(parsed.query)
            repo = Path(params.get("repo", [str(PROJECT_ROOT / "demo_repo")])[0]).resolve()
            rel_path = params.get("path", ["calculator.py"])[0]
            tools = DemoTools(repo)
            res = tools.inspect_repo(action="read", path=rel_path)
            self._send_json(res)
        elif path == "/api/stream":
            self._serve_sse()
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            payload = json.loads(body)
        except Exception:
            payload = {}

        if path == "/api/run":
            repo = payload.get("repo") or str(PROJECT_ROOT / "demo_repo")
            bug = payload.get("bug") or (
                "The calculator's total calculation is wrong for discounted items, and its "
                "average helper crashes for an empty list. Investigate and fix both implementation bugs."
            )
            model = payload.get("model") or "openai/gpt-oss-20b"
            max_steps = int(payload.get("max_steps", 12))
            api_key = payload.get("api_key") or os.getenv("GROQ_API_KEY", "")
            simulate = bool(payload.get("simulate", False))

            started = runner.start_run(
                repo_root=repo,
                bug_report=bug,
                model=model,
                max_steps=max_steps,
                api_key=api_key,
                simulate=simulate,
            )
            self._send_json({"ok": started, "message": "Run started" if started else "Already running"})

        elif path == "/api/stop":
            runner.request_stop()
            self._send_json({"ok": True, "message": "Stop requested"})

        elif path == "/api/run_tests":
            repo = Path(payload.get("repo") or (PROJECT_ROOT / "demo_repo")).resolve()
            tools = DemoTools(repo)
            result = tools.run_tests()
            self._send_json(result)

        elif path == "/api/inspect_repo":
            repo = Path(payload.get("repo") or (PROJECT_ROOT / "demo_repo")).resolve()
            action = payload.get("action", "list")
            rel_path = payload.get("path", "")
            tools = DemoTools(repo)
            result = tools.inspect_repo(action=action, path=rel_path)
            self._send_json(result)

        elif path == "/api/reset_demo":
            demo_calc = PROJECT_ROOT / "demo_repo" / "calculator.py"
            try:
                demo_calc.write_text(BUGGY_CALCULATOR_CODE, encoding="utf-8")
                runner.log("[RESET] demo_repo/calculator.py restored to buggy baseline.")
                self._send_json({"ok": True, "message": "Demo repository reset to original buggy state."})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)})

        elif path == "/api/save_env":
            api_key = payload.get("groq_api_key", "").strip()
            model = payload.get("model", "").strip()
            env_file = PROJECT_ROOT / ".env"
            lines = []
            if env_file.exists():
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    if line.startswith("GROQ_API_KEY=") or line.startswith("FAULTLINE_MODEL="):
                        continue
                    lines.append(line)
            if api_key:
                lines.append(f"GROQ_API_KEY={api_key}")
                os.environ["GROQ_API_KEY"] = api_key
            if model:
                lines.append(f"FAULTLINE_MODEL={model}")
                os.environ["FAULTLINE_MODEL"] = model
            env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self._send_json({"ok": True, "message": "Saved to .env successfully!"})
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def _serve_sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        q = runner.subscribe()
        try:
            # Send initial ping & status
            init_payload = json.dumps(runner.latest_status)
            self.wfile.write(f"event: status\ndata: {init_payload}\n\n".encode("utf-8"))
            self.wfile.flush()

            while True:
                try:
                    msg = q.get(timeout=20.0)
                    evt = msg.get("event", "message")
                    data = json.dumps(msg.get("data", {}))
                    self.wfile.write(f"event: {evt}\ndata: {data}\n\n".encode("utf-8"))
                    self.wfile.flush()
                except queue.Empty:
                    # Keepalive ping
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            runner.unsubscribe(q)

    def _serve_index(self) -> None:
        html_file = Path(__file__).resolve().parent / "index.html"
        if html_file.exists():
            content = html_file.read_bytes()
        else:
            content = b"<h1>FAULTLINE UI</h1><p>index.html not found</p>"

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, data: Any, status: int = 200) -> None:
        content = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(content)


def run_web_server(host: str = "127.0.0.1", port: int = 5050, open_browser: bool = True) -> None:
    if load_dotenv is not None:
        load_dotenv(PROJECT_ROOT / ".env")
    else:
        _local_load_dotenv(PROJECT_ROOT / ".env")
    server_address = (host, port)
    try:
        httpd = ThreadingHTTPServer(server_address, FaultlineHttpHandler)
    except OSError:
        # Try port fallback if 5050 is busy
        port = port + 1
        server_address = (host, port)
        httpd = ThreadingHTTPServer(server_address, FaultlineHttpHandler)

    url = f"http://{host}:{port}"
    print(f"\n" + "=" * 60)
    print(f"  ⚡ FAULTLINE User Interface (Red & White Theme)")
    print(f"  URL: {url}")
    print(f"  Press Ctrl+C to stop the UI server.")
    print("=" * 60 + "\n")

    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping FAULTLINE UI server...")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FAULTLINE Web UI")
    parser.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5050, help="Port (default: 5050)")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser")
    parser.add_argument("--desktop", action="store_true", help="Launch native Tkinter desktop UI instead")
    args = parser.parse_args()

    if args.desktop:
        try:
            from User_Interface.desktop_app import run_desktop_app
        except ImportError:
            from desktop_app import run_desktop_app
        run_desktop_app()
    else:
        run_web_server(host=args.host, port=args.port, open_browser=not args.no_browser)
