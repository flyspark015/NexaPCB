# 🧰 CLI Reference
> Complete command reference for NexaPCB’s CLI-only export, inspection, and reporting workflow.

> [!NOTE]
> NexaPCB is an **export/reporting tool**. It is **not** an autorouter and does **not** make a PCB production-ready automatically.

## 🧭 Overview

### Most-used commands

| Command | Purpose |
|---|---|
| `nexapcb doctor` | Check local environment readiness |
| `nexapcb check all` | Validate a SKiDL project before export |
| `nexapcb export` | Run the full SKiDL → KiCad pipeline |
| `nexapcb report all --format json` | Get the full machine-readable report bundle |
| `nexapcb part inspect` | Study a part before wiring |
| `nexapcb issue list` | Query normalized issues |

### Command groups

| Group | Commands | Purpose |
|---|---|---|
| Core | `doctor`, `version`, `explain`, `help` | Tool discovery and diagnostics |
| Project | `init`, `check`, `stage`, `export` | Build and validate projects |
| Reports | `report`, `inspect`, `issue` | Read structured output |
| Analysis | `erc`, `drc`, `net`, `ref` | Focused design/problem queries |
| Parts & assets | `part`, `asset` | Pre-wiring inspection and localization |
| Examples | `examples` | Create learning fixtures |

## 🚀 Common syntax

```bash
.venv/bin/python -m nexapcb.cli <command> [subcommand] [options]
```

JSON-producing commands return a stable envelope:

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

## 🛠 Core commands

### `nexapcb --help`
- **Purpose:** show the top-level CLI
- **Example:**
  ```bash
  .venv/bin/python -m nexapcb.cli --help
  ```
- **Exit:** `0`

### `nexapcb doctor`
- **Purpose:** verify local system readiness
- **Syntax:**
  ```bash
  .venv/bin/python -m nexapcb.cli doctor
  .venv/bin/python -m nexapcb.cli doctor --output /tmp/nexapcb_doctor
  .venv/bin/python -m nexapcb.cli doctor --source path/to/main.py --format json
  ```
- **Checks:** Python, platform, SKiDL, KiCad CLI, JLC importer, output writability, source existence
- **Reports:** `doctor_report.json`, `doctor_report.md`
- **Exit:** `0` on usable environment; nonzero on hard failure

### `nexapcb version`
- **Purpose:** print stable machine-readable version/runtime info
- **Syntax:**
  ```bash
  .venv/bin/python -m nexapcb.cli version
  .venv/bin/python -m nexapcb.cli version --json
  ```
- **Exit:** `0`

### `nexapcb explain`
- **Purpose:** explain a normalized error code
- **Syntax:**
  ```bash
  .venv/bin/python -m nexapcb.cli explain --list
  .venv/bin/python -m nexapcb.cli explain PIN_PAD_MISMATCH
  ```
- **Related help topics:**
  ```bash
  .venv/bin/python -m nexapcb.cli help sku
  .venv/bin/python -m nexapcb.cli help part-request
  ```

### `nexapcb init`
- **Purpose:** scaffold a modular SKiDL project
- **Syntax:**
  ```bash
  .venv/bin/python -m nexapcb.cli init --project-root /path/to/project --project-name my_board
  ```
- **Creates:** `skidl_project/`, `custom_assets/`, `nexapcb.toml`

## ✅ `nexapcb check`

### Subcommands
- `source`
- `syntax`
- `imports`
- `skidl`
- `assets`
- `paths`
- `all`

### Examples

```bash
.venv/bin/python -m nexapcb.cli check source --source path/to/main.py --format json
.venv/bin/python -m nexapcb.cli check imports --project-root path/to/project --entry skidl_project/main.py
.venv/bin/python -m nexapcb.cli check all --source path/to/main.py --output /tmp/out --format json
```

### Reports written
- `check_source_report.json/.md`
- `check_syntax_report.json/.md`
- `check_imports_report.json/.md`
- `check_skidl_report.json/.md`
- `check_assets_report.json/.md`
- `check_paths_report.json/.md`
- `check_report.json/.md`

### Exit behavior
- `0` on pass
- `2` on check failure

## 🧪 `nexapcb stage`

### Subcommands
- `ast`
- `skidl-export`
- `netlist-parse`
- `jlc-import`
- `custom-assets`
- `kicad-generate`
- `symbol-rewrite`
- `validate`
- `all`

### Examples

