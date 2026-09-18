#!/usr/bin/env python3
"""CLI entry point for FAULTLINE."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from agent import Agent
from registry import ToolRegistry
from state import format_report
from tools import DemoTools


def load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE lines without adding python-dotenv as a dependency."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def build_registry(repo_root: Path) -> ToolRegistry:
    tools = DemoTools(repo_root)
    registry = ToolRegistry()
    registry.register(
        "inspect_repo",
        "List repository files or read one relevant text file. Use action='list' or action='read'.",
        {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "read"]},
                "path": {"type": "string", "description": "Repository-relative path when reading"},
            },
            "required": ["action"],
            "additionalProperties": False,
        },
        tools.inspect_repo,
    )
    registry.register(
        "run_tests",
        "Run the repository's controlled Python unittest suite and return output and exit code.",
        {"type": "object", "properties": {}, "additionalProperties": False},
        tools.run_tests,
    )
    registry.register(
        "edit_file",
        "Replace an existing implementation Python file with complete new content. Tests cannot be edited.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
        tools.edit_file,
    )
    return registry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FAULTLINE autonomous Python debugging agent")
    parser.add_argument("--repo", help="Path to the buggy Python repository")
    parser.add_argument("--bug", help="Bug description; prompted interactively when omitted")
    parser.add_argument("--demo", action="store_true", help="Use the included two-bug demo repository")
    parser.add_argument("--model", help="Groq model (default: FAULTLINE_MODEL or openai/gpt-oss-20b)")
    parser.add_argument("--max-steps", type=int, default=12)
    parser.add_argument("--ui", action="store_true", help="Launch the FAULTLINE User Interface (Web)")
    parser.add_argument("--desktop", action="store_true", help="Launch the FAULTLINE native Desktop GUI")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parent

    if args.ui or args.desktop:
        from User_Interface.app import run_web_server
        from User_Interface.desktop_app import run_desktop_app
        if args.desktop:
            run_desktop_app()
        else:
            run_web_server()
        return 0

    load_dotenv(project_root / ".env")
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        print("\n[FAULTLINE] Missing or unset GROQ_API_KEY.")
        print("  1. Copy .env.example to .env:  cp .env.example .env")
        print("  2. Add your Groq API key:      GROQ_API_KEY=gsk_...")
        print("  3. Or export it in shell:      export GROQ_API_KEY=\"gsk_...\"")
        print("\n  💡 Tip: You can also test without an API key using the Web UI (Simulation Mode):")
        print("     python3 user_interface.py\n")
        return 2

    if args.demo:
        repo_root = project_root / "demo_repo"
        bug = args.bug or (
            "The calculator's total calculation is wrong for discounted items, and its "
            "average helper crashes for an empty list. Investigate and fix both implementation bugs."
        )
    else:
        repo_root = Path(args.repo or input("Repository path: ")).expanduser().resolve()
        bug = args.bug or input("Describe the bug: ")

    try:
        registry = build_registry(repo_root)
        agent = Agent(registry, bug, str(repo_root), model=args.model, max_steps=args.max_steps)
        result = agent.run()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    except Exception as exc:
        print(f"FAULTLINE could not start: {type(exc).__name__}: {exc}")
        return 1

    print("\n" + format_report(result))
    return 0 if result.verification_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
