from __future__ import annotations


HELP_TOPICS = {
    "commands": """Command groups:
- nexapcb check <subcommand>
- nexapcb stage <subcommand>
- nexapcb export
- nexapcb report <subcommand>
- nexapcb erc <run|parse|report>
- nexapcb drc <run|parse|report>
- nexapcb inspect <subcommand>
- nexapcb part <subcommand>
- nexapcb asset <subcommand>
- nexapcb net <subcommand>
- nexapcb ref <subcommand>
- nexapcb issue <subcommand>
- nexapcb doctor
- nexapcb version
- nexapcb explain

Use --format json when you want machine-readable output with status, data, issues, and next_action.
""",
    "skidl-format": """SKiDL format:\n- Use from skidl import *\n- Build named nets explicitly\n- Assign stable refs and footprints\n- Call ERC(), generate_netlist(file_='name.net'), generate_xml(file_='name.xml')\n- Modular projects are supported by running the entry file with its folder on sys.path\n""",
    "modular-projects": """Modular projects:
- Use --project-root and --entry for multi-file SKiDL projects.
- NexaPCB runs the entry file with its source folder on sys.path and cwd set to the entry folder.
- Import errors should be reported with stage=context in issue reports.

Example:
  nexapcb export --project-root my_board --entry skidl_project/main.py --project-name my_board --output out/my_board
""",
    "custom-parts": """Custom parts:\n- Use part.fields['CUSTOM_SYMBOL'] = '/path/file.kicad_sym'\n- Use part.fields['CUSTOM_SYMBOL_NAME'] = 'SymbolName'\n- Use part.fields['CUSTOM_FOOTPRINT'] = '/path/file.kicad_mod'\n- Use part.fields['CUSTOM_MODEL'] = '/path/file.step'\n- Or supply --custom-assets manifest.json\n- NexaPCB localizes these into output/symbols/custom, output/footprints/custom.pretty, output/3d_models/custom\n""",
    "sku": """LCSC/JLCPCB SKU:\n- Use part.fields['LCSC'] = 'Cxxxxx'\n- Only exact confirmed SKUs should be used\n- NexaPCB reports confirmed SKUs, no-SKU parts, and any import/localization failures\n""",
    "reports": """Reports:\n- summary_report.* generated project summary\n- check_report.* source validation\n- ast_parse_report.json AST scan\n- skidl_export_report.json SKiDL export status\n- netlist_report.* net/xml counts\n- component_report.* components and metadata\n- connection_report.* net/node mapping\n- issue_report.* collected failures and warnings\n- validation_report.* overall generated project validation\n- erc_report.* KiCad ERC summary when kicad-cli is available\n- drc_report.* KiCad PCB DRC summary when kicad-cli is available\n- unconnected_report.* unrouted PCB connectivity grouped by net/ref/subsystem\n- routing_todo_report.* routing priorities and strategy\n- board_connectivity_report.* pad-net assignment status\n- pin_pad_match_report.* symbol pins vs XML pins vs footprint pads\n- asset_report.* symbols, footprints, models, and localization status\n""",
    "errors": """Common errors:\n- SOURCE_FILE_NOT_FOUND\n- PYTHON_SYNTAX_ERROR\n- SKIDL_IMPORT_FAILED\n- SKIDL_EXPORT_FAILED\n- XML_NOT_FOUND\n- NETLIST_NOT_FOUND\n- CUSTOM_SYMBOL_NOT_FOUND\n- CUSTOM_FOOTPRINT_NOT_FOUND\n- CUSTOM_MODEL_NOT_FOUND\n- ABSOLUTE_PATH_FOUND\n- KICAD_PROJECT_NOT_GENERATED\n- ERC_FAILED\n- ERC_VIOLATIONS_FOUND\n""",
    "ai-agent-workflow": """AI agent workflow:\n1. Write or update modular SKiDL code.\n2. Run nexapcb check.\n3. Read check_report and fix source issues.\n4. Run nexapcb export.\n5. Read validation_report, erc_report, drc_report, and issue_report.\n6. Fix SKiDL code or generator settings.\n7. Repeat until reports are acceptable.\n8. Open KiCad for final engineering review.\n""",
    "ai-loop": """AI agent workflow:\n1. Write or update modular SKiDL code.\n2. Run nexapcb check.\n3. Read check_report and fix source issues.\n4. Run nexapcb export.\n5. Read validation_report, erc_report, drc_report, and issue_report.\n6. Fix SKiDL code or generator settings.\n7. Repeat until reports are acceptable.\n8. Open KiCad for final engineering review.\n""",
    "pin-mapping": """Pin mapping:\n- Pin mapping is needed when symbol pin names used by SKiDL/XML do not match footprint pad numbers.\n- Provide a JSON file with --pin-map, for example:\n  {\n    \"Q1\": {\"B\": \"1\", \"C\": \"2\", \"E\": \"3\"}\n  }\n- You can also store a mapping in SKiDL with:\n  part.fields['NEXAPCB_PINMAP'] = 'B=1,C=2,E=3'\n- NexaPCB reports whether a mapping came from direct match, normalized match, pin_map_file, skidl_field, or remains unresolved.\n- Invalid mappings are reported as PINMAP_INVALID and are never silently ignored.\n""",
    "part-request": """Part request / part study:\n- Use `nexapcb part inspect` to study a local symbol/footprint/model before writing SKiDL.\n- Use `nexapcb part compare` to compare symbol pins against footprint pads.\n- Use `nexapcb part report` to print a previously generated part-study folder.\n- This is a pre-design inspection flow. It does not generate a full board.\n""",
    "symbol-pins": """Symbol pin inspection:\n- NexaPCB parses .kicad_sym files and reports pin number, pin name, electrical type, unit, and a safe SKiDL access form.\n- Use these reports before wiring a symbol in SKiDL to avoid wrong pin labels.\n""",
    "footprint-pads": """Footprint pad inspection:\n- NexaPCB parses .kicad_mod files and reports pad number/name, type, shape, layers, position, size, drill, and model references.\n- Compare this with symbol pins before choosing a footprint in SKiDL.\n""",
    "pin-pad-match": """Pin / pad compare:\n- Use `nexapcb part compare --symbol ... --footprint ...`.\n- The compare report shows exact matches, missing pads, extra pads, normalized matches, and suggestions for safe SKiDL pin labels or mapping overrides.\n- NexaPCB does not silently guess low-confidence mappings.\n""",
    "examples": """Examples:
- Use `nexapcb examples` to list example templates.
- Use `nexapcb examples --create <name> --output <dir>` to create an example project.
- Current examples are intended for smoke testing and CLI/report validation, not for production boards.
""",
}


