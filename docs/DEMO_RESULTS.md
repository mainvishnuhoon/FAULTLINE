# Prepared demo: intended behavior and workflow

## Scope and evidence

This document is based on the checked-in source in `demo_repo/`. It describes expected behavior encoded by the tests and the intentional defects in the implementation. No test command was run while preparing this documentation, so it does not claim an observed test transcript, exit code, or repair result.

## Intentional bugs

| Location | Intentional defect | Expected contract | Expected failing behavior before a fix |
| --- | --- | --- | --- |
| `demo_repo/calculator.py`: `calculate_total` | Tax is calculated as `price * tax_rate` before the discount. | `test_discount_is_applied_before_tax` expects `calculate_total(100, 20, 0.10)` to return `88.00`: 20% discount first, then 10% tax. | The implementation returns the discounted price plus tax on the original price, which differs from the asserted value. |
| `demo_repo/calculator.py`: `average` | It divides by `len(values)` with no empty-list branch. | `test_average_of_empty_list_is_zero` expects `average([])` to return `0.0`. | Calling it with an empty list attempts division by zero instead of returning `0.0`. |

`test_average_of_numbers` additionally establishes the normal case: `average([2, 4, 6])` is expected to equal `4`.

## Debugging workflow

1. Start in `demo_repo/` and inspect `calculator.py` plus `test_calculator.py`.
2. Run the repository's configured command: `python -m unittest discover -v`.
3. Compare the test contracts against `calculate_total` and `average`.
4. Make the smallest implementation-only correction:
   - calculate tax from `discounted_price`;
   - return `0.0` before dividing when the input list is empty.
5. Use the backup created by `DemoTools.edit_file` to inspect the change if needed.

The prepared UI simulation follows this same order programmatically in `User_Interface/app.py` (`AgentRunner._run_simulation`), but its edit content and sequence are pre-scripted for this calculator.

## Verification workflow

Run `python -m unittest discover -v` again from `demo_repo/` after the implementation-only change. The verification criterion used by FAULTLINE is the command's zero exit code, represented as `passed: true` by `DemoTools.run_tests`. The agent records that condition as `verification_passed`.

This repository's source specifies the intended post-fix behavior, but this document intentionally makes no assertion that a particular run has passed. To repeat the presentation baseline after an edit, the web and desktop UI reset controls overwrite `demo_repo/calculator.py` with their embedded buggy baseline.