```bash
.venv/bin/python -m nexapcb.cli stage ast --source path/to/main.py --output /tmp/out --format json
.venv/bin/python -m nexapcb.cli stage skidl-export --source path/to/main.py --project-name my_board --output /tmp/out
.venv/bin/python -m nexapcb.cli stage jlc-import --output /tmp/out
.venv/bin/python -m nexapcb.cli stage custom-assets --source path/to/main.py --output /tmp/out --custom-assets custom_assets.json
.venv/bin/python -m nexapcb.cli stage kicad-generate --project-name my_board --output /tmp/out
.venv/bin/python -m nexapcb.cli stage symbol-rewrite --project-name my_board --output /tmp/out
.venv/bin/python -m nexapcb.cli stage validate --project-name my_board --output /tmp/out
```

### Stage reports
- `ast_parse_report.json`
- `skidl_export_report.json`
- `netlist_report.json/.md`
- `jlc_import_report.json/.md`
- `custom_asset_report.json/.md`
- `kicad_generation_report.json/.md`
- `schematic_symbol_rewrite_report.json/.md`
- `validation_report.json/.md`

### Exit behavior
- `0` on stage success
- nonzero on missing prerequisite or stage failure

## 🚀 `nexapcb export`

- **Purpose:** run the full pipeline from source to KiCad + reports
- **Syntax:**
  ```bash
  .venv/bin/python -m nexapcb.cli export \
    --source path/to/main.py \
    --project-name my_board \
    --output /tmp/out

  .venv/bin/python -m nexapcb.cli export \
    --project-root path/to/project \
    --entry skidl_project/main.py \
    --project-name my_board \
    --output /tmp/out
  ```
- **Important options:** `--custom-assets`, `--pin-map`, `--strict`, `--allow-issues`
- **Reports:** full `reports/` bundle including `final_result.json`
- **Exit:** `0` on successful export; nonzero on export failure; in `--strict` mode, nonzero if issue thresholds are exceeded

## 📊 `nexapcb report`

### Subcommands
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

### Examples

```bash
.venv/bin/python -m nexapcb.cli report final --output /tmp/out --format json
.venv/bin/python -m nexapcb.cli report issues --output /tmp/out --severity error --format json
.venv/bin/python -m nexapcb.cli report all --output /tmp/out --format json
```

### Filters
- `--severity`
- `--code`
- `--ref`
- `--net`
- `--save`

### Formats
- `--format json`
- `--format md`
- `--format text`

## 🔎 `nexapcb inspect`

### Subcommands
- `source`
- `output`
- `symbols`
- `footprints`
- `models`
- `nets`
- `refs`
- `paths`

### Examples

```bash
.venv/bin/python -m nexapcb.cli inspect source --source path/to/main.py --format json
.venv/bin/python -m nexapcb.cli inspect output --output /tmp/out --format json
.venv/bin/python -m nexapcb.cli inspect nets --output /tmp/out --net SYS_3V3 --format json
.venv/bin/python -m nexapcb.cli inspect refs --output /tmp/out --ref U7 --format json
```

## ⚠️ `nexapcb erc`

### Subcommands
- `run`
- `parse`
- `report`

### Examples

```bash
.venv/bin/python -m nexapcb.cli erc run --output /tmp/out
.venv/bin/python -m nexapcb.cli erc parse --output /tmp/out --input /tmp/out/reports/final_erc.json
.venv/bin/python -m nexapcb.cli erc report --output /tmp/out --format json
```

### Reports
- `erc_report.json/.md`

### Exit
- nonzero on missing KiCad CLI unless allowed
- nonzero on violations only when configured to fail

## 📐 `nexapcb drc`

### Subcommands
- `run`
- `parse`
- `report`

### Examples

```bash
.venv/bin/python -m nexapcb.cli drc run --output /tmp/out
.venv/bin/python -m nexapcb.cli drc parse --output /tmp/out --input /tmp/out/reports/final_drc.json
.venv/bin/python -m nexapcb.cli drc report --output /tmp/out --format json
```

### Reports
- `drc_report.json/.md`

## 🧠 `nexapcb part`

### Subcommands
- `lookup`
- `inspect`
- `compare`
- `request`
- `report`
- `pins`
- `pads`
- `skidl-snippet`
- `model-check`

### Examples

