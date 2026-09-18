"""The FAULTLINE autonomous debugging loop."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from openai import OpenAI

from registry import ToolRegistry


SYSTEM_PROMPT = """You are FAULTLINE, an autonomous debugging agent.

Your job is to investigate and fix the user's reported bug in the repository.
You have three tools: inspect_repo, run_tests, and edit_file. You must choose
tools dynamically from observations; do not assume a fixed sequence.

Work like this: inspect the repository and relevant source/tests, run the test
suite to establish a baseline, reason about the failure, edit only the source
files needed, and run the tests again. Continue investigating or correcting
your edit until the tests pass or you have a concrete blocker.

Important rules:
- The repository root supplied by the user is the only workspace you may use.
- Never edit tests to make them pass.
- Use inspect_repo before editing so you understand the implementation and its tests.
- edit_file requires complete replacement content for an existing source file.
- Keep changes minimal and explain your hypothesis after observing tool output.
- At the end, give a concise report of the bug, files changed, verification, and fix.
"""


@dataclass
class AgentState:
    bug_report: str
    repo_root: str
    steps: int = 0
    files_inspected: list[str] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    tests_run: int = 0
    reasoning_notes: list[str] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentResult:
    final_message: str
    state: AgentState
    verification_passed: bool


class Agent:
    """LLM-driven tool user with a bounded observe/reason/act loop."""

    def __init__(
        self,
        registry: ToolRegistry,
        bug_report: str,
        repo_root: str,
        model: str | None = None,
        max_steps: int = 12,
    ) -> None:
        self.registry = registry
        self.state = AgentState(bug_report=bug_report, repo_root=repo_root)
        self.model = model or os.getenv("FAULTLINE_MODEL", "openai/gpt-oss-20b")
        self.max_steps = max_steps
        self.client = OpenAI(
            api_key=os.getenv("GROQ_API_KEY"),
            base_url="https://api.groq.com/openai/v1",
        )

    def _record_observation(self, tool_name: str, result: dict[str, Any]) -> None:
        if tool_name == "inspect_repo":
            for path in result.get("files", []):
                if path not in self.state.files_inspected:
                    self.state.files_inspected.append(path)
            path = result.get("path")
            if path and path not in self.state.files_inspected:
                self.state.files_inspected.append(path)
        elif tool_name == "edit_file" and result.get("ok"):
            path = result.get("path")
            if path and path not in self.state.files_changed:
                self.state.files_changed.append(path)
        elif tool_name == "run_tests":
            self.state.tests_run += 1

    def _print_step(self, step: int, tool_name: str, result: dict[str, Any]) -> None:
        print(f"\n[STEP {step}]\nTool: {tool_name}")
        compact = json.dumps(result, indent=2, ensure_ascii=False)
        if len(compact) > 7000:
            compact = compact[:7000] + "\n... output truncated ..."
        print(f"Result: {compact}")

    def run(self) -> AgentResult:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Repository root: {self.state.repo_root}\n"
                    f"Bug report: {self.state.bug_report}\n"
                    "Begin by investigating the repository."
                ),
            },
        ]
        final_message = "The agent stopped before producing a final explanation."
        verification_passed = False

        for _ in range(self.max_steps):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.registry.openai_schemas(),
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

            if not tool_calls:
                final_message = message.content or final_message
                break

            for call in tool_calls:
                self.state.steps += 1
                tool_name = call.function.name
                raw_arguments = call.function.arguments
                result = self.registry.execute(tool_name, raw_arguments)
                self._record_observation(tool_name, result)
                self.state.trace.append(
                    {"step": self.state.steps, "tool": tool_name, "result": result}
                )
                self._print_step(self.state.steps, tool_name, result)
                if tool_name == "run_tests" and result.get("passed"):
                    verification_passed = True
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )

        else:
            final_message = (
                f"Stopped after the {self.max_steps}-step safety limit. "
                "Review the trace and continue with a narrower bug report."
            )

        return AgentResult(
            final_message=final_message,
            state=self.state,
            verification_passed=verification_passed,
        )
