# 2–3 minute hackathon demo script

This script uses the prepared calculator demo and the UI's **Simulate Demo Run** option. Simulation is the most repeatable presentation path because it requires no API key, but it is a scripted walkthrough; call that out clearly rather than presenting it as a live model decision.

## 0:00–0:20 — Frame the problem

Show the FAULTLINE UI with **Prepared Demo (2 Bugs)** selected.

Say: “FAULTLINE is a constrained Python debugging agent. It receives a bug report and a repository, then can inspect files, run the repository’s unittest suite, and edit only implementation Python files. Before every edit it saves a backup.”

## 0:20–0:45 — Establish the failing behavior

Click **Run Tests Now**. Point to the test output and then show `demo_repo/test_calculator.py` in the code viewer.

Say: “The test contract is clear: discounted items are taxed after discount, and `average([])` returns `0.0`. The repository is deliberately seeded with two failures.”

Do not state a particular terminal transcript or count of failures unless the displayed test output shows it.

## 0:45–1:50 — Show the debugging workflow

Click **Simulate Demo Run** and follow the timeline:

1. `inspect_repo` lists the available calculator and test files.
2. `run_tests` captures the failing baseline.
3. `inspect_repo` reads `calculator.py`.
4. `edit_file` replaces that implementation and records a `.faultline_backups` copy.
5. `run_tests` is invoked again for verification.

Say: “The visible trace makes each action reviewable. The tool layer resolves paths under the selected repository, tests are protected from edits, and the test runner is restricted to unittest discovery.”

When the diff is available, open **File Diff / Changes**.

Say: “The diff compares the working calculator against the latest safety backup. The intended patch taxes the discounted price and returns zero for an empty list.”

## 1:50–2:20 — Verification and honest scope

Show the final test result and final report only as they appear in the UI.

Say: “Verification is test-driven: FAULTLINE reports success only after the configured unittest command returns success. The UI also supports a live Groq-backed run, where the model dynamically selects from the same three tools. The simulation we just ran is a deterministic demo flow, not live model reasoning.”

Optional closing: click **Reset Demo** only after the audience has seen the diff, explaining that it restores the intentionally buggy `calculator.py` for another demonstration.

## Live-run alternative

With a configured `GROQ_API_KEY`, use **Start Autonomous Agent** or run `python main.py --demo`. The live agent has the same maximum step limit and tools, but its exact sequence and wording are model-generated. For that reason, do not promise a fixed number of steps or a successful repair in a live demo.