```bash
.venv/bin/python -m nexapcb.cli part lookup --sku C25804 --output /tmp/part_c25804
.venv/bin/python -m nexapcb.cli part inspect --symbol part.kicad_sym --symbol-name MY_PART --footprint part.kicad_mod --output /tmp/part_study
.venv/bin/python -m nexapcb.cli part compare --symbol part.kicad_sym --symbol-name MY_PART --footprint part.kicad_mod --output /tmp/part_compare
.venv/bin/python -m nexapcb.cli part request --sku C25804 --output /tmp/part_req
.venv/bin/python -m nexapcb.cli part pins --symbol part.kicad_sym --symbol-name MY_PART --format json
.venv/bin/python -m nexapcb.cli part pads --footprint part.kicad_mod --format json
.venv/bin/python -m nexapcb.cli part skidl-snippet --input /tmp/part_compare --format json
.venv/bin/python -m nexapcb.cli part model-check --footprint part.kicad_mod --model part.step --format json
.venv/bin/python -m nexapcb.cli part report --input /tmp/part_compare --format json
```

### Reports
- `part_summary_report.json/.md`
- `symbol_pin_report.json/.md`
- `footprint_pad_report.json/.md`
- `pin_pad_compare_report.json/.md`
- `model_report.json/.md`
- `skidl_usage_report.json/.md`

> [!IMPORTANT]
> Use `part inspect` / `compare` before wiring complex parts in SKiDL.
> Do not guess pin labels. Use the labels the symbol actually exposes.

## 📦 `nexapcb asset`

### Subcommands
- `scan`
- `localize`
- `check-paths`
- `report`

### Examples

```bash
.venv/bin/python -m nexapcb.cli asset scan --source path/to/main.py --format json
.venv/bin/python -m nexapcb.cli asset localize --source path/to/main.py --output /tmp/out --custom-assets custom_assets.json
.venv/bin/python -m nexapcb.cli asset check-paths --output /tmp/out --format json
.venv/bin/python -m nexapcb.cli asset report --output /tmp/out --format json
```

## 🔌 `nexapcb net`

### Subcommands
- `list`
- `show`
- `critical`
- `single-node`
- `unconnected`

### Examples

```bash
.venv/bin/python -m nexapcb.cli net list --output /tmp/out --format json
.venv/bin/python -m nexapcb.cli net show --output /tmp/out --net SYS_3V3 --format json
.venv/bin/python -m nexapcb.cli net critical --output /tmp/out --format json
```

## 🧷 `nexapcb ref`

### Subcommands
- `list`
- `show`
- `pins`
- `pads`
- `nets`
- `issues`

### Examples

```bash
.venv/bin/python -m nexapcb.cli ref list --output /tmp/out --format json
.venv/bin/python -m nexapcb.cli ref show --output /tmp/out --ref U7 --format json
.venv/bin/python -m nexapcb.cli ref issues --output /tmp/out --ref U7 --format json
```

## 🚨 `nexapcb issue`

### Subcommands
- `list`
- `show`
- `by-ref`
- `by-net`
- `by-code`
- `explain`

### Examples

```bash
.venv/bin/python -m nexapcb.cli issue list --output /tmp/out --severity error --format json
.venv/bin/python -m nexapcb.cli issue by-ref --output /tmp/out --ref U7 --format json
.venv/bin/python -m nexapcb.cli issue by-code --output /tmp/out --code PIN_PAD_MISMATCH --format json
.venv/bin/python -m nexapcb.cli issue explain --code ABSOLUTE_PATH_FOUND --format json
```

## 🧪 `nexapcb examples`

- **Purpose:** list built-in examples or create one on disk
- **Examples:**
  ```bash
  .venv/bin/python -m nexapcb.cli examples
  .venv/bin/python -m nexapcb.cli examples --create rc_filter --output /tmp/rc_filter_example
  ```

## 🆘 `nexapcb help`

### Topics
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

### Examples

```bash
.venv/bin/python -m nexapcb.cli help commands
.venv/bin/python -m nexapcb.cli help modular-projects
.venv/bin/python -m nexapcb.cli help reports
```

## ✅ Checklist

- [ ] Use `doctor` before debugging environment problems
- [ ] Use `check all` before export
- [ ] Use `part inspect` / `part compare` before wiring complex parts
- [ ] Read `final_result.json` first after export
- [ ] Use focused commands (`issue`, `net`, `ref`) instead of scanning giant logs

## 🔗 Related docs

- [README.md](../README.md)
- [SKIDL_FORMAT_GUIDE.md](SKIDL_FORMAT_GUIDE.md)
- [CUSTOM_PARTS.md](CUSTOM_PARTS.md)
- [PART_REQUEST_SYSTEM.md](PART_REQUEST_SYSTEM.md)
- [REPORTS.md](REPORTS.md)
- [ERRORS.md](ERRORS.md)
