# ❌ NexaPCB Error Reference
> Searchable error-code reference for users, developers, and AI agents.

[!TIP]
Use the CLI for a fast explanation:

```bash
.venv/bin/python -m nexapcb.cli explain --list
.venv/bin/python -m nexapcb.cli explain PIN_PAD_MISMATCH
```

## 🧭 Overview

NexaPCB errors are designed to be:

- machine-readable
- stable enough for automation
- descriptive enough for humans
- actionable enough for AI repair loops

Each error should answer:

- **what failed**
- **why it probably failed**
- **what to do next**

## 📋 Error Table

| Code | Meaning | Likely Cause | Suggested Fix |
|---|---|---|---|
| `SOURCE_FILE_NOT_FOUND` | Source path missing | Wrong `--source` / `--entry` path | Fix the path and rerun |
| `PYTHON_SYNTAX_ERROR` | Python syntax invalid | Broken source file | Run `nexapcb check syntax` |
| `SKIDL_IMPORT_FAILED` | SKiDL or local imports failed | Missing module or broken import path | Run `nexapcb check imports` |
| `SKIDL_EXPORT_FAILED` | SKiDL did not produce XML/netlist | Runtime/export error | Verify `ERC()`, `generate_netlist()`, `generate_xml()` |
| `XML_NOT_FOUND` | Expected XML file missing | Export stage not run or failed | Run `nexapcb stage skidl-export` or `export` |
| `NETLIST_NOT_FOUND` | Expected `.net` file missing | Export stage not run or failed | Rerun export and verify outputs |
| `MISSING_PREREQUISITE_AST_REPORT` | Required AST report missing | Prior stage not run | Run `nexapcb stage ast` |
| `JLC2KICADLIB_NOT_FOUND` | Optional importer unavailable | Dependency not installed | Install importer or skip SKU import |
| `LCSC_SKU_IMPORT_FAILED` | LCSC/JLC-style import failed | Wrong SKU or importer failure | Verify SKU and inspect import report |
| `SKU_NOT_CONFIRMED` | No confirmed supplier/catalog SKU | SKU not researched yet | Confirm from supplier catalog before adding |
| `SKU_IMPORT_FAILED` | Supplier import failed | Wrong SKU, unsupported provider, or importer failure | Verify SKU/provider or use custom assets |
| `CUSTOM_SYMBOL_NOT_FOUND` | Custom symbol path missing | Wrong file path | Fix path or provide file |
| `CUSTOM_FOOTPRINT_NOT_FOUND` | Custom footprint path missing | Wrong file path | Fix path or provide file |
| `CUSTOM_MODEL_NOT_FOUND` | Custom model path missing | Wrong file path | Fix path or provide file |
| `PIN_PAD_MISMATCH` | Symbol pins and footprint pads do not align | Wrong symbol, footprint, or naming convention | Run `nexapcb part compare` |
| `PIN_LABEL_NOT_CONFIRMED` | SKiDL used a pin label not found in symbol | Guessed pin name | Run `nexapcb part pins` or `part report` |
| `FOOTPRINT_PAD_MISMATCH` | Footprint pad set incompatible with symbol | Wrong pad count or numbering | Choose a correct footprint or verified pin map |
| `ABSOLUTE_PATH_FOUND` | KiCad artifact contains absolute paths | Assets not localized/re-written | Localize assets and enforce `${KIPRJMOD}` |
| `KICAD_PROJECT_NOT_GENERATED` | Expected KiCad files missing | Generation stage failed | Inspect `kicad_generation_report.json` |
| `KICAD_CLI_NOT_FOUND` | KiCad CLI unavailable | KiCad not installed or not on path | Install KiCad or pass `--kicad-cli` |
| `ERC_FAILED` | ERC command failed to run | KiCad CLI execution error | Inspect raw command output |
| `ERC_VIOLATIONS_FOUND` | ERC completed with violations | Design or generation issue | Read `erc_report.json` |
| `DRC_FAILED` | DRC command failed to run | KiCad CLI execution error | Inspect raw command output |
| `DRC_VIOLATIONS_FOUND` | DRC completed with violations | Board geometry/placement/routing issue | Read `drc_report.json` |
| `UNCONNECTED_ITEMS_FOUND` | Board has unrouted/unconnected items | Normal first-pass board or real connectivity issue | Read `unconnected_report.json` |
| `NOT_IMPLEMENTED` | Command exists but logic is not implemented yet | Alpha/incomplete command path | Use the documented alternative command |

