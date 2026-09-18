# Track 2 mapping: source-backed evidence

No Track 2 rubric is present in this repository. This mapping therefore covers only requirements that can be supported by the checked-in implementation; it does not infer unstated judging criteria.

| Demonstrable requirement | Evidence | What the implementation does |
| --- | --- | --- |
| Accept a target repository and bug description | `main.py`: `parse_args`, `main` | Accepts `--repo` and `--bug`; `--demo` selects the included calculator repository. |
| Use an LLM-driven debugging loop | `agent.py`: `Agent.__init__`, `Agent.run`; `SYSTEM_PROMPT` | Creates an OpenAI client for Groq's compatible endpoint and presents tool schemas with `tool_choice="auto"` in a bounded loop. |
| Inspect repository files | `tools.py`: `DemoTools.inspect_repo`; `main.py`: `build_registry` | Lists eligible files or reads a selected file, exposed as `inspect_repo`. |
| Execute automated tests | `tools.py`: `DemoTools.run_tests`; `main.py`: `build_registry` | Runs `python -m unittest discover -v`, returns output, exit code, and `passed`; applies a 30-second timeout. |
| Make an implementation edit | `tools.py`: `DemoTools.edit_file`; `main.py`: `build_registry` | Replaces the full content of an existing `.py` implementation file through `edit_file`. |
| Protect test files and preserve a pre-edit copy | `tools.py`: `DemoTools.edit_file` | Rejects names beginning `test_` and files whose direct parent is `tests`; copies the original into `.faultline_backups/` before writing. |
| Constrain repository path access | `tools.py`: `DemoTools._safe_path` | Resolves a requested path and rejects it if it is outside the selected root. |
| Track work and present a final result | `agent.py`: `AgentState`, `AgentResult`, `Agent._record_observation`, `Agent.run`; `state.py`: `format_report` | Tracks steps, inspected/changed files, test count, and trace; formats a final report. |
| Provide a visual interface and execution trace | `User_Interface/app.py`: `AgentRunner`, `FaultlineHttpHandler._serve_sse`, `run_web_server`; `User_Interface/index.html` | Hosts a web UI, sends status/step/log events over SSE, and displays the trace, report, tests, and diff. |
| Provide a desktop interface | `User_Interface/desktop_app.py`: `FaultlineDesktopUI`, `run_desktop_app` | Offers a Tkinter controller that delegates agent runs to the shared web-app runner. |
| Support an API-key-free prepared demo | `User_Interface/app.py`: `AgentRunner._run_simulation`, `FIXED_CALCULATOR_CODE`; `User_Interface/desktop_app.py`: `FaultlineDesktopUI._start_agent` | Executes a deterministic five-step calculator walkthrough using the real tool implementations. |

## Gaps or ambiguous areas

- A formal Track 2 requirement list is not checked into the repository, so compliance with any criterion beyond the table cannot be established from source alone.
- The tool layer is Python/unittest-specific: it does not discover or run other test frameworks, languages, linters, or build systems (`DemoTools.run_tests`).
- `edit_file` replaces an entire existing `.py` file; it cannot create files or apply a structured patch (`DemoTools.edit_file`).
- Live model behavior is not deterministic and has no guaranteed repair outcome; it is bounded by `max_steps` (`Agent.run`). The UI simulation is deterministic but is not an autonomous model-driven run (`AgentRunner._run_simulation`).
- Verification means a successful invocation of the configured unittest-discovery command. There is no independent test coverage, regression, rollback, approval, or static-analysis workflow implemented (`DemoTools.run_tests`, `Agent.run`).
- The test-file protection is naming/location based, not a broader policy that prevents every possible non-implementation edit (`DemoTools.edit_file`).
