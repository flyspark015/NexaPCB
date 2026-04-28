# ✅ NexaPCB QA Test Plan
> Release-oriented QA guidance from basic CLI health to complex stress-test reporting.

[!IMPORTANT]
The QA goal is **tool reliability**, not proof that any example board is manufacturing-ready. NexaPCB is **not an autorouter**.

## 🧭 Overview

Fresh QA outputs are written to:

```text
/tmp/nexapcb_qa/
```

Summary artifacts:

- `/tmp/nexapcb_qa/qa_summary.json`
- `/tmp/nexapcb_qa/qa_summary.md`

Main script:

```bash
./tests/run_full_qa.sh
```

## 📊 QA Levels

| Level | Scope | Goal |
|---|---|---|
| 1 | Basic CLI health | Verify help, doctor, version, explain |
| 2 | One-file project | Verify full pipeline on smallest happy-path example |
| 3 | Modular project | Verify multi-file imports and export flow |
| 4 | Custom part demo | Verify custom asset localization and part inspection |
| 5 | Part request system | Verify part-study workflow before SKiDL wiring |
| 6 | Negative tests | Verify structured, actionable failures |
| 7 | ERC/DRC reporting | Verify KiCad CLI integrations and report parsing |
| 8 | Stress test | Verify report usefulness on a complex project |

## 🚀 Level 1 — Basic CLI Health

Run:

```bash
.venv/bin/python -m nexapcb.cli --help
.venv/bin/python -m nexapcb.cli help commands
.venv/bin/python -m nexapcb.cli doctor --format json
.venv/bin/python -m nexapcb.cli version --json
.venv/bin/python -m nexapcb.cli explain --list
.venv/bin/python -m nexapcb.cli explain PIN_PAD_MISMATCH
```

Pass criteria:

- no command crashes
- help is readable
- JSON outputs are valid

## 🧩 Level 2 — Basic One-File Project

Fixture:

```text
tests/fixtures/rc_filter/main.py
```

Run:

```bash
.venv/bin/python -m nexapcb.cli check all --source tests/fixtures/rc_filter/main.py --output /tmp/nexapcb_qa/rc_filter --format json
.venv/bin/python -m nexapcb.cli stage ast --source tests/fixtures/rc_filter/main.py --output /tmp/nexapcb_qa/rc_filter --format json
.venv/bin/python -m nexapcb.cli stage skidl-export --source tests/fixtures/rc_filter/main.py --project-name rc_filter --output /tmp/nexapcb_qa/rc_filter --format json
.venv/bin/python -m nexapcb.cli stage netlist-parse --project-name rc_filter --output /tmp/nexapcb_qa/rc_filter --format json
.venv/bin/python -m nexapcb.cli stage jlc-import --source tests/fixtures/rc_filter/main.py --output /tmp/nexapcb_qa/rc_filter --format json
.venv/bin/python -m nexapcb.cli stage custom-assets --source tests/fixtures/rc_filter/main.py --output /tmp/nexapcb_qa/rc_filter --format json
.venv/bin/python -m nexapcb.cli stage kicad-generate --project-name rc_filter --output /tmp/nexapcb_qa/rc_filter --format json
.venv/bin/python -m nexapcb.cli stage symbol-rewrite --project-name rc_filter --output /tmp/nexapcb_qa/rc_filter --format json
.venv/bin/python -m nexapcb.cli stage validate --project-name rc_filter --output /tmp/nexapcb_qa/rc_filter --format json
.venv/bin/python -m nexapcb.cli export --source tests/fixtures/rc_filter/main.py --project-name rc_filter --output /tmp/nexapcb_qa/rc_filter --allow-issues
.venv/bin/python -m nexapcb.cli report all --output /tmp/nexapcb_qa/rc_filter --format json
.venv/bin/python -m nexapcb.cli inspect output --output /tmp/nexapcb_qa/rc_filter --format json
.venv/bin/python -m nexapcb.cli net list --output /tmp/nexapcb_qa/rc_filter --format json
.venv/bin/python -m nexapcb.cli ref list --output /tmp/nexapcb_qa/rc_filter --format json
.venv/bin/python -m nexapcb.cli issue list --output /tmp/nexapcb_qa/rc_filter --format json
```

