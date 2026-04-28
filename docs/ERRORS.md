# Errors

Use:

```bash
nexapcb explain --list
nexapcb explain PIN_PAD_MISMATCH
```

## Core error codes

### `SOURCE_FILE_NOT_FOUND`
- meaning: source path does not exist
- likely cause: bad `--source` or `--entry`
- suggested fix: pass a valid source path

### `PYTHON_SYNTAX_ERROR`
- meaning: Python syntax failed before SKiDL export
- likely cause: malformed source file
- suggested fix: run `nexapcb check syntax`

### `SKIDL_IMPORT_FAILED`
- meaning: source could not import SKiDL or a local module
- likely cause: bad module path or broken local import
- suggested fix: run `nexapcb check imports`

### `SKIDL_EXPORT_FAILED`
- meaning: SKiDL execution did not generate netlist/XML
- likely cause: export functions missing or runtime exception
- suggested fix: verify `ERC()`, `generate_netlist()`, `generate_xml()`

### `XML_NOT_FOUND`
- meaning: XML export required by a later stage is missing
- likely cause: SKiDL export was not run
- suggested fix: run `nexapcb stage skidl-export` or `nexapcb export`

### `NETLIST_NOT_FOUND`
- meaning: `.net` export required by a later stage is missing
- likely cause: SKiDL export was not run
- suggested fix: rerun export and confirm `.net` exists

### `MISSING_PREREQUISITE_AST_REPORT`
- meaning: a later stage could not recover source metadata
- likely cause: `ast_parse_report.json` missing
- suggested fix: run `nexapcb stage ast`

### `JLC2KICADLIB_NOT_FOUND`
- meaning: SKU import dependency is unavailable
- likely cause: optional dependency not installed
- suggested fix: install `JLC2KiCadLib` or skip SKU import

### `LCSC_SKU_IMPORT_FAILED`
- meaning: SKU import failed
- likely cause: bad SKU or importer failure
- suggested fix: verify SKU, inspect `jlc_import_report.json`

### `SKU_NOT_CONFIRMED`
- meaning: a part has no confirmed supplier/catalog SKU
- likely cause: the exact supplier reference is not known yet
- suggested fix: search LCSC/JLCPCB/EasyEDA/SemiNest or the supplier catalog and add the SKU only if the exact match is confirmed

### `SKU_IMPORT_FAILED`
- meaning: NexaPCB could not import symbol, footprint, or model for the provided SKU
- likely cause: wrong SKU, unsupported provider, importer failure, or missing external dependency
- suggested fix: verify the SKU, check provider support, inspect `jlc_import_report.json`, or fall back to custom assets

### `CUSTOM_SYMBOL_NOT_FOUND`
- meaning: declared custom symbol file does not exist
- likely cause: wrong path
- suggested fix: fix the path or provide the symbol file

### `CUSTOM_FOOTPRINT_NOT_FOUND`
- meaning: declared custom footprint file does not exist
- likely cause: wrong path
- suggested fix: fix the path or provide the footprint file

### `CUSTOM_MODEL_NOT_FOUND`
- meaning: declared custom 3D model file does not exist
- likely cause: wrong path
- suggested fix: fix the path or provide the model file

### `PIN_PAD_MISMATCH`
- meaning: symbol pins and footprint pads do not match
- likely cause: wrong symbol, wrong footprint, or wrong pin labels in SKiDL
- suggested fix: inspect part first, compare symbol vs footprint, add verified pin map if needed

### `PIN_LABEL_NOT_CONFIRMED`
- meaning: SKiDL code used a pin label not found in the inspected symbol
- likely cause: guessed pin name or wrong symbol assumption
- suggested fix: run `nexapcb part pins` or `nexapcb part report` and use the exact symbol pin label

### `FOOTPRINT_PAD_MISMATCH`
- meaning: symbol pins do not match footprint pads
- likely cause: footprint choice is wrong, pad count differs, or the symbol uses different numbering semantics
- suggested fix: run `nexapcb part compare`, choose a matching footprint, or add a verified pin map only if electrically correct

### `ABSOLUTE_PATH_FOUND`
- meaning: generated KiCad artifacts still contain absolute paths
- likely cause: custom assets were not localized/re-written
- suggested fix: run asset localization and recheck `${KIPRJMOD}` compliance

### `KICAD_PROJECT_NOT_GENERATED`
- meaning: expected `.kicad_pro/.kicad_sch/.kicad_pcb` missing
- likely cause: generation stage failed
- suggested fix: inspect `kicad_generation_report.json`

### `KICAD_CLI_NOT_FOUND`
- meaning: KiCad CLI could not be found
- likely cause: KiCad not installed or path not discoverable
- suggested fix: install KiCad or pass `--kicad-cli`

### `ERC_FAILED`
- meaning: ERC run itself failed
- likely cause: KiCad CLI execution error
- suggested fix: inspect raw KiCad command output

### `ERC_VIOLATIONS_FOUND`
- meaning: ERC completed and found violations
- likely cause: design or generation issue
- suggested fix: read `erc_report.json`

### `DRC_FAILED`
- meaning: DRC run itself failed
- likely cause: KiCad CLI execution error
- suggested fix: inspect raw KiCad command output

### `DRC_VIOLATIONS_FOUND`
- meaning: DRC completed and found violations
- likely cause: board geometry/placement/routing issue
- suggested fix: read `drc_report.json`

### `UNCONNECTED_ITEMS_FOUND`
- meaning: board contains unrouted/unconnected items
- likely cause: normal first-pass board state or missing connectivity
- suggested fix: read `unconnected_report.json` and `routing_todo_report.json`

### `NOT_IMPLEMENTED`
- meaning: command shell exists but logic is not implemented yet
- likely cause: alpha/incomplete command
- suggested fix: use the documented alternative path or implement the missing stage
