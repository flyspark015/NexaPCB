# CLI Reference

NexaPCB is a CLI-only export/reporting tool. It does not autoroute and it does not make a board production-ready automatically.

All commands can be discovered with:

```bash
nexapcb --help
```

Most machine-facing commands support:
- `--format json`
- stable JSON envelope output
- meaningful nonzero exit codes on failure

## Common command behavior

JSON commands return:

```json
{
  "ok": true,
  "command": "check all",
  "status": "OK",
  "data": {},
  "issues": [],
  "reports": {},
  "next_action": "..."
}
```

Failures return:

```json
{
  "ok": false,
  "command": "export",
  "status": "FAILED",
  "error": {
    "code": "XML_NOT_FOUND",
    "message": "...",
    "likely_cause": "...",
    "suggested_fix": "..."
  },
  "issues": []
}
```

---

## `nexapcb --help`

Purpose:
- show the full top-level command surface

Expected output:
- top-level commands and short usage

Exit behavior:
- `0`

---

## `nexapcb doctor`

Purpose:
- verify local system readiness

Syntax:

```bash
nexapcb doctor
nexapcb doctor --output /tmp/nexapcb_doctor
nexapcb doctor --source path/to/main.py --output /tmp/nexapcb_doctor
nexapcb doctor --format json
```

Checks:
- Python version
- platform
- SKiDL availability/version
- KiCad CLI availability/version
- JLC2KiCadLib availability/version
- output folder writeability
- source existence when provided

Reports:
- `doctor_report.json`
- `doctor_report.md`

Exit behavior:
- `0` if usable
- nonzero on hard failure

---

## `nexapcb version`

Purpose:
- print tool/runtime metadata

Syntax:

```bash
nexapcb version
nexapcb version --json
```

Data includes:
- NexaPCB version
- Python version
- platform
- SKiDL version
- KiCad CLI path/version if found
- JLC2KiCadLib availability/version

Exit behavior:
- `0`

---

## `nexapcb explain`

Purpose:
- explain an error code

Syntax:

```bash
nexapcb explain --list
nexapcb explain PIN_PAD_MISMATCH
```

Output includes:
- code
- meaning
- likely cause
- suggested fix
- examples where useful

Exit behavior:
- `0` for known code
- nonzero for unknown code in strict script use

---

## `nexapcb init`

Purpose:
- create a modular SKiDL project template

Syntax:

```bash
nexapcb init --project-root /path/to/project --project-name my_board
```

Creates:
- `skidl_project/`
- `custom_assets/`
- `nexapcb.toml`

Exit behavior:
- `0` on success

---

## `nexapcb check`

Purpose:
- validate source before export

Subcommands:
- `source`
- `syntax`
- `imports`
- `skidl`
- `assets`
- `paths`
- `all`

Examples:

```bash
nexapcb check source --source path/to/main.py --format json
nexapcb check imports --project-root path/to/project --entry skidl_project/main.py
nexapcb check all --source path/to/main.py --output /tmp/out --format json
```

Reports:
- `check_source_report.json/.md`
- `check_syntax_report.json/.md`
- `check_imports_report.json/.md`
- `check_skidl_report.json/.md`
- `check_assets_report.json/.md`
- `check_paths_report.json/.md`
- `check_report.json/.md`

Exit behavior:
- `0` on pass
- `2` on check failure

---

## `nexapcb stage`

Purpose:
- run one export pipeline stage at a time

Subcommands:
- `ast`
- `skidl-export`
- `netlist-parse`
- `jlc-import`
- `custom-assets`
- `kicad-generate`
- `symbol-rewrite`
- `validate`
- `all`

Examples:

```bash
nexapcb stage ast --source path/to/main.py --output /tmp/out --format json
nexapcb stage skidl-export --source path/to/main.py --project-name my_board --output /tmp/out
nexapcb stage jlc-import --output /tmp/out
nexapcb stage custom-assets --source path/to/main.py --output /tmp/out --custom-assets custom_assets.json
nexapcb stage kicad-generate --project-name my_board --output /tmp/out
nexapcb stage symbol-rewrite --project-name my_board --output /tmp/out
nexapcb stage validate --project-name my_board --output /tmp/out
```

Reports:
- `ast_parse_report.json`
- `skidl_export_report.json`
- `netlist_report.json/.md`
- `jlc_import_report.json/.md`
- `custom_asset_report.json/.md`
- `kicad_generation_report.json/.md`
- `schematic_symbol_rewrite_report.json/.md`
- `validation_report.json/.md`

Exit behavior:
- `0` on success
- nonzero on stage failure or missing prerequisite

---

## `nexapcb export`

Purpose:
- run the full pipeline from source to KiCad and reports

Syntax:

```bash
nexapcb export --source path/to/main.py --project-name my_board --output /tmp/out
nexapcb export --project-root path/to/project --entry skidl_project/main.py --project-name my_board --output /tmp/out
```

Important options:
- `--custom-assets`
- `--pin-map`
- `--allow-generic-fallback`
- `--strict`
- `--allow-issues`

Reports:
- full `reports/` bundle including `final_result.json`

Exit behavior:
- `0` on successful export
- nonzero on export failure
- in `--strict` mode returns nonzero if reported issues remain

---

## `nexapcb report`

Purpose:
- print one normalized report or the whole bundle

Subcommands:
- `summary`
- `components`
- `connections`
- `issues`
- `validation`
- `erc`
- `drc`
- `unconnected`
- `routing`
- `board-connectivity`
- `pin-pad`
- `assets`
- `final`
- `all`

Examples:

```bash
nexapcb report final --output /tmp/out --format json
nexapcb report issues --output /tmp/out --severity error --format json
nexapcb report all --output /tmp/out --format json
```

Filters:
- `--severity`
- `--code`
- `--ref`
- `--net`

Exit behavior:
- `0`

---

## `nexapcb inspect`

Purpose:
- query a source tree or generated project without printing all reports

Subcommands:
- `source`
- `output`
- `symbols`
- `footprints`
- `models`
- `nets`
- `refs`
- `paths`

Examples:

```bash
nexapcb inspect source --source path/to/main.py --format json
nexapcb inspect output --output /tmp/out --format json
nexapcb inspect nets --output /tmp/out --net SYS_3V3 --format json
nexapcb inspect refs --output /tmp/out --ref U7 --format json
```

Exit behavior:
- `0`

---

## `nexapcb erc`

Purpose:
- run, parse, or print schematic ERC

Subcommands:
- `run`
- `parse`
- `report`

Examples:

```bash
nexapcb erc run --output /tmp/out
nexapcb erc parse --output /tmp/out --input /tmp/out/reports/final_erc.json
nexapcb erc report --output /tmp/out --format json
```

Reports:
- `erc_report.json/.md`

Exit behavior:
- nonzero on missing KiCad CLI unless `--allow-errors`
- nonzero on ERC violations only when configured to fail

---

## `nexapcb drc`

Purpose:
- run, parse, or print PCB DRC

Subcommands:
- `run`
- `parse`
- `report`

Examples:

```bash
nexapcb drc run --output /tmp/out
nexapcb drc parse --output /tmp/out --input /tmp/out/reports/final_drc.json
nexapcb drc report --output /tmp/out --format json
```

Reports:
- `drc_report.json/.md`

Exit behavior:
- nonzero on missing KiCad CLI unless `--allow-errors`
- nonzero on DRC violations only when configured to fail

---

## `nexapcb part`

Purpose:
- study a part before wiring it in SKiDL

Subcommands:
- `lookup`
- `inspect`
- `compare`
- `request`
- `report`
- `pins`
- `pads`
- `skidl-snippet`
- `model-check`

Examples:

```bash
nexapcb part lookup --sku C25804 --output /tmp/part_c25804
nexapcb part inspect --symbol part.kicad_sym --symbol-name MY_PART --footprint part.kicad_mod --output /tmp/part_study
nexapcb part compare --symbol part.kicad_sym --symbol-name MY_PART --footprint part.kicad_mod --output /tmp/part_compare
nexapcb part request --sku C25804 --output /tmp/part_req
nexapcb part pins --symbol part.kicad_sym --symbol-name MY_PART --format json
nexapcb part pads --footprint part.kicad_mod --format json
nexapcb part skidl-snippet --input /tmp/part_compare --format json
nexapcb part model-check --footprint part.kicad_mod --model part.step --format json
nexapcb part report --input /tmp/part_compare --format json
```

Reports:
- `part_summary_report.json/.md`
- `symbol_pin_report.json/.md`
- `footprint_pad_report.json/.md`
- `pin_pad_compare_report.json/.md`
- `model_report.json/.md`
- `skidl_usage_report.json/.md`

Exit behavior:
- `0` on successful inspection
- nonzero on missing symbol/footprint/model or hard mismatch conditions

---

## `nexapcb asset`

Purpose:
- work with symbols, footprints, and models separately from the main export

Subcommands:
- `scan`
- `localize`
- `check-paths`
- `report`

Examples:

```bash
nexapcb asset scan --source path/to/main.py --format json
nexapcb asset localize --source path/to/main.py --output /tmp/out --custom-assets custom_assets.json
nexapcb asset check-paths --output /tmp/out --format json
nexapcb asset report --output /tmp/out --format json
```

Reports:
- `asset_report.json/.md`
- `custom_asset_report.json/.md`

---

## `nexapcb net`

Purpose:
- query connectivity by net

Subcommands:
- `list`
- `show`
- `critical`
- `single-node`
- `unconnected`

Examples:

```bash
nexapcb net list --output /tmp/out --format json
nexapcb net show --output /tmp/out --net SYS_3V3 --format json
nexapcb net critical --output /tmp/out --format json
```

---

## `nexapcb ref`

Purpose:
- query a single component/reference

Subcommands:
- `list`
- `show`
- `pins`
- `pads`
- `nets`
- `issues`

Examples:

```bash
nexapcb ref list --output /tmp/out --format json
nexapcb ref show --output /tmp/out --ref U7 --format json
nexapcb ref issues --output /tmp/out --ref U7 --format json
```

---

## `nexapcb issue`

Purpose:
- query normalized issue objects

Subcommands:
- `list`
- `show`
- `by-ref`
- `by-net`
- `by-code`
- `explain`

Examples:

```bash
nexapcb issue list --output /tmp/out --severity error --format json
nexapcb issue by-ref --output /tmp/out --ref U7 --format json
nexapcb issue by-code --output /tmp/out --code PIN_PAD_MISMATCH --format json
nexapcb issue explain --code ABSOLUTE_PATH_FOUND --format json
```

---

## `nexapcb examples`

Purpose:
- list built-in examples or create one on disk

Examples:

```bash
nexapcb examples
nexapcb examples --create rc_filter --output /tmp/rc_filter_example
```

---

## `nexapcb help`

Purpose:
- show long-form topical help

Topics:
- `commands`
- `skidl-format`
- `modular-projects`
- `custom-parts`
- `sku`
- `reports`
- `errors`
- `ai-loop`
- `part-request`
- `examples`

Examples:

```bash
nexapcb help commands
nexapcb help modular-projects
nexapcb help reports
```
