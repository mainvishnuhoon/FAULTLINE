"""Small state/report helpers kept separate from the agent loop."""

from __future__ import annotations

from agent import AgentResult


def format_report(result: AgentResult) -> str:
    state = result.state
    changed = ", ".join(state.files_changed) or "none"
    inspected = ", ".join(state.files_inspected) or "none"
    status = "PASSED" if result.verification_passed else "NOT VERIFIED"
    return f"""
FINAL REPORT
============
Bug identified:
{state.bug_report}

Files inspected: {inspected}
Tests run: {state.tests_run}
Hypothesis/reasoning summary:
{result.final_message}

Files changed: {changed}
Verification: {status}
""".strip()