Verify:

- `.kicad_pro` exists
- `.kicad_sch` exists
- `.kicad_pcb` exists
- reports exist
- `final_result.json` exists
- JSON outputs parse cleanly

## 🧱 Level 3 — Modular Multi-File Project

Fixture:

```text
tests/fixtures/modular_esp32/
```

Run:

```bash
.venv/bin/python -m nexapcb.cli check imports --project-root tests/fixtures/modular_esp32 --entry skidl_project/main.py --format json
.venv/bin/python -m nexapcb.cli check all --project-root tests/fixtures/modular_esp32 --entry skidl_project/main.py --output /tmp/nexapcb_qa/modular_esp32 --format json
.venv/bin/python -m nexapcb.cli export --project-root tests/fixtures/modular_esp32 --entry skidl_project/main.py --project-name modular_esp32 --output /tmp/nexapcb_qa/modular_esp32 --allow-issues
.venv/bin/python -m nexapcb.cli report all --output /tmp/nexapcb_qa/modular_esp32 --format json
```

Pass criteria:

- modular imports work
- no Python import crash
- final reports exist

## 🧰 Level 4 — Custom Part Demo

Fixture:

```text
tests/fixtures/custom_part_demo/
```

Run:

```bash
.venv/bin/python -m nexapcb.cli check assets --project-root tests/fixtures/custom_part_demo --entry skidl_project/main.py --format json
.venv/bin/python -m nexapcb.cli asset scan --source tests/fixtures/custom_part_demo/skidl_project/main.py --format json
.venv/bin/python -m nexapcb.cli asset localize --output /tmp/nexapcb_qa/custom_part_demo --custom-assets tests/fixtures/custom_part_demo/custom_assets.json --format json
.venv/bin/python -m nexapcb.cli part inspect --symbol tests/fixtures/custom_part_demo/custom_assets/symbols/custom_sensor.kicad_sym --symbol-name CUSTOM_SENSOR --footprint tests/fixtures/custom_part_demo/custom_assets/footprints/CUSTOM_SENSOR.kicad_mod --output /tmp/nexapcb_qa/custom_part_demo_part
.venv/bin/python -m nexapcb.cli part compare --symbol tests/fixtures/custom_part_demo/custom_assets/symbols/custom_sensor.kicad_sym --symbol-name CUSTOM_SENSOR --footprint tests/fixtures/custom_part_demo/custom_assets/footprints/CUSTOM_SENSOR.kicad_mod --output /tmp/nexapcb_qa/custom_part_demo_compare
.venv/bin/python -m nexapcb.cli export --project-root tests/fixtures/custom_part_demo --entry skidl_project/main.py --project-name custom_part_demo --output /tmp/nexapcb_qa/custom_part_demo --allow-issues
```

Verify:

- `custom_asset_report` exists
- part reports exist
- copied assets exist
- no absolute paths remain in KiCad artifacts

## 📦 Level 5 — Part Request System

Run:

```bash
.venv/bin/python -m nexapcb.cli part lookup --sku C25804 --output /tmp/nexapcb_qa/part_requests/part_c25804
.venv/bin/python -m nexapcb.cli part inspect --symbol tests/fixtures/custom_part_demo/custom_assets/symbols/custom_sensor.kicad_sym --symbol-name CUSTOM_SENSOR --footprint tests/fixtures/custom_part_demo/custom_assets/footprints/CUSTOM_SENSOR.kicad_mod --output /tmp/nexapcb_qa/part_requests/custom_sensor
.venv/bin/python -m nexapcb.cli part compare --symbol tests/fixtures/custom_part_demo/custom_assets/symbols/custom_sensor.kicad_sym --symbol-name CUSTOM_SENSOR --footprint tests/fixtures/custom_part_demo/custom_assets/footprints/CUSTOM_SENSOR.kicad_mod --output /tmp/nexapcb_qa/part_requests/custom_sensor_compare
.venv/bin/python -m nexapcb.cli part pins --symbol tests/fixtures/custom_part_demo/custom_assets/symbols/custom_sensor.kicad_sym --symbol-name CUSTOM_SENSOR --format json
.venv/bin/python -m nexapcb.cli part pads --footprint tests/fixtures/custom_part_demo/custom_assets/footprints/CUSTOM_SENSOR.kicad_mod --format json
.venv/bin/python -m nexapcb.cli part skidl-snippet --input /tmp/nexapcb_qa/part_requests/custom_sensor --ref U1
.venv/bin/python -m nexapcb.cli part report --input /tmp/nexapcb_qa/part_requests/custom_sensor --format json
```

