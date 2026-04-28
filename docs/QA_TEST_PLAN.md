# QA Test Plan

NexaPCB QA is organized from basic CLI health to complex stress-test reporting.

## Output root

Fresh QA runs write to:

```text
/tmp/nexapcb_qa/
```

Summary files:
- `/tmp/nexapcb_qa/qa_summary.json`
- `/tmp/nexapcb_qa/qa_summary.md`

## Level 1 — Basic CLI health

Run:
- `nexapcb --help`
- `nexapcb help commands`
- `nexapcb doctor --format json`
- `nexapcb version --json`
- `nexapcb explain --list`
- `nexapcb explain PIN_PAD_MISMATCH`

## Level 2 — Basic one-file project

Fixture:
- `tests/fixtures/rc_filter/main.py`

Run:
- `check all`
- all core `stage` commands
- `export`
- `report all --format json`
- `inspect output`
- `net list`
- `ref list`
- `issue list`

Verify:
- generated KiCad files exist
- reports exist
- `final_result.json` exists

## Level 3 — Modular multi-file project

Fixture:
- `tests/fixtures/modular_esp32/`

Verify:
- modular imports work
- no Python import crash
- reports generated

## Level 4 — Custom part demo

Fixture:
- `tests/fixtures/custom_part_demo/`

Verify:
- custom assets are detected/localized
- part inspect/compare works
- no absolute asset paths remain in KiCad artifacts

## Level 5 — Part request system

Verify:
- `part lookup`
- `part inspect`
- `part compare`
- `part pins`
- `part pads`
- `part skidl-snippet`
- `part report`

If network or JLC import is unavailable:
- mark lookup as skipped
- do not fail the entire QA run if the rest of the tool works

## Level 6 — Negative tests

Fixtures:
- `bad_unconnected_pins`
- `bad_pin_pad_mismatch`
- `bad_missing_custom_asset`

Goal:
- not to make them pass
- to ensure failures are structured and actionable

## Level 7 — ERC/DRC reporting

If KiCad CLI is available:
- run ERC/DRC commands
- verify normalized reports are generated

If KiCad CLI is missing:
- verify `KICAD_CLI_NOT_FOUND` is returned cleanly

## Level 8 — Stress test

Use N-Defender only as a stress-test of reporting and export robustness.

Do not use this level as proof the board is finished or routed.