## 🛠 Detailed Explanations

### `SOURCE_FILE_NOT_FOUND`

**Meaning:** the file passed to `--source` or `--entry` does not exist.

**Likely cause:**

- typo in path
- wrong working directory assumption
- modular project entry path incorrect

**Suggested fix:**

```bash
.venv/bin/python -m nexapcb.cli check source --source path/to/main.py
```

---

### `PYTHON_SYNTAX_ERROR`

**Meaning:** Python could not parse the source before any SKiDL execution.

**Likely cause:**

- missing colon
- bad indentation
- invalid string or bracket syntax

**Suggested fix:**

```bash
.venv/bin/python -m nexapcb.cli check syntax --source path/to/main.py
```

---

### `SKIDL_IMPORT_FAILED`

**Meaning:** NexaPCB could not import SKiDL or project-local modules.

**Likely cause:**

- broken `import` statements
- modular project path not resolved
- missing dependency in the environment

**Suggested fix:**

```bash
.venv/bin/python -m nexapcb.cli check imports --project-root workspace/my_board --entry skidl_project/main.py
```

---

### `SKIDL_EXPORT_FAILED`

**Meaning:** source ran, but XML/netlist export failed.

**Likely cause:**

- runtime exception in SKiDL code
- `generate_netlist()` missing
- `generate_xml()` missing
- wrong output filename assumptions

**Suggested fix:**

- verify the source calls:

```python
ERC()
generate_netlist(file_="my_board.net")
generate_xml(file_="my_board.xml")
```

---

### `XML_NOT_FOUND`

**Meaning:** a later stage expected XML but it was not generated.

**Likely cause:**

- `stage skidl-export` not run
- export failed earlier
- XML generated with an unexpected name and not canonicalized

**Suggested fix:**

```bash
.venv/bin/python -m nexapcb.cli stage skidl-export --source path/to/main.py --project-name my_board --output out/my_board
```

---

### `NETLIST_NOT_FOUND`

**Meaning:** the KiCad netlist file is missing.

**Likely cause:**

- export did not complete
- `.net` filename mismatch
- output folder not writable

**Suggested fix:**

- rerun export
- inspect `skidl_export_report.json`

---

### `MISSING_PREREQUISITE_AST_REPORT`

**Meaning:** a stage was invoked without required prior metadata.

**Likely cause:**

- ran a mid-pipeline stage directly
- deleted `ast_parse_report.json`

**Suggested fix:**

```bash
.venv/bin/python -m nexapcb.cli stage ast --source path/to/main.py --output out/my_board
```

---

### `JLC2KICADLIB_NOT_FOUND`

**Meaning:** the optional JLC/EasyEDA import helper is not installed or not importable.

**Likely cause:**

- missing optional dependency
- environment mismatch

**Suggested fix:**

- install the required dependency
- or continue with manual/custom assets

[!NOTE]
This is a tooling/dependency problem, not an electrical design problem.

---

### `LCSC_SKU_IMPORT_FAILED`

**Meaning:** NexaPCB attempted a C-number style import and it failed.

**Likely cause:**

- wrong or stale SKU
- importer/network/provider problem

**Suggested fix:**

- verify the exact catalog entry
- inspect `jlc_import_report.json`
- use custom assets if needed

---

### `SKU_NOT_CONFIRMED`

**Meaning:** the design has no confirmed supplier/catalog reference for that part.

**Likely cause:**

- exact provider SKU not researched yet
- AI/user guessed the value but not the catalog entry

**Suggested fix:**

- search supplier catalog
- if unconfirmed, document it:

```python
part.fields["NO_SKU_REASON"] = "SKU not confirmed"
```

[!WARNING]
Do not guess supplier SKUs.

---

### `SKU_IMPORT_FAILED`

**Meaning:** import by supplier SKU failed.

**Likely cause:**

- unsupported provider
- wrong SKU
- missing importer dependency

**Suggested fix:**

- verify the provider and SKU
- use custom assets if import is unavailable

---

### `CUSTOM_SYMBOL_NOT_FOUND`
### `CUSTOM_FOOTPRINT_NOT_FOUND`
### `CUSTOM_MODEL_NOT_FOUND`

**Meaning:** a declared custom asset file does not exist.

**Likely cause:**

- wrong path
- file not checked into repo
- stale absolute path

**Suggested fix:**