If JLC import/network is unavailable:

- mark lookup as `SKIPPED_JLC_LOOKUP`
- do **not** fail the whole QA run if all local part-study features still work

## 🧪 Level 6 — Negative Tests

Fixtures:

- `tests/fixtures/bad_unconnected_pins/`
- `tests/fixtures/bad_pin_pad_mismatch/`
- `tests/fixtures/bad_missing_custom_asset/`

Run the relevant `check`, `export`, and `report` commands.

Expected behavior:

- command may fail
- failure must be structured
- `issue_report.json` must exist when applicable
- error code must be useful
- `suggested_fix` must be present
- no raw Python traceback unless `--debug` is explicitly enabled

## 📏 Level 7 — ERC/DRC Reporting

If KiCad CLI exists:

```bash
.venv/bin/python -m nexapcb.cli erc run --output /tmp/nexapcb_qa/rc_filter
.venv/bin/python -m nexapcb.cli erc parse --output /tmp/nexapcb_qa/rc_filter --input /tmp/nexapcb_qa/rc_filter/reports/final_erc.json
.venv/bin/python -m nexapcb.cli erc report --output /tmp/nexapcb_qa/rc_filter --format json
.venv/bin/python -m nexapcb.cli drc run --output /tmp/nexapcb_qa/rc_filter
.venv/bin/python -m nexapcb.cli drc parse --output /tmp/nexapcb_qa/rc_filter --input /tmp/nexapcb_qa/rc_filter/reports/final_drc.json
.venv/bin/python -m nexapcb.cli drc report --output /tmp/nexapcb_qa/rc_filter --format json
```

If KiCad CLI does not exist:

- commands should return `KICAD_CLI_NOT_FOUND`
- docs must explain how to install or pass `--kicad-cli`

## ⚡ Level 8 — Stress Test

Use N-Defender only as a stress test.

Run:

```bash
.venv/bin/python -m nexapcb.cli check --source /Users/surajbhati/Desktop/temp/pcb/neha/nexapcb_fresh_skidl/n_defender_clean.py --format json
.venv/bin/python -m nexapcb.cli export --source /Users/surajbhati/Desktop/temp/pcb/neha/nexapcb_fresh_skidl/n_defender_clean.py --project-name n_defender_clean --output /tmp/nexapcb_qa/n_defender_stress --allow-issues
.venv/bin/python -m nexapcb.cli report all --output /tmp/nexapcb_qa/n_defender_stress --format json
```

Do **not** use this level as proof that the board is finished or routed.

## 📄 QA Output

The QA script must generate:

- `/tmp/nexapcb_qa/qa_summary.json`
- `/tmp/nexapcb_qa/qa_summary.md`

The summary should include:

- total tests
- passed
- failed
- skipped
- command list
- output paths
- failure details
- GitHub readiness recommendation

## ✅ Release Checklist

- CLI help works
- doctor/version/explain work
- one-file export works
- modular import/export works
- custom asset workflow works
- part-study workflow works
- negative fixtures fail clearly
- ERC/DRC reporting works or reports `KICAD_CLI_NOT_FOUND`
- stress-test reports are complete and actionable

## ⚠️ Common mistakes

| Mistake | Why it is wrong | Better approach |
|---|---|---|
| Using stale output folders | Hides regressions | Always use fresh `/tmp/nexapcb_qa/...` outputs |
| Treating stress-test design issues as tool failures | Confuses board quality with tool quality | Validate report completeness, not board perfection |
| Ignoring `qa_summary.json` | Misses failure aggregation | Read it first after running QA |

## 🔗 Related docs

- [CLI Reference](./CLI_REFERENCE.md)
- [Reports](./REPORTS.md)
- [AI Agent Workflow](./AI_AGENT_WORKFLOW.md)
- [Examples](./EXAMPLES.md)