ERROR_EXPLANATIONS = {
    "SOURCE_FILE_NOT_FOUND": {
        "meaning": "The requested SKiDL source file does not exist.",
        "likely_cause": "Wrong --source path, wrong --project-root/--entry combination, or missing file.",
        "suggested_fix": "Pass a valid source path or verify the project root and entry path.",
        "example": "nexapcb check --source skidl_project/main.py",
    },
    "PYTHON_SYNTAX_ERROR": {
        "meaning": "Python could not compile the SKiDL source.",
        "likely_cause": "Syntax error or unsupported Python syntax in the SKiDL file.",
        "suggested_fix": "Run py_compile on the file and fix the reported line/column.",
        "example": "python3 -m py_compile skidl_project/main.py",
    },
    "SKIDL_IMPORT_FAILED": {
        "meaning": "The active Python interpreter could not import SKiDL.",
        "likely_cause": "SKiDL is not installed in the current interpreter or venv.",
        "suggested_fix": "Use the correct virtualenv or install SKiDL into the interpreter being used.",
        "example": "python3 -c 'import skidl; print(skidl.__version__)'",
    },
    "SKIDL_EXPORT_FAILED": {
        "meaning": "Executing the SKiDL source did not complete successfully.",
        "likely_cause": "Import failure, runtime exception, or bad SKiDL generation code.",
        "suggested_fix": "Read skidl_export_report.json and the command stdout/stderr to identify the failing module or line.",
        "example": "nexapcb export --source main.py --project-name demo --output out/demo",
    },
    "XML_NOT_FOUND": {
        "meaning": "No XML netlist was found after export.",
        "likely_cause": "generate_xml() was not called, used a different filename, or export failed before writing it.",
        "suggested_fix": "Ensure the SKiDL entry calls generate_xml(file_='name.xml') and that export succeeds.",
        "example": "generate_xml(file_='my_board.xml')",
    },
    "NETLIST_NOT_FOUND": {
        "meaning": "No .net file was found after export.",
        "likely_cause": "generate_netlist() was not called, used a different filename, or export failed before writing it.",
        "suggested_fix": "Ensure the SKiDL entry calls generate_netlist(file_='name.net').",
        "example": "generate_netlist(file_='my_board.net')",
    },
    "CUSTOM_ASSET_NOT_FOUND": {
        "meaning": "A referenced custom symbol, footprint, or 3D model file does not exist.",
        "likely_cause": "Incorrect path in SKiDL metadata or missing asset file.",
        "suggested_fix": "Fix the path or add the missing custom asset. Check custom_asset_report.json for the exact field and file.",
        "example": "part.fields['CUSTOM_FOOTPRINT'] = '/abs/path/to/MY_PART.kicad_mod'",
    },
    "PIN_PAD_MISMATCH": {
        "meaning": "A symbol pin used by SKiDL/XML does not match a footprint pad exposed by the chosen footprint.",
        "likely_cause": "Wrong pin labels in SKiDL, wrong symbol, wrong footprint, or missing explicit pin-map override.",
        "suggested_fix": "Read pin_pad_match_report.json and either use the correct SKiDL pin label, choose a matching footprint, or add a verified pin map.",
        "example": "part.fields['NEXAPCB_PINMAP'] = 'B=1,C=2,E=3'",
    },
    "ABSOLUTE_PATH_FOUND": {
        "meaning": "A generated KiCad artifact still contains an absolute filesystem path.",
        "likely_cause": "Custom assets or imported libraries were not localized to the output project.",
        "suggested_fix": "Localize the asset into the output folder and rewrite references to ${KIPRJMOD}.",
        "example": "CUSTOM_MODEL -> ${KIPRJMOD}/3d_models/custom/part.step",
    },
    "KICAD_PROJECT_NOT_GENERATED": {
        "meaning": "The expected .kicad_pro/.kicad_sch/.kicad_pcb file set was not generated.",
        "likely_cause": "Export failed before KiCad generation or output paths are wrong.",
        "suggested_fix": "Read final_result.json and skidl_export_report.json to find the failing stage.",
        "example": "nexapcb export --source main.py --project-name demo --output out/demo",
    },
    "ERC_FAILED": {
        "meaning": "KiCad ERC command failed to run successfully.",
        "likely_cause": "kicad-cli not found, invalid schematic path, or KiCad CLI runtime error.",
        "suggested_fix": "Pass --kicad-cli explicitly or inspect erc_report.json raw command output.",
        "example": "nexapcb erc --output out/demo --kicad-cli /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
    },
    "ERC_VIOLATIONS_FOUND": {
        "meaning": "KiCad ERC ran successfully and found violations.",
        "likely_cause": "Design-state issue in the schematic, not necessarily a tool failure.",
        "suggested_fix": "Read erc_report.json and issue_report.json, then fix the SKiDL or symbol/footprint choices.",
        "example": "nexapcb report --output out/demo --report erc --format json",
    },
}