- fix the path
- localize the asset into project assets
- verify with:

```bash
.venv/bin/python -m nexapcb.cli asset scan --source path/to/main.py --format json
```

---

### `PIN_PAD_MISMATCH`

**Meaning:** the symbol pins and footprint pads do not match well enough for safe use.

**Likely cause:**

- wrong symbol
- wrong footprint
- semantic pin labels vs numeric pads
- guessed SKiDL pin labels

**Suggested fix:**

```bash
.venv/bin/python -m nexapcb.cli part compare --symbol path/to/symbol.kicad_sym --symbol-name MY_PART --footprint path/to/footprint.kicad_mod --output /tmp/part_compare
```

Then read:

- `pin_pad_compare_report.json`
- `pin_pad_match_report.json`

---

### `PIN_LABEL_NOT_CONFIRMED`

**Meaning:** SKiDL used a pin label not present in the actual symbol.

**Likely cause:**

- guessed pin name from datasheet memory
- symbol naming differs from expectation

**Suggested fix:**

```bash
.venv/bin/python -m nexapcb.cli part pins --symbol path/to/symbol.kicad_sym --symbol-name MY_PART --format json
```

Use only confirmed labels from the report.

---

### `FOOTPRINT_PAD_MISMATCH`

**Meaning:** the footprint pad scheme is incompatible with the symbol pin scheme.

**Likely cause:**

- wrong package/footprint
- wrong connector variant
- symbol pads named semantically while footprint pads are numeric

**Suggested fix:**

- choose a matching footprint
- or use a verified mapping only if electrically correct

---

### `ABSOLUTE_PATH_FOUND`

**Meaning:** generated KiCad artifacts still contain absolute filesystem paths.

**Likely cause:**

- custom assets not localized
- model references not rewritten

**Suggested fix:**

- localize assets
- ensure final KiCad files use `${KIPRJMOD}`

---

### `KICAD_PROJECT_NOT_GENERATED`

**Meaning:** the exporter did not produce the expected KiCad project files.

**Likely cause:**

- generation stage failed
- missing XML/net prerequisites

**Suggested fix:**

- inspect `kicad_generation_report.json`
- verify XML and `.net` exist

---

### `KICAD_CLI_NOT_FOUND`

**Meaning:** KiCad CLI could not be located.

**Likely cause:**

- KiCad not installed
- nonstandard install path

**Suggested fix:**

- install KiCad
- or pass `--kicad-cli /path/to/kicad-cli`

---

### `ERC_FAILED` / `ERC_VIOLATIONS_FOUND`

**Meaning:** ERC failed to run, or ran and found issues.

**Likely cause:**

- KiCad CLI failure
- design-state schematic issues
- generation issues

**Suggested fix:**

- inspect `erc_report.json`
- use `issue_report.json` and `connection_report.json`

---

### `DRC_FAILED` / `DRC_VIOLATIONS_FOUND`

**Meaning:** DRC failed to run, or ran and found board issues.

**Likely cause:**

- KiCad CLI failure
- board outline/placement/routing issues

**Suggested fix:**

- inspect `drc_report.json`
- separate generator bugs from unrouted-board state with `board_connectivity_report.json`

---

### `UNCONNECTED_ITEMS_FOUND`

**Meaning:** the board contains unrouted/unconnected items.

**Likely cause:**

- normal first-pass board state
- missing routes
- missing net assignment if `board_connectivity_report` also shows pad-net failures

**Suggested fix:**

- read:
  - `unconnected_report.json`
  - `routing_todo_report.json`
  - `board_connectivity_report.json`

[!IMPORTANT]
Unconnected items are not automatically a tool failure. They may simply mean the board is not routed yet.

---

### `NOT_IMPLEMENTED`

**Meaning:** a command shell exists, but the operation is still alpha/incomplete.

**Likely cause:**

- command planned but not fully implemented yet

**Suggested fix:**

- use the documented alternative path
- or contribute the missing command implementation

## ✅ Checklist

- Use `nexapcb explain --list` to discover codes
- Prefer structured reports over reading raw stderr
- Distinguish tooling errors from design-state issues
- Never guess SKU or pin labels to “make the error go away”

## 🔗 Related docs

- [CLI Reference](./CLI_REFERENCE.md)
- [Reports](./REPORTS.md)
- [AI Agent Workflow](./AI_AGENT_WORKFLOW.md)
- [Part Request System](./PART_REQUEST_SYSTEM.md)
