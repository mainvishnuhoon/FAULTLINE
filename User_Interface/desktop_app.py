"""FAULTLINE Native Desktop GUI - Red & White Theme.

Tkinter-based desktop interface for FAULTLINE.
"""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# Ensure root directory is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import build_registry, load_dotenv
from agent import Agent
from tools import DemoTools
from state import format_report

# Color palette: Red & White
COLOR_WHITE = "#ffffff"
COLOR_BG = "#f8fafc"
COLOR_CARD = "#ffffff"
COLOR_RED_PRIMARY = "#dc2626"
COLOR_RED_HOVER = "#b91c1c"
COLOR_RED_DARK = "#991b1b"
COLOR_RED_LIGHT = "#fef2f2"
COLOR_RED_BORDER = "#fecaca"
COLOR_TEXT_MAIN = "#0f172a"
COLOR_TEXT_MUTED = "#64748b"
COLOR_TERMINAL_BG = "#0f172a"
COLOR_TERMINAL_FG = "#f8fafc"

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


class FaultlineDesktopUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("FAULTLINE — Autonomous Debugging Agent")
        self.root.geometry("1080x750")
        self.root.minsize(850, 600)
        self.root.configure(bg=COLOR_BG)

        load_dotenv(PROJECT_ROOT / ".env")

        self.is_running = False
        self.stop_requested = False
        self.log_queue: queue.Queue[str] = queue.Queue()

        self._create_widgets()
        self.root.after(100, self._process_log_queue)

    def _create_widgets(self) -> None:
        # Top Red Accent Banner
        top_accent = tk.Frame(self.root, bg=COLOR_RED_PRIMARY, height=5)
        top_accent.pack(fill=tk.X, side=tk.TOP)

        # Header Frame
        header_frame = tk.Frame(self.root, bg=COLOR_WHITE, padx=20, pady=12, highlightthickness=1, highlightbackground=COLOR_RED_BORDER)
        header_frame.pack(fill=tk.X)

        title_lbl = tk.Label(
            header_frame,
            text="⚡ FAULTLINE",
            font=("Helvetica", 18, "bold"),
            fg=COLOR_RED_PRIMARY,
            bg=COLOR_WHITE,
        )
        title_lbl.pack(side=tk.LEFT)

        subtitle_lbl = tk.Label(
            header_frame,
            text="  Autonomous Python Debugging Agent (Red & White Edition)",
            font=("Helvetica", 11),
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_WHITE,
        )
        subtitle_lbl.pack(side=tk.LEFT, pady=(3, 0))

        self.status_label = tk.Label(
            header_frame,
            text="● AGENT IDLE",
            font=("Helvetica", 11, "bold"),
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_RED_LIGHT,
            padx=12,
            pady=4,
            relief=tk.FLAT,
        )
        self.status_label.pack(side=tk.RIGHT)

        # Main Split Content
        main_split = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg=COLOR_BG, sashwidth=6)
        main_split.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        # Left Control Panel
        left_frame = tk.Frame(main_split, bg=COLOR_WHITE, padx=16, pady=16, highlightthickness=1, highlightbackground=COLOR_RED_BORDER)
        main_split.add(left_frame, width=420)

        # Config Title
        tk.Label(
            left_frame,
            text="Agent Configuration",
            font=("Helvetica", 13, "bold"),
            fg=COLOR_RED_DARK,
            bg=COLOR_WHITE,
        ).pack(anchor=tk.W, pady=(0, 12))

        # Mode Selection
        mode_frame = tk.Frame(left_frame, bg=COLOR_WHITE)
        mode_frame.pack(fill=tk.X, pady=(0, 10))

        self.mode_var = tk.StringVar(value="demo")
        rb_demo = tk.Radiobutton(
            mode_frame,
            text="Prepared Demo (2 Bugs)",
            variable=self.mode_var,
            value="demo",
            command=self._on_mode_change,
            bg=COLOR_WHITE,
            fg=COLOR_TEXT_MAIN,
            activebackground=COLOR_WHITE,
            selectcolor=COLOR_RED_LIGHT,
            font=("Helvetica", 10, "bold"),
        )
        rb_demo.pack(side=tk.LEFT, padx=(0, 10))

        rb_custom = tk.Radiobutton(
            mode_frame,
            text="Custom Repo",
            variable=self.mode_var,
            value="custom",
            command=self._on_mode_change,
            bg=COLOR_WHITE,
            fg=COLOR_TEXT_MAIN,
            activebackground=COLOR_WHITE,
            selectcolor=COLOR_RED_LIGHT,
            font=("Helvetica", 10),
        )
        rb_custom.pack(side=tk.LEFT)

        # Repo Path
        tk.Label(left_frame, text="REPOSITORY PATH:", font=("Helvetica", 9, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_WHITE).pack(anchor=tk.W)
        self.repo_entry = tk.Entry(left_frame, font=("Helvetica", 10), relief=tk.SOLID, bd=1)
        self.repo_entry.insert(0, str(PROJECT_ROOT / "demo_repo"))
        self.repo_entry.pack(fill=tk.X, pady=(2, 10))

        # Bug Description
        tk.Label(left_frame, text="BUG DESCRIPTION:", font=("Helvetica", 9, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_WHITE).pack(anchor=tk.W)
        self.bug_text = tk.Text(left_frame, height=4, font=("Helvetica", 10), relief=tk.SOLID, bd=1, wrap=tk.WORD)
        default_bug = (
            "The calculator's total calculation is wrong for discounted items, and its "
            "average helper crashes for an empty list. Investigate and fix both implementation bugs."
        )
        self.bug_text.insert(tk.END, default_bug)
        self.bug_text.pack(fill=tk.X, pady=(2, 10))

        # Groq API Key
        tk.Label(left_frame, text="GROQ API KEY:", font=("Helvetica", 9, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_WHITE).pack(anchor=tk.W)
        api_frame = tk.Frame(left_frame, bg=COLOR_WHITE)
        api_frame.pack(fill=tk.X, pady=(2, 10))
        self.api_entry = tk.Entry(api_frame, font=("Helvetica", 10), relief=tk.SOLID, bd=1, show="*")
        self.api_entry.insert(0, os.getenv("GROQ_API_KEY", ""))
        self.api_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn_save_key = tk.Button(
            api_frame,
            text="Save",
            font=("Helvetica", 9, "bold"),
            bg=COLOR_RED_LIGHT,
            fg=COLOR_RED_PRIMARY,
            relief=tk.SOLID,
            bd=1,
            command=self._save_key,
        )
        btn_save_key.pack(side=tk.RIGHT, padx=(6, 0))

        # Model & Steps
        settings_frame = tk.Frame(left_frame, bg=COLOR_WHITE)
        settings_frame.pack(fill=tk.X, pady=(0, 14))

        tk.Label(settings_frame, text="MODEL:", font=("Helvetica", 9, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_WHITE).grid(row=0, column=0, sticky=tk.W)
        self.model_combo = ttk.Combobox(
            settings_frame,
            values=["openai/gpt-oss-20b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
            state="readonly",
        )
        self.model_combo.set("openai/gpt-oss-20b")
        self.model_combo.grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(2, 0))

        tk.Label(settings_frame, text="MAX STEPS:", font=("Helvetica", 9, "bold"), fg=COLOR_TEXT_MUTED, bg=COLOR_WHITE).grid(row=0, column=1, sticky=tk.W)
        self.steps_spin = tk.Spinbox(settings_frame, from_=1, to=30, width=6, font=("Helvetica", 10))
        self.steps_spin.delete(0, tk.END)
        self.steps_spin.insert(0, "12")
        self.steps_spin.grid(row=1, column=1, sticky=tk.W, pady=(2, 0))

        # Primary Action Buttons
        self.btn_run = tk.Button(
            left_frame,
            text="⚡ Start Autonomous Agent",
            font=("Helvetica", 11, "bold"),
            bg=COLOR_RED_PRIMARY,
            fg=COLOR_WHITE,
            activebackground=COLOR_RED_HOVER,
            activeforeground=COLOR_WHITE,
            relief=tk.FLAT,
            padx=16,
            pady=10,
            cursor="hand2",
            command=lambda: self._start_agent(simulate=False),
        )
        self.btn_run.pack(fill=tk.X, pady=(4, 6))

        self.btn_simulate = tk.Button(
            left_frame,
            text="✨ Simulate Demo Run (Offline)",
            font=("Helvetica", 10, "bold"),
            bg=COLOR_RED_LIGHT,
            fg=COLOR_RED_PRIMARY,
            activebackground=COLOR_RED_BORDER,
            relief=tk.SOLID,
            bd=1,
            pady=6,
            cursor="hand2",
            command=lambda: self._start_agent(simulate=True),
        )
        self.btn_simulate.pack(fill=tk.X, pady=(0, 8))

        quick_btns_frame = tk.Frame(left_frame, bg=COLOR_WHITE)
        quick_btns_frame.pack(fill=tk.X, pady=(0, 6))

        btn_test = tk.Button(
            quick_btns_frame,
            text="🧪 Run Tests Now",
            font=("Helvetica", 9, "bold"),
            bg=COLOR_WHITE,
            fg=COLOR_TEXT_MAIN,
            relief=tk.SOLID,
            bd=1,
            command=self._run_tests_now,
        )
        btn_test.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        btn_reset = tk.Button(
            quick_btns_frame,
            text="🔄 Reset Demo",
            font=("Helvetica", 9, "bold"),
            bg=COLOR_WHITE,
            fg=COLOR_RED_PRIMARY,
            relief=tk.SOLID,
            bd=1,
            command=self._reset_demo,
        )
        btn_reset.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

        self.btn_stop = tk.Button(
            left_frame,
            text="⏹ Stop Agent",
            font=("Helvetica", 10, "bold"),
            bg=COLOR_WHITE,
            fg=COLOR_RED_PRIMARY,
            relief=tk.SOLID,
            bd=1,
            state=tk.DISABLED,
            command=self._stop_agent,
        )
        self.btn_stop.pack(fill=tk.X, pady=(4, 0))

        # Right Panel: Output and Trace Log
        right_frame = tk.Frame(main_split, bg=COLOR_WHITE, padx=16, pady=16, highlightthickness=1, highlightbackground=COLOR_RED_BORDER)
        main_split.add(right_frame, width=620)

        tk.Label(
            right_frame,
            text="Live Trace & Verification Log",
            font=("Helvetica", 13, "bold"),
            fg=COLOR_RED_DARK,
            bg=COLOR_WHITE,
        ).pack(anchor=tk.W, pady=(0, 8))

        self.log_text = scrolledtext.ScrolledText(
            right_frame,
            bg=COLOR_TERMINAL_BG,
            fg=COLOR_TERMINAL_FG,
            insertbackground=COLOR_WHITE,
            font=("Courier", 11),
            wrap=tk.WORD,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Initial banner
        self._append_log(
            "============================================================\n"
            "  ⚡ FAULTLINE Autonomous Debugging Agent (Ready)\n"
            "  Color Scheme: Red & White Edition\n"
            "============================================================\n"
            "Ready for execution.\n"
        )

    def _append_log(self, text: str) -> None:
        self.log_queue.put(text)

    def _process_log_queue(self) -> None:
        while not self.log_queue.empty():
            msg = self.log_queue.get_nowait()
            self.log_text.insert(tk.END, msg)
            self.log_text.see(tk.END)
        self.root.after(100, self._process_log_queue)

    def _on_mode_change(self) -> None:
        if self.mode_var.get() == "demo":
            self.repo_entry.delete(0, tk.END)
            self.repo_entry.insert(0, str(PROJECT_ROOT / "demo_repo"))
            self.bug_text.delete("1.0", tk.END)
            self.bug_text.insert(
                tk.END,
                "The calculator's total calculation is wrong for discounted items, and its "
                "average helper crashes for an empty list. Investigate and fix both implementation bugs.",
            )
        else:
            self.repo_entry.delete(0, tk.END)
            self.bug_text.delete("1.0", tk.END)

    def _save_key(self) -> None:
        key = self.api_entry.get().strip()
        if not key:
            messagebox.showwarning("Empty Key", "Please enter a valid Groq API key.")
            return
        os.environ["GROQ_API_KEY"] = key
        env_file = PROJECT_ROOT / ".env"
        lines = []
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("GROQ_API_KEY="):
                    continue
                lines.append(line)
        lines.append(f"GROQ_API_KEY={key}")
        env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        messagebox.showinfo("Saved", "GROQ_API_KEY saved to .env!")

    def _reset_demo(self) -> None:
        demo_calc = PROJECT_ROOT / "demo_repo" / "calculator.py"
        try:
            demo_calc.write_text(BUGGY_CALCULATOR_CODE, encoding="utf-8")
            self._append_log("\n[RESET] demo_repo/calculator.py restored to baseline buggy code.\n")
            messagebox.showinfo("Reset Demo", "Demo repository reset to original buggy state.")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to reset demo: {exc}")

    def _run_tests_now(self) -> None:
        repo = Path(self.repo_entry.get().strip() or (PROJECT_ROOT / "demo_repo")).resolve()
        self._append_log(f"\n[MANUAL TEST] Running unittest in {repo}...\n")
        try:
            tools = DemoTools(repo)
            res = tools.run_tests()
            status = "PASSED ✅" if res.get("passed") else f"FAILED ❌ (Exit code {res.get('exit_code')})"
            self._append_log(f"Status: {status}\n{res.get('output')}\n")
        except Exception as exc:
            self._append_log(f"Error running tests: {exc}\n")

    def _stop_agent(self) -> None:
        self.stop_requested = True
        self._append_log("\n[SYSTEM] Stop requested by user.\n")

    def _start_agent(self, simulate: bool = False) -> None:
        if self.is_running:
            return

        api_key = self.api_entry.get().strip()
        if not simulate and not api_key and not os.getenv("GROQ_API_KEY"):
            messagebox.showwarning(
                "API Key Missing",
                "Please enter a GROQ_API_KEY or choose 'Simulate Demo Run (Offline)'.",
            )
            return

        self.is_running = True
        self.stop_requested = False
        self.status_label.config(text="● RUNNING...", fg=COLOR_RED_PRIMARY, bg=COLOR_RED_LIGHT)
        self.btn_run.config(state=tk.DISABLED)
        self.btn_simulate.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)

        repo = self.repo_entry.get().strip() or str(PROJECT_ROOT / "demo_repo")
        bug = self.bug_text.get("1.0", tk.END).strip()
        model = self.model_combo.get()
        max_steps = int(self.steps_spin.get() or 12)

        def worker() -> None:
            try:
                try:
                    from User_Interface.app import runner
                except ImportError:
                    from app import runner
                runner.start_run(
                    repo_root=repo,
                    bug_report=bug,
                    model=model,
                    max_steps=max_steps,
                    api_key=api_key,
                    simulate=simulate,
                )
                # Listen to runner log messages
                q = runner.subscribe()
                while runner.is_running:
                    try:
                        msg = q.get(timeout=0.5)
                        if msg.get("event") == "log":
                            self._append_log(msg["data"]["line"] + "\n")
                    except queue.Empty:
                        continue
                runner.unsubscribe(q)
            except Exception as exc:
                self._append_log(f"\n[ERROR] {exc}\n")
            finally:
                self.is_running = False
                self.root.after(0, self._on_agent_finished)

        threading.Thread(target=worker, daemon=True).start()

    def _on_agent_finished(self) -> None:
        self.status_label.config(text="● IDLE", fg=COLOR_TEXT_MUTED, bg=COLOR_RED_LIGHT)
        self.btn_run.config(state=tk.NORMAL)
        self.btn_simulate.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)


def run_desktop_app() -> None:
    root = tk.Tk()
    app = FaultlineDesktopUI(root)
    root.mainloop()


if __name__ == "__main__":
    run_desktop_app()
