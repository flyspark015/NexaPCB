from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import os
import platform
import re
import uuid
from pathlib import Path

from nexapcb import __version__
from nexapcb.assets import import_jlc_assets, localize_custom_assets
from nexapcb.checker import check_source
from nexapcb.examples_lib import create_example, list_examples
from nexapcb.exporter import (
    export_project,
    _add_board_outline,
    _generate_pcb_with_kicad_python,
    _generate_schematic_inproc,
    _sanitize_kicad_artifacts,
    _tune_project_rules,
    _write_fp_lib_table,
    _write_kicad_pro,
    _write_sym_lib_table,
)
from nexapcb.helptext import ERROR_EXPLANATIONS, HELP_TOPICS
from nexapcb.inspectors import (
    apply_pinmap_to_pcb,
    build_asset_report,
    build_board_reports,
    build_component_and_connection_reports,
    build_issue_report,
    inspect_output,
    inspect_source,
)
from nexapcb.part_tools import explain_error, list_error_codes, print_part_report, write_part_reports
from nexapcb.project import detect_kicad_cli, ensure_reports_dir, resolve_source
from nexapcb.config import make_project_paths
from nexapcb.reports import write_report_json, write_report_markdown
from nexapcb.ast_parser import parse_skidl_source
from nexapcb.utils.fs import copy_dir, read_json, read_text, write_text
from nexapcb.utils.process import find_python_with_module, run_command


EXIT_OK = 0
EXIT_GENERAL = 1
EXIT_CHECK_FAILED = 2
EXIT_SKIDL_EXPORT_FAILED = 3
EXIT_ASSET_FAILED = 4
EXIT_KICAD_FAILED = 5
EXIT_VALIDATION_FAILED = 6
EXIT_ERC_VIOLATIONS = 7
EXIT_CUSTOM_ASSET_FAILED = 8


def _json_print(data: dict) -> None:
    print(json.dumps(data, indent=2))


def _response(
    *,
    command: str,
    ok: bool,
    status: str,
    data: dict | list | None = None,
    issues: list | None = None,
    reports: dict | None = None,
    next_action: str = "",
    error: dict | None = None,
) -> dict:
    payload = {
        "ok": ok,
        "command": command,
        "status": status,
        "data": data if data is not None else {},
        "issues": issues or [],
        "reports": reports or {},
        "next_action": next_action,
    }
    if error is not None:
        payload["error"] = error
    return payload


def _emit(args: argparse.Namespace, payload: dict) -> None:
    fmt = getattr(args, "format", "text")
    if fmt == "json":
        _json_print(payload)
        return
    if fmt == "md" and isinstance(payload.get("data"), dict):
        print(json.dumps(payload["data"], indent=2))
        return
    if payload.get("error"):
        print(payload["error"]["message"])
        return
    print(json.dumps(payload.get("data", {}), indent=2))


def _not_implemented(command: str, message: str) -> dict:
    return _response(
        command=command,
        ok=False,
        status="NOT_IMPLEMENTED",
        error={
            "code": "NOT_IMPLEMENTED",
            "message": message,
            "likely_cause": "This command shell exists, but the implementation is still alpha/incomplete.",
            "suggested_fix": "Use the broader export/report workflow for now, or implement this stage directly if needed.",
        },
        next_action="Use the canonical export/report commands or inspect the generated reports directly.",
    )


def _load_reports_bundle(output_root: Path) -> dict:
    reports_dir = output_root / "reports"
    names = {
        "summary": "summary_report.json",
        "components": "component_report.json",
        "connections": "connection_report.json",
        "issues": "issue_report.json",
        "validation": "validation_report.json",
        "erc": "erc_report.json",
        "drc": "drc_report.json",
        "unconnected": "unconnected_report.json",
        "routing_todo": "routing_todo_report.json",
        "board_connectivity": "board_connectivity_report.json",
        "pin_labels": "pin_label_report.json",
        "pin_pad_match": "pin_pad_match_report.json",
        "assets": "asset_report.json",
        "final_result": "final_result.json",
    }
    return {k: read_json(reports_dir / v, {}) for k, v in names.items()}


def _write_named_check_report(reports_dir: Path, name: str, payload: dict) -> None:
    write_report_json(reports_dir / f"{name}.json", payload)
    write_report_markdown(reports_dir / f"{name}.md", name.replace("_", " ").title(), payload if isinstance(payload, dict) else {"data": payload})


def _check_reports_dir(args: argparse.Namespace, source: Path | None = None) -> Path:
    if getattr(args, "output", None):
        return ensure_reports_dir(Path(args.output).expanduser().resolve())
    if getattr(args, "project_root", None):
        return ensure_reports_dir(Path(args.project_root).expanduser().resolve())
    if source is not None:
        return ensure_reports_dir(source.parent)
    return ensure_reports_dir(Path.cwd())


def _check_issues_from_result(result: dict) -> list[dict]:
    issues = []
    for err in result.get("errors", []):
        issues.append(
            {
                "severity": "error",
                "stage": "check",
                "code": err,
                "message": err,
                "file": result.get("source"),
                "ref": None,
                "pin": None,
                "pad": None,
                "net": None,
                "coordinate": None,
                "likely_cause": "Source validation failed.",
                "suggested_fix": f"Read {err} and fix the source or asset path.",
                "raw": err,
            }
        )
    for warn in result.get("warnings", []):
        issues.append(
            {
                "severity": "warning",
                "stage": "check",
                "code": warn,
                "message": warn,
                "file": result.get("source"),
                "ref": None,
                "pin": None,
                "pad": None,
                "net": None,
                "coordinate": None,
                "likely_cause": "Source check warning.",
                "suggested_fix": "Inspect the warning and decide whether the SKiDL source needs cleanup.",
                "raw": warn,
            }
        )
    return issues


def _filter_issue_entries(entries: list[dict], severity: str | None = None, code: str | None = None, ref: str | None = None, net: str | None = None) -> list[dict]:
    out = []
    for item in entries:
        if severity and item.get("severity") != severity:
            continue
        if code and item.get("code") != code:
            continue
        if ref and item.get("ref") != ref:
            continue
        if net and item.get("net") != net:
            continue
        out.append(item)
    return out


def _recover_source_from_reports(output_root: Path) -> Path | None:
    reports_dir = output_root / "reports"
    for name in ("ast_parse_report.json", "check_report.json", "final_result.json"):
        data = read_json(reports_dir / name, {})
        source = data.get("source_file") or data.get("source")
        if source:
            p = Path(source).expanduser().resolve()
            if p.exists():
                return p
    return None


def _ensure_canonical_netlist_files(output_root: Path, project_name: str) -> tuple[Path | None, Path | None]:
    netlist_dir = output_root / "netlist"
    netlist_dir.mkdir(parents=True, exist_ok=True)
    xml_target = netlist_dir / f"{project_name}.xml"
    net_target = netlist_dir / f"{project_name}.net"
    xml_existing = xml_target if xml_target.exists() else next(iter(sorted(netlist_dir.glob("*.xml"))), None)
    net_existing = net_target if net_target.exists() else next(iter(sorted(netlist_dir.glob("*.net"))), None)
    if xml_existing and xml_existing != xml_target:
        write_text(xml_target, xml_existing.read_text())
        xml_existing = xml_target
    if net_existing and net_existing != net_target:
        write_text(net_target, net_existing.read_text())
        net_existing = net_target
    return xml_existing, net_existing


def _project_name_for_stage(args: argparse.Namespace, output_root: Path) -> str | None:
    if getattr(args, "project_name", None):
        return args.project_name
    final = read_json(output_root / "reports" / "final_result.json", {})
    if final.get("project_name"):
        return final["project_name"]
    pros = sorted(output_root.glob("*.kicad_pro"))
    if pros:
        return pros[0].stem
    xmls = sorted((output_root / "netlist").glob("*.xml"))
    if xmls:
        return xmls[0].stem
    return None


def _detect_optional_module(module_name: str) -> dict:
    spec = importlib.util.find_spec(module_name)
    version = None
    if spec:
        try:
            version = importlib.metadata.version(module_name)
        except Exception:
            version = None
    return {"available": bool(spec), "version": version}


def _version_payload() -> dict:
    kicad_cli = detect_kicad_cli(None)
    kicad_version = None
    if kicad_cli:
        version_result = run_command([kicad_cli, "--version"], timeout=20)
        kicad_version = (version_result.stdout or version_result.stderr).strip()
    skidl_info = _detect_optional_module("skidl")
    jlc_info = _detect_optional_module("JLC2KiCadLib")
    return {
        "nexapcb_version": __version__,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "skidl_version": skidl_info["version"] if skidl_info["available"] else None,
        "kicad_cli_path": kicad_cli,
        "kicad_cli_version": kicad_version,
        "jlc2kicadlib_available": jlc_info["available"],
        "jlc2kicadlib_version": jlc_info["version"],
    }


def _issue_counts_from_reports(reports_dir: Path) -> dict:
    erc = read_json(reports_dir / "erc_report.json", {})
    drc = read_json(reports_dir / "drc_report.json", {})
    unconnected = read_json(reports_dir / "unconnected_report.json", {})
    pin_pad = read_json(reports_dir / "pin_pad_match_report.json", {})
    validation = read_json(reports_dir / "validation_report.json", {})
    return {
        "erc_count": int(erc.get("total", 0) or 0),
        "drc_count": int(drc.get("total", 0) or 0),
        "unconnected_count": int(unconnected.get("total_unconnected_count", unconnected.get("total_unconnected", 0)) or 0),
        "pin_pad_mismatch_count": int((pin_pad.get("summary") or {}).get("missing_pad_mapping_count", 0) or 0),
        "absolute_path_violation_count": len(validation.get("artifact_absolute_path_hits", []) or []),
    }


def _write_final_result(
    *,
    project_name: str,
    source: str,
    output_root: Path,
    status: str,
    exit_code: int,
    next_recommended_action: str,
) -> dict:
    reports_dir = ensure_reports_dir(output_root)
    issue_counts = _issue_counts_from_reports(reports_dir)
    generated_files = {
        "kicad_pro": [str(p) for p in output_root.glob("*.kicad_pro")],
        "kicad_sch": [str(p) for p in output_root.glob("*.kicad_sch")],
        "kicad_pcb": [str(p) for p in output_root.glob("*.kicad_pcb")],
        "netlist": [str(p) for p in (output_root / "netlist").glob("*")] if (output_root / "netlist").exists() else [],
    }
    reports = sorted(str(p) for p in reports_dir.glob("*"))
    payload = {
        "project_name": project_name,
        "source": source,
        "output": str(output_root),
        "status": status,
        "exit_code": exit_code,
        "generated_files": generated_files,
        "reports": reports,
        "issue_counts": issue_counts,
        **issue_counts,
        "next_recommended_action": next_recommended_action,
    }
    write_report_json(reports_dir / "final_result.json", payload)
    return payload


def _iter_symbol_blocks(text: str):
    i = 0
    while True:
        s = text.find("(symbol", i)
        if s == -1:
            break
        depth = 0
        for j in range(s, len(text)):
            ch = text[j]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    yield s, j + 1, text[s : j + 1]
                    i = j + 1
                    break
        else:
            break


def _extract_declared_nc_map(sch_file: Path) -> dict[str, set[str]]:
    text = sch_file.read_text()
    out: dict[str, set[str]] = {}
    for _, _, block in _iter_symbol_blocks(text):
        if "(instances" not in block:
            continue
        ref_m = re.search(r'\(property "Reference" "([^"]+)"', block)
        nc_m = re.search(r'\(property "NEXAPCB_NC_PINS" "([^"]+)"', block)
        if not ref_m or not nc_m:
            continue
        ref = ref_m.group(1)
        pins = {p.strip() for p in nc_m.group(1).split(",") if p.strip()}
        if pins:
            out[ref] = pins
    return out


def _add_declared_no_connects(output_root: Path) -> int:
    sch_files = list(output_root.glob("*.kicad_sch"))
    if not sch_files:
        return 0
    sch_file = sch_files[0]
    erc_file = output_root / "reports" / "final_erc.json"
    if not erc_file.exists():
        return 0
    declared = _extract_declared_nc_map(sch_file)
    if not declared:
        return 0
    erc = read_json(erc_file, {})
    text = sch_file.read_text()
    existing = set(re.findall(r'\(no_connect\s+\(at\s+([^\s]+)\s+([^\s\)]+)\)', text))
    additions: list[str] = []
    for sheet in erc.get("sheets", []):
        for viol in sheet.get("violations", []):
            if viol.get("type") != "pin_not_connected":
                continue
            item = (viol.get("items") or [{}])[0]
            desc = item.get("description", "")
            m = re.search(r"Symbol\s+(\S+)\s+Pin\s+(\S+)", desc)
            if not m:
                continue
            ref, pin = m.group(1), m.group(2)
            if pin not in declared.get(ref, set()):
                continue
            pos = item.get("pos") or {}
            x = pos.get("x")
            y = pos.get("y")
            if x is None or y is None:
                continue
            sx = f"{x * 100:.3f}".rstrip("0").rstrip(".")
            sy = f"{y * 100:.3f}".rstrip("0").rstrip(".")
            if (sx, sy) in existing:
                continue
            existing.add((sx, sy))
            additions.append(
                f'  (no_connect\n'
                f'    (at {sx} {sy})\n'
                f'    (uuid "{uuid.uuid4()}")\n'
                f'  )\n'
            )
    if not additions:
        return 0
    text = text.rstrip()
    if text.endswith(")"):
        text = text[:-1] + "\n" + "".join(additions) + ")\n"
    else:
        text += "\n" + "".join(additions)
    write_text(sch_file, text)
    return len(additions)


def _cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.project_root).expanduser().resolve()
    proj = root / "skidl_project"
    (root / "custom_assets" / "symbols").mkdir(parents=True, exist_ok=True)
    (root / "custom_assets" / "footprints").mkdir(parents=True, exist_ok=True)
    (root / "custom_assets" / "3d_models").mkdir(parents=True, exist_ok=True)
    proj.mkdir(parents=True, exist_ok=True)
    write_text(
        proj / "parts.py",
        "from skidl import *\n\n\ndef resistor(ref, value):\n    p = Part('Device', 'R', ref=ref, value=value)\n    p.footprint = 'Resistor_SMD:R_0603_1608Metric'\n    p.fields['LCSC'] = 'C25804'\n    return p\n",
    )
    write_text(
        proj / "power.py",
        "from skidl import *\nfrom parts import resistor\n\n\ndef build_power(nets):\n    c = Part('Device', 'C', ref='C1', value='10uF')\n    c.footprint = 'Capacitor_SMD:C_0805_2012Metric'\n    c[1] += nets['SYS_3V3']\n    c[2] += nets['GND']\n",
    )
    write_text(
        proj / "mcu.py",
        "from skidl import *\n\n\ndef build_mcu(nets):\n    u = Part('RF_Module', 'ESP32-S3-WROOM-1', ref='U1', value='ESP32-S3-WROOM-1-N16R8')\n    u.footprint = 'RF_Module:ESP32-S3-WROOM-1'\n    u['3V3'] += nets['SYS_3V3']\n    u['GND'] += nets['GND']\n",
    )
    write_text(
        proj / "connectors.py",
        "from skidl import *\n\n\ndef build_connectors(nets):\n    j = Part('Connector_Generic', 'Conn_01x06', ref='J1', value='UART')\n    j.footprint = 'Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical'\n    j[1] += nets['SYS_3V3']\n    j[2] += nets['GND']\n",
    )
    write_text(
        proj / "main.py",
        "from skidl import *\nfrom power import build_power\nfrom mcu import build_mcu\nfrom connectors import build_connectors\n\nnets = {\n    'SYS_3V3': Net('SYS_3V3'),\n    'GND': Net('GND'),\n}\n\nbuild_power(nets)\nbuild_mcu(nets)\nbuild_connectors(nets)\nERC()\ngenerate_netlist(file_='"
        + args.project_name
        + ".net')\ngenerate_xml(file_='"
        + args.project_name
        + ".xml')\n",
    )
    write_text(
        proj / "README.md",
        "Modular SKiDL template.\n- main.py is the entry.\n- Use part.fields['LCSC']='Cxxxxx' for confirmed SKUs.\n- Use CUSTOM_SYMBOL / CUSTOM_FOOTPRINT / CUSTOM_MODEL fields for custom assets.\n",
    )
    write_text(
        root / "nexapcb.toml",
        f'project_name = "{args.project_name}"\nentry = "skidl_project/main.py"\n',
    )
    print(str(root))
    return EXIT_OK


def _cmd_doctor(args: argparse.Namespace) -> int:
    output_root = Path(args.output or (Path.cwd() / "nexapcb_doctor")).expanduser().resolve()
    reports_dir = ensure_reports_dir(output_root)
    source_info = {}
    source_exists = None
    if args.source:
        source_path = Path(args.source).expanduser().resolve()
        source_exists = source_path.exists()
        source_info = {"source": str(source_path), "exists": source_exists}
    kicad_cli = detect_kicad_cli(args.kicad_cli)
    kicad_version = None
    if kicad_cli:
        version_result = run_command([kicad_cli, "--version"], timeout=20)
        kicad_version = (version_result.stdout or version_result.stderr).strip()
    skidl_info = _detect_optional_module("skidl")
    jlc_info = _detect_optional_module("JLC2KiCadLib")
    write_test = output_root / ".doctor_write_test"
    write_ok = False
    write_error = None
    try:
        output_root.mkdir(parents=True, exist_ok=True)
        write_test.write_text("ok")
        write_test.unlink()
        write_ok = True
    except Exception as exc:
        write_error = repr(exc)
    payload = {
        "status": "ok" if write_ok else "warning",
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "skidl": skidl_info,
        "kicad_cli": {"path": kicad_cli, "version": kicad_version, "available": bool(kicad_cli)},
        "jlc2kicadlib": jlc_info,
        "output_root": str(output_root),
        "output_writable": write_ok,
        "output_write_error": write_error,
        "source_check": source_info,
        "optional_dependencies": {
            "skidl": skidl_info["available"],
            "JLC2KiCadLib": jlc_info["available"],
        },
    }
    write_report_json(reports_dir / "doctor_report.json", payload)
    write_report_markdown(
        reports_dir / "doctor_report.md",
        "Doctor Report",
        {
            "System": {
                "python_version": payload["python_version"],
                "platform": payload["platform"],
                "output_root": payload["output_root"],
                "output_writable": payload["output_writable"],
            },
            "Dependencies": {
                "skidl_available": skidl_info["available"],
                "skidl_version": skidl_info["version"],
                "kicad_cli_available": bool(kicad_cli),
                "kicad_cli_version": kicad_version,
                "jlc2kicadlib_available": jlc_info["available"],
                "jlc2kicadlib_version": jlc_info["version"],
            },
            "Source": source_info or {"source": None},
        },
    )
    if getattr(args, "format", "text") == "json":
        _json_print(_response(command="doctor", ok=write_ok, status="OK" if write_ok else "WARNING", data=payload, next_action="Use this report to confirm local NexaPCB readiness."))
    else:
        print(json.dumps(payload, indent=2))
    return EXIT_OK if write_ok else EXIT_GENERAL


def _cmd_version(args: argparse.Namespace) -> int:
    payload = _version_payload()
    if args.json:
        _json_print(_response(command="version", ok=True, status="OK", data=payload, next_action="Use this metadata for environment-aware automation."))
    else:
        print(f"NexaPCB {payload['nexapcb_version']}")
    return EXIT_OK


def _cmd_explain(args: argparse.Namespace) -> int:
    if args.list:
        _json_print(_response(command="explain --list", ok=True, status="OK", data={"error_codes": list_error_codes()}, next_action="Use `nexapcb explain <ERROR_CODE>` for details."))
        return EXIT_OK
    payload = explain_error(args.code)
    ok = payload.get("meaning") != "Unknown error code."
    _json_print(_response(command=f"explain {args.code}", ok=ok, status="OK" if ok else "FAILED", data=payload if ok else {}, error=None if ok else {"code": "UNKNOWN_ERROR_CODE", "message": f"Unknown error code: {args.code}", "likely_cause": "The requested code is not in NexaPCB's explanation table.", "suggested_fix": "Run `nexapcb explain --list` and use a listed code."}, next_action="Use the explanation to guide SKiDL or CLI fixes."))
    return EXIT_OK if ok else EXIT_GENERAL


def _cmd_check_group(args: argparse.Namespace) -> int:
    sub = getattr(args, "check_command", None) or "all"
    source = resolve_source(args.source, args.project_root, args.entry) if (args.source or args.project_root) else None
    reports_dir = _check_reports_dir(args, source)
    python_exe = find_python_with_module("skidl", Path(args.project_root).expanduser().resolve() if args.project_root else (source.parent if source else Path.cwd())) or "python3"

    if sub == "source":
        ok = bool(source and source.exists())
        data = {"source": str(source) if source else None, "exists": ok}
        payload = _response(command="check source", ok=ok, status="OK" if ok else "FAILED", data=data, issues=[] if ok else [{"severity":"error","stage":"check","code":"SOURCE_FILE_NOT_FOUND","message":"Source file not found.","file":str(source) if source else None,"ref":None,"pin":None,"pad":None,"net":None,"coordinate":None,"likely_cause":"Bad --source or --project-root/--entry path.","suggested_fix":"Pass a valid source path.","raw":str(source) if source else ""}], reports={"check_source_report": str(reports_dir / "check_source_report.json")}, next_action="Fix the source path if missing.")
        if getattr(args, "output", None):
            _write_named_check_report(reports_dir, "check_source_report", payload)
        _emit(args, payload)
        return EXIT_OK if ok else EXIT_CHECK_FAILED

    if sub == "syntax":
        if not source or not source.exists():
            payload = _response(command="check syntax", ok=False, status="FAILED", error={"code":"SOURCE_FILE_NOT_FOUND","message":"Source file not found.","likely_cause":"Bad source path.","suggested_fix":"Pass a valid --source."}, next_action="Fix the source path.")
            _emit(args, payload)
            return EXIT_CHECK_FAILED
        result = run_command([python_exe, "-m", "py_compile", str(source)], cwd=source.parent)
        ok = result.ok
        data = {"source": str(source), "syntax_ok": ok, "stdout": result.stdout, "stderr": result.stderr}
        payload = _response(command="check syntax", ok=ok, status="OK" if ok else "FAILED", data=data, issues=[] if ok else [{"severity":"error","stage":"check","code":"PYTHON_SYNTAX_ERROR","message":"Python syntax check failed.","file":str(source),"ref":None,"pin":None,"pad":None,"net":None,"coordinate":None,"likely_cause":"Syntax error in SKiDL source.","suggested_fix":"Run py_compile and fix the reported line.","raw":result.stderr or result.stdout}], reports={"check_syntax_report": str(reports_dir / "check_syntax_report.json")}, next_action="Fix syntax and rerun.")
        if getattr(args, "output", None):
            _write_named_check_report(reports_dir, "check_syntax_report", payload)
        _emit(args, payload)
        return EXIT_OK if ok else EXIT_CHECK_FAILED

    if sub in {"imports", "skidl", "assets", "all"}:
        if not source:
            payload = _response(command=f"check {sub}", ok=False, status="FAILED", error={"code":"SOURCE_FILE_NOT_FOUND","message":"Source file not provided.","likely_cause":"Missing --source or --project-root/--entry.","suggested_fix":"Provide a source or project-root/entry."}, next_action="Provide a valid source input.")
            _emit(args, payload)
            return EXIT_CHECK_FAILED
        result = check_source(source, reports_dir, python_exe, args.custom_assets).to_dict()
        issues = _check_issues_from_result(result)
        if sub == "imports":
            ok = result["source_exists"] and result["syntax_ok"]
            data = {"source": result["source"], "imports": result["imports"], "source_exists": result["source_exists"], "syntax_ok": result["syntax_ok"]}
            report_name = "check_imports_report"
        elif sub == "skidl":
            ok = result["skidl_importable"] and result["has_generate_netlist"] and result["has_generate_xml"]
            data = {"source": result["source"], "skidl_importable": result["skidl_importable"], "has_generate_netlist": result["has_generate_netlist"], "has_generate_xml": result["has_generate_xml"], "has_erc": result["has_erc"]}
            report_name = "check_skidl_report"
        elif sub == "assets":
            ok = not result["custom_asset_missing"]
            data = {"source": result["source"], "custom_asset_count": result["custom_asset_count"], "custom_asset_missing": result["custom_asset_missing"]}
            report_name = "check_assets_report"
        else:
            ok = result["ok"]
            data = result
            report_name = "check_report"
        payload = _response(command=f"check {sub}", ok=ok, status="OK" if ok else "FAILED", data=data, issues=issues, reports={report_name: str(reports_dir / f"{report_name}.json")}, next_action="Fix reported issues before export." if not ok else "Proceed to export.")
        if getattr(args, "output", None):
            _write_named_check_report(reports_dir, report_name, payload)
        _emit(args, payload)
        return EXIT_OK if ok else EXIT_CHECK_FAILED

    if sub == "paths":
        output_root = Path(args.output).expanduser().resolve()
        out_info = inspect_output(output_root)
        ok = len(out_info.get("artifact_absolute_path_hits", [])) == 0
        data = {
            "output": str(output_root),
            "artifact_absolute_path_hits": out_info.get("artifact_absolute_path_hits", []),
            "report_metadata_absolute_path_hits": out_info.get("report_metadata_absolute_path_hits", []),
        }
        payload = _response(command="check paths", ok=ok, status="OK" if ok else "FAILED", data=data, issues=[] if ok else [{"severity":"error","stage":"validation","code":"ABSOLUTE_PATH_FOUND","message":"Absolute paths remain in KiCad artifacts.","file":str(output_root),"ref":None,"pin":None,"pad":None,"net":None,"coordinate":None,"likely_cause":"Assets or library references were not localized.","suggested_fix":"Localize assets and rewrite to ${KIPRJMOD}.","raw":str(data["artifact_absolute_path_hits"])}], reports={"check_paths_report": str(reports_dir / "check_paths_report.json")}, next_action="Fix artifact path localization." if not ok else "No KiCad artifact absolute-path violations found.")
        if getattr(args, "output", None):
            _write_named_check_report(reports_dir, "check_paths_report", payload)
        _emit(args, payload)
        return EXIT_OK if ok else EXIT_CHECK_FAILED

    payload = _not_implemented(f"check {sub}", f"Unsupported check subcommand: {sub}")
    _emit(args, payload)
    return EXIT_GENERAL


def _cmd_check(args: argparse.Namespace) -> int:
    return _cmd_check_group(args)


def _write_additional_reports(output_root: Path, source: Path, custom_assets: str | None = None, pin_map: str | None = None) -> None:
    reports_dir = output_root / "reports"
    kicad_cli = detect_kicad_cli(None)
    sch_files = list(output_root.glob("*.kicad_sch"))
    pcb_files = list(output_root.glob("*.kicad_pcb"))
    if kicad_cli and sch_files:
        run_command([kicad_cli, "sch", "export", "netlist", str(sch_files[0]), "-o", str(reports_dir / "from_schematic.net")], cwd=output_root)
        run_command([kicad_cli, "sch", "erc", str(sch_files[0]), "--format", "json", "-o", str(reports_dir / "final_erc.json")], cwd=output_root)
        if _add_declared_no_connects(output_root):
            run_command([kicad_cli, "sch", "export", "netlist", str(sch_files[0]), "-o", str(reports_dir / "from_schematic.net")], cwd=output_root)
            run_command([kicad_cli, "sch", "erc", str(sch_files[0]), "--format", "json", "-o", str(reports_dir / "final_erc.json")], cwd=output_root)
        if pcb_files and pin_map:
            apply_pinmap_to_pcb(output_root, pin_map)
        if pcb_files:
            run_command([kicad_cli, "pcb", "drc", str(pcb_files[0]), "--format", "json", "-o", str(reports_dir / "final_drc.json")], cwd=output_root)
            run_command([kicad_cli, "pcb", "drc", str(pcb_files[0]), "--output", str(reports_dir / "pcb_drc.rpt")], cwd=output_root)
    component_report, connection_report, pin_label_report, pad_mapping_report = build_component_and_connection_reports(output_root, source=source, pin_map_path=pin_map)
    build_board_reports(output_root)
    build_asset_report(output_root)
    issue_report = build_issue_report(output_root)
    source_info = inspect_source(source)
    output_info = inspect_output(output_root, reports_dir=reports_dir)
    validation = read_json(reports_dir / "validation_report.json", {})
    validation["artifact_absolute_path_hits"] = output_info.get("artifact_absolute_path_hits", [])
    validation["report_metadata_absolute_path_hits"] = output_info.get("report_metadata_absolute_path_hits", [])
    validation["counts"] = {
        "components": output_info["component_count"],
        "schematic_symbols": output_info["schematic_symbol_count"],
        "pcb_footprints": output_info["pcb_footprint_count"],
        "nets": output_info["net_count"],
        "nodes": output_info["node_count"],
    }
    validation["xml_parse"] = {"ok": output_info.get("xml_ok", False), "error": output_info.get("xml_error")}
    write_report_json(reports_dir / "validation_report.json", validation)
    write_report_markdown(
        reports_dir / "validation_report.md",
        "NexaPCB Validation Report",
        {
            "Counts": validation["counts"],
            "Validation": {
                "source_export_ok": validation.get("source_export_ok", False),
                "pcb_generation_ok": validation.get("pcb_generation_ok", False),
                "artifact_absolute_path_hits": len(validation["artifact_absolute_path_hits"]),
                "report_metadata_absolute_path_hits": len(validation["report_metadata_absolute_path_hits"]),
                "xml_parse_ok": output_info.get("xml_ok", False),
            },
        },
    )
    write_report_json(
        reports_dir / "summary_report.json",
        {
            "project_name": output_root.name,
            "source_path": str(source),
            "output_path": str(output_root),
            "component_count": output_info["component_count"],
            "schematic_symbol_count": output_info["schematic_symbol_count"],
            "pcb_footprint_count": output_info["pcb_footprint_count"],
            "net_count": output_info["net_count"],
            "node_count": output_info["node_count"],
            "sku_count": len(source_info["sku_map"]),
            "custom_asset_count": len(source_info["custom_assets"]),
            "validation_status": validation.get("source_export_ok", False),
            "erc_status": validation.get("erc", {}).get("ok", False),
            "artifact_absolute_path_hits": len(output_info.get("artifact_absolute_path_hits", [])),
            "report_metadata_absolute_path_hits": len(output_info.get("report_metadata_absolute_path_hits", [])),
            "xml_ok": output_info.get("xml_ok", False),
        },
    )
    write_report_markdown(
        reports_dir / "summary_report.md",
        "Summary Report",
        {
            "Counts": {
                "components": output_info["component_count"],
                "schematic_symbols": output_info["schematic_symbol_count"],
                "pcb_footprints": output_info["pcb_footprint_count"],
                "nets": output_info["net_count"],
                "nodes": output_info["node_count"],
            }
        },
    )
    erc = read_json(reports_dir / "final_erc.json", {})
    violation_types: dict[str, int] = {}
    total = 0
    for sheet in erc.get("sheets", []):
        for v in sheet.get("violations", []):
            violation_types[v.get("type", "unknown")] = violation_types.get(v.get("type", "unknown"), 0) + 1
            total += 1
    write_report_json(reports_dir / "erc_report.json", {"total": total, "breakdown": violation_types, "raw": erc})
    write_report_markdown(reports_dir / "erc_report.md", "ERC Report", {"Counts": {"total": total, **violation_types}})
    write_report_json(
        reports_dir / "skidl_export_report.json",
        {
            "source": str(source),
            "custom_assets_manifest": custom_assets,
            "component_report_count": component_report["component_count"],
            "connection_net_count": connection_report["net_count"],
            "pin_label_mismatch_count": pin_label_report["summary"]["missing_pad_mapping_count"],
            "matched_pad_count": pad_mapping_report["matched_pad_nets"],
            "issue_count": issue_report["issue_count"],
        },
    )

def _cmd_export(args: argparse.Namespace) -> int:
    source = resolve_source(args.source, args.project_root, args.entry)
    output_root = Path(args.output).expanduser().resolve()
    reports_dir = ensure_reports_dir(output_root)
    python_exe = find_python_with_module("skidl", Path(args.project_root).expanduser().resolve() if args.project_root else source.parent) or "python3"
    check = check_source(source, reports_dir, python_exe, args.custom_assets)
    if not check.ok:
        payload = {"stage": "check", "result": check.to_dict()}
        _write_final_result(
            project_name=args.project_name,
            source=str(source),
            output_root=output_root,
            status="export_failed",
            exit_code=EXIT_CHECK_FAILED,
            next_recommended_action="Fix source/check issues listed in check_report.json before exporting again.",
        )
        _json_print(payload)
        return EXIT_CHECK_FAILED

    result = export_project(source, args.project_name, output_root)
    initial_component_report, _, _, _ = build_component_and_connection_reports(output_root, source=source, pin_map_path=args.pin_map)
    try:
        import_jlc_assets(
            output_root,
            initial_component_report.get("components", []),
            allow_generic_fallback=args.allow_generic_fallback,
            python_exe=python_exe,
        )
    except Exception as exc:
        _write_final_result(
            project_name=args.project_name,
            source=str(source),
            output_root=output_root,
            status="export_failed",
            exit_code=EXIT_ASSET_FAILED,
            next_recommended_action="Review JLC/SKU import failures and either fix the SKU or allow generic fallback explicitly.",
        )
        _json_print({"stage": "jlc_import", "error": str(exc)})
        return EXIT_ASSET_FAILED
    custom_report = localize_custom_assets(source, output_root, args.custom_assets)
    if custom_report.get("missing"):
        _write_final_result(
            project_name=args.project_name,
            source=str(source),
            output_root=output_root,
            status="export_failed",
            exit_code=EXIT_CUSTOM_ASSET_FAILED,
            next_recommended_action="Fix missing custom assets reported in custom_asset_report.json.",
        )
        return EXIT_CUSTOM_ASSET_FAILED
    _write_additional_reports(output_root, source, args.custom_assets, args.pin_map)
    issue_counts = _issue_counts_from_reports(reports_dir)
    strict_issue_present = any(
        issue_counts[k] > 0
        for k in ("erc_count", "drc_count", "unconnected_count", "pin_pad_mismatch_count", "absolute_path_violation_count")
    )
    exit_code = EXIT_OK
    status = "export_successful"
    next_action = "Open the generated reports and KiCad project for review."
    if not result.export_ok:
        exit_code = EXIT_SKIDL_EXPORT_FAILED
        status = "export_failed"
        next_action = "Fix the SKiDL execution error shown in skidl_export_report.json."
    elif not result.validation.get("pcb_generation_ok", False):
        exit_code = EXIT_KICAD_FAILED
        status = "export_failed"
        next_action = "Fix KiCad generation issues reported in validation_report.json and logs/export.log."
    elif args.strict and strict_issue_present and not args.allow_issues:
        exit_code = EXIT_VALIDATION_FAILED
        status = "export_successful_with_issues"
        next_action = "Fix reported validation/ERC/DRC/pin-pad/unconnected issues before treating this export as clean."
    elif strict_issue_present:
        status = "export_successful_with_issues"
        next_action = "Design issues remain; read final_result.json and the reports bundle before editing SKiDL."
    final_result = _write_final_result(
        project_name=args.project_name,
        source=str(source),
        output_root=output_root,
        status=status,
        exit_code=exit_code,
        next_recommended_action=next_action,
    )
    _json_print({**result.to_dict(), "final_result": final_result})
    if not result.export_ok:
        return EXIT_SKIDL_EXPORT_FAILED
    if not result.validation.get("pcb_generation_ok", False):
        return EXIT_KICAD_FAILED
    return exit_code


def _select_report_data(bundle: dict, name: str) -> dict:
    mapping = {
        "summary": bundle.get("summary", {}),
        "components": bundle.get("components", {}),
        "connections": bundle.get("connections", {}),
        "issues": bundle.get("issues", {}),
        "validation": bundle.get("validation", {}),
        "erc": bundle.get("erc", {}),
        "drc": bundle.get("drc", {}),
        "unconnected": bundle.get("unconnected", {}),
        "routing": bundle.get("routing_todo", {}),
        "board-connectivity": bundle.get("board_connectivity", {}),
        "pin-pad": bundle.get("pin_pad_match", {}),
        "pin-labels": bundle.get("pin_labels", {}),
        "assets": bundle.get("assets", {}),
        "final": bundle.get("final_result", {}),
        "final-result": bundle.get("final_result", {}),
        "all": bundle,
        "nets": bundle.get("connections", {}),
        "footprints": {"footprint_count": bundle.get("summary", {}).get("pcb_footprint_count")},
    }
    return mapping.get(name, {})


def _cmd_report(args: argparse.Namespace) -> int:
    output_root = Path(args.output).expanduser().resolve()
    bundle = _load_reports_bundle(output_root)
    report_name = getattr(args, "report_command", None) or getattr(args, "report", None) or "summary"
    data = _select_report_data(bundle, report_name)
    if report_name == "issues":
        issue_items = data.get("issues", []) if isinstance(data, dict) else []
        data = {**data, "issues": _filter_issue_entries(issue_items, getattr(args, "severity", None), getattr(args, "code", None), getattr(args, "ref", None), getattr(args, "net", None))}
    payload = _response(command=f"report {report_name}", ok=True, status="OK", data=data, reports={"reports_dir": str(output_root / 'reports')}, next_action="Read the selected report data and update SKiDL or generator behavior as needed.")
    _emit(args, payload)
    return EXIT_OK


def _cmd_erc(args: argparse.Namespace) -> int:
    sub = getattr(args, "erc_command", None) or "run"
    output_root = Path(args.output).expanduser().resolve()
    reports_dir = ensure_reports_dir(output_root)
    if sub == "report":
        payload = _response(command="erc report", ok=True, status="OK", data=read_json(reports_dir / "erc_report.json", {}), reports={"erc_report": str(reports_dir / "erc_report.json")}, next_action="Use the ERC report to fix schematic issues in SKiDL or generation.")
        _emit(args, payload)
        return EXIT_OK
    if sub == "parse":
        input_path = Path(args.input).expanduser().resolve() if args.input else reports_dir / "final_erc.json"
        if not input_path.exists():
            payload = _response(command="erc parse", ok=False, status="FAILED", error={"code":"ERC_REPORT_NOT_FOUND","message":"ERC input file not found.","likely_cause":"KiCad ERC has not been run yet or --input is wrong.","suggested_fix":"Run `nexapcb erc run` first or pass a valid --input file."}, next_action="Provide an existing KiCad ERC JSON file.")
            _emit(args, payload)
            return EXIT_KICAD_FAILED
        raw = read_json(input_path, {})
        breakdown: dict[str, int] = {}
        total = 0
        issues = []
        for sheet in raw.get("sheets", []):
            for v in sheet.get("violations", []):
                vtype = v.get("type", "unknown")
                breakdown[vtype] = breakdown.get(vtype, 0) + 1
                total += 1
                item = (v.get("items") or [{}])[0]
                issues.append({"severity": "error", "stage": "erc", "code": vtype.upper(), "message": v.get("description") or vtype, "file": str(input_path), "ref": item.get("ref"), "pin": item.get("pin"), "pad": None, "net": item.get("net"), "coordinate": item.get("pos"), "likely_cause": "Schematic design or generation issue.", "suggested_fix": "Read the exact violation and update the SKiDL source or generation logic.", "raw": v})
        payload_data = {"total": total, "breakdown": breakdown, "raw": raw}
        write_report_json(reports_dir / "erc_report.json", payload_data)
        write_report_markdown(reports_dir / "erc_report.md", "ERC Report", {"Counts": {"total": total, **breakdown}})
        payload = _response(command="erc parse", ok=True, status="OK", data=payload_data, issues=issues, reports={"erc_report": str(reports_dir / "erc_report.json")}, next_action="Use the normalized ERC report in issue triage or AI repair loops.")
        _emit(args, payload)
        return EXIT_OK if (total == 0 or args.allow_errors) else EXIT_ERC_VIOLATIONS
    kicad_cli = detect_kicad_cli(args.kicad_cli)
    if not kicad_cli:
        payload = _response(command="erc run", ok=False, status="FAILED", error={"code":"KICAD_CLI_NOT_FOUND","message":"KiCad CLI was not found.","likely_cause":"KiCad is not installed or the path is not discoverable.","suggested_fix":"Install KiCad or pass --kicad-cli explicitly."}, next_action="Install KiCad or rerun with --kicad-cli.")
        _emit(args, payload)
        return EXIT_OK if args.allow_errors else EXIT_KICAD_FAILED
    sch_files = list(output_root.glob("*.kicad_sch"))
    if not sch_files:
        payload = _response(command="erc run", ok=False, status="FAILED", error={"code":"KICAD_PROJECT_NOT_GENERATED","message":"No schematic file found in output.","likely_cause":"Export did not generate a KiCad schematic.","suggested_fix":"Run export first and verify the output path."}, next_action="Generate the KiCad project first.")
        _emit(args, payload)
        return EXIT_KICAD_FAILED
    erc_json = reports_dir / "erc_report.json"
    result = run_command([kicad_cli, "sch", "erc", str(sch_files[0]), "--format", "json", "-o", str(erc_json)], cwd=output_root)
    raw = read_json(erc_json, {})
    breakdown: dict[str, int] = {}
    total = 0
    for sheet in raw.get("sheets", []):
        for v in sheet.get("violations", []):
            breakdown[v.get("type", "unknown")] = breakdown.get(v.get("type", "unknown"), 0) + 1
            total += 1
    write_report_markdown(reports_dir / "erc_report.md", "ERC Report", {"Counts": {"total": total, **breakdown}})
    payload = {"command": result.to_dict(), "total": total, "breakdown": breakdown, "raw": raw}
    write_report_json(erc_json, payload)
    _emit(args, _response(command="erc run", ok=True, status="OK", data=payload, reports={"erc_report": str(erc_json)}, next_action="Read erc_report.json or run `nexapcb report erc`."))
    if total and not args.allow_errors:
        return EXIT_ERC_VIOLATIONS
    return EXIT_OK


def _cmd_drc(args: argparse.Namespace) -> int:
    sub = getattr(args, "drc_command", None) or "run"
    output_root = Path(args.output).expanduser().resolve()
    reports_dir = ensure_reports_dir(output_root)
    if sub == "report":
        payload = _response(command="drc report", ok=True, status="OK", data=read_json(reports_dir / "drc_report.json", {}), reports={"drc_report": str(reports_dir / "drc_report.json")}, next_action="Read the DRC report and board connectivity/unconnected reports together.")
        _emit(args, payload)
        return EXIT_OK
    if sub == "parse":
        input_path = Path(args.input).expanduser().resolve() if args.input else reports_dir / "final_drc.json"
        if not input_path.exists():
            payload = _response(command="drc parse", ok=False, status="FAILED", error={"code":"DRC_REPORT_NOT_FOUND","message":"DRC input file not found.","likely_cause":"KiCad DRC has not been run yet or --input is wrong.","suggested_fix":"Run `nexapcb drc run` first or pass a valid --input file."}, next_action="Provide an existing KiCad DRC JSON file.")
            _emit(args, payload)
            return EXIT_KICAD_FAILED
        build_board_reports(output_root)
        payload = _response(command="drc parse", ok=True, status="OK", data=read_json(reports_dir / "drc_report.json", {}), reports={"drc_report": str(reports_dir / "drc_report.json")}, next_action="Use DRC, unconnected, and routing reports together.")
        _emit(args, payload)
        return EXIT_OK if ((payload["data"].get("total") or 0) == 0 or args.allow_errors) else EXIT_ERC_VIOLATIONS
    kicad_cli = detect_kicad_cli(args.kicad_cli)
    if not kicad_cli:
        payload = _response(command="drc run", ok=False, status="FAILED", error={"code":"KICAD_CLI_NOT_FOUND","message":"KiCad CLI was not found.","likely_cause":"KiCad is not installed or not discoverable.","suggested_fix":"Install KiCad or pass --kicad-cli explicitly."}, next_action="Install KiCad or rerun with --kicad-cli.")
        _emit(args, payload)
        return EXIT_OK if args.allow_errors else EXIT_KICAD_FAILED
    pcb_files = list(output_root.glob("*.kicad_pcb"))
    if not pcb_files:
        payload = _response(command="drc run", ok=False, status="FAILED", error={"code":"KICAD_PROJECT_NOT_GENERATED","message":"No PCB file found in output.","likely_cause":"Export did not generate a KiCad PCB.","suggested_fix":"Run export first and verify the output path."}, next_action="Generate the KiCad project first.")
        _emit(args, payload)
        return EXIT_KICAD_FAILED
    drc_json = reports_dir / "final_drc.json"
    result_json = run_command([kicad_cli, "pcb", "drc", str(pcb_files[0]), "--format", "json", "-o", str(drc_json)], cwd=output_root)
    result_rpt = run_command([kicad_cli, "pcb", "drc", str(pcb_files[0]), "--output", str(reports_dir / "pcb_drc.rpt")], cwd=output_root)
    build_board_reports(output_root)
    drc_report = read_json(reports_dir / "drc_report.json", {})
    payload = {
        "command_json": result_json.to_dict(),
        "command_rpt": result_rpt.to_dict(),
        **drc_report,
    }
    write_report_json(reports_dir / "drc_report.json", payload)
    _emit(args, _response(command="drc run", ok=True, status="OK", data=payload, reports={"drc_report": str(reports_dir / "drc_report.json")}, next_action="Read drc_report, unconnected_report, and routing_todo_report together."))
    if (payload.get("total") or 0) and not args.allow_errors:
        return EXIT_ERC_VIOLATIONS
    return EXIT_OK


def _cmd_inspect(args: argparse.Namespace) -> int:
    sub = getattr(args, "inspect_command", None)
    if args.output and args.pin_labels:
        sub = "pin-labels"
    if args.output and args.pin_pad_match:
        sub = "pin-pad-match"
    if not sub:
        sub = "source" if (args.source or (args.project_root and args.entry)) else "output"
    if sub == "source":
        source = resolve_source(args.source, args.project_root, args.entry)
        result = inspect_source(source)
    else:
        output_root = Path(args.output).expanduser().resolve()
        bundle = _load_reports_bundle(output_root)
        if sub == "output":
            result = inspect_output(output_root)
        elif sub == "symbols":
            result = bundle.get("assets", {}).get("symbols", {})
        elif sub == "footprints":
            result = bundle.get("assets", {}).get("footprints", {})
        elif sub == "models":
            result = bundle.get("assets", {}).get("models", {})
        elif sub == "nets":
            con = bundle.get("connections", {})
            nets = con.get("nets", [])
            if args.net:
                nets = [n for n in nets if n.get("name") == args.net]
            result = {"nets": nets}
        elif sub == "refs":
            comps = bundle.get("components", {}).get("components", [])
            if args.ref:
                comps = [c for c in comps if c.get("ref") == args.ref]
            result = {"components": comps}
        elif sub == "paths":
            result = {
                "artifact_absolute_path_hits": bundle.get("validation", {}).get("artifact_absolute_path_hits", []),
                "report_metadata_absolute_path_hits": bundle.get("validation", {}).get("report_metadata_absolute_path_hits", []),
            }
        elif sub == "pin-labels":
            result = bundle.get("pin_labels", {})
        elif sub == "pin-pad-match":
            result = bundle.get("pin_pad_match", {})
        else:
            payload = _not_implemented(f"inspect {sub}", f"Unsupported inspect subcommand: {sub}")
            _emit(args, payload)
            return EXIT_GENERAL
    _emit(args, _response(command=f"inspect {sub}", ok=True, status="OK", data=result, next_action="Use this inspection output to decide the next command or source edit."))
    return EXIT_OK


def _cmd_examples(args: argparse.Namespace) -> int:
    if not args.create:
        print("\n".join(list_examples()))
        return EXIT_OK
    output = create_example(args.create, args.output)
    print(str(output))
    return EXIT_OK


def _cmd_help(args: argparse.Namespace) -> int:
    if not args.topic:
        print("Topics: " + ", ".join(sorted(HELP_TOPICS)))
        return EXIT_OK
    text = HELP_TOPICS.get(args.topic)
    if not text:
        print(f"Unknown help topic: {args.topic}")
        return EXIT_GENERAL
    print(text)
    return EXIT_OK


def _cmd_part_inspect(args: argparse.Namespace) -> int:
    output = Path(args.output or Path.cwd() / "nexapcb_part_inspect").expanduser().resolve()
    payload = write_part_reports(
        output,
        mpn=args.mpn or "",
        sku=args.sku or "",
        symbol_file=args.symbol,
        symbol_name=args.symbol_name,
        footprint_file=args.footprint,
        model_file=args.model,
        source_type="custom" if args.symbol or args.footprint or args.model else "manual",
    )
    _json_print(payload)
    return EXIT_OK


def _cmd_part_lookup(args: argparse.Namespace) -> int:
    output = Path(args.output or Path.cwd() / f"nexapcb_part_{args.sku}").expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    reports_dir = ensure_reports_dir(output)
    if not args.sku:
        payload = _response(
            command="part lookup",
            ok=False,
            status="FAILED",
            error={
                "code": "LCSC_SKU_REQUIRED",
                "message": "part lookup requires --sku.",
                "likely_cause": "No LCSC/JLCPCB SKU was provided.",
                "suggested_fix": "Pass a confirmed --sku such as C25804.",
            },
            next_action="Provide a confirmed LCSC/JLCPCB SKU.",
        )
        _emit(args, payload)
        return EXIT_CHECK_FAILED
    jlc_info = _detect_optional_module("JLC2KiCadLib")
    if not jlc_info["available"]:
        payload = _response(
            command="part lookup",
            ok=False,
            status="FAILED",
            error={
                "code": "JLC2KICADLIB_NOT_FOUND",
                "message": "JLC2KiCadLib is not available.",
                "likely_cause": "The optional importer dependency is not installed.",
                "suggested_fix": "Install JLC2KiCadLib or inspect local symbol/footprint files instead.",
            },
            next_action="Install JLC2KiCadLib or use `nexapcb part inspect`.",
        )
        _emit(args, payload)
        return EXIT_ASSET_FAILED
    python_exe = find_python_with_module("skidl", Path.cwd()) or "python3"
    data = import_jlc_assets(output, [{"ref": args.ref or "U1", "LCSC": args.sku}], allow_generic_fallback=False, python_exe=python_exe)
    succeeded = data.get("succeeded", [])
    if not succeeded:
        payload = _response(
            command="part lookup",
            ok=False,
            status="FAILED",
            error={
                "code": "LCSC_SKU_IMPORT_FAILED",
                "message": f"Failed to import SKU {args.sku}.",
                "likely_cause": "The JLC import tool could not fetch or convert the part assets.",
                "suggested_fix": "Verify the SKU exists and retry, or inspect a local symbol/footprint manually.",
            },
            data=data,
            reports={"jlc_import_report": str(reports_dir / "jlc_import_report.json")},
            next_action="Retry with a valid SKU or switch to local part inspection.",
        )
        _emit(args, payload)
        return EXIT_ASSET_FAILED
    item = succeeded[0]
    symbol_file = output / "symbols" / f"{item['symbol_lib']}.kicad_sym"
    footprint_lib, footprint_name = item["footprint"].split(":", 1)
    footprint_file = output / "footprints" / f"{footprint_lib}.pretty" / f"{footprint_name}.kicad_mod"
    model_dir = output / "3d_models" / "imported_jlc" / args.sku
    model_file = next(iter(sorted(model_dir.glob("*"))), None) if model_dir.exists() else None
    part_payload = write_part_reports(
        output,
        mpn=args.mpn or item.get("symbol_name") or args.sku,
        sku=args.sku,
        symbol_file=symbol_file,
        symbol_name=item.get("symbol_name"),
        footprint_file=footprint_file,
        model_file=model_file,
        source_type="lcsc",
    )
    write_report_json(reports_dir / "part_lookup_report.json", part_payload)
    write_report_markdown(reports_dir / "part_lookup_report.md", "Part Lookup Report", part_payload)
    payload = _response(
        command="part lookup",
        ok=True,
        status="OK",
        data=part_payload,
        reports={
            "part_lookup_report": str(reports_dir / "part_lookup_report.json"),
            "part_summary_report": str(reports_dir / "part_summary_report.json"),
        },
        next_action="Use the symbol/pad reports before wiring this part in SKiDL.",
    )
    _emit(args, payload)
    return EXIT_OK


def _cmd_part_request(args: argparse.Namespace) -> int:
    if args.sku:
        return _cmd_part_lookup(args)
    if args.symbol or args.footprint or args.model:
        return _cmd_part_inspect(args)
    payload = _response(
        command="part request",
        ok=False,
        status="FAILED",
        error={
            "code": "PART_REQUEST_INCOMPLETE",
            "message": "part request needs either --sku or local --symbol/--footprint inputs.",
            "likely_cause": "No usable part source was provided.",
            "suggested_fix": "Pass --sku for JLC lookup or local symbol/footprint/model paths for inspection.",
        },
        next_action="Provide a SKU or local asset paths.",
    )
    _emit(args, payload)
    return EXIT_CHECK_FAILED


def _cmd_part_compare(args: argparse.Namespace) -> int:
    output = Path(args.output or Path.cwd() / "nexapcb_part_compare").expanduser().resolve()
    payload = write_part_reports(
        output,
        mpn=args.mpn or "",
        sku=args.sku or "",
        symbol_file=args.symbol,
        symbol_name=args.symbol_name,
        footprint_file=args.footprint,
        model_file=args.model,
        source_type="manual",
    )
    compare = payload.get("compare", {})
    _json_print(payload)
    if compare.get("status") == "failed_pin_pad_mismatch" and not args.allow_fuzzy:
        return EXIT_VALIDATION_FAILED
    return EXIT_OK


def _cmd_part_report(args: argparse.Namespace) -> int:
    payload = print_part_report(args.input, fmt=args.format)
    if args.format == "json":
        _json_print(_response(command="part report", ok=True, status="OK", data=payload, next_action="Use the part study bundle before wiring SKiDL."))
    else:
        print(json.dumps(payload, indent=2))
    return EXIT_OK


def _cmd_part_pins(args: argparse.Namespace) -> int:
    from nexapcb.part_tools import parse_kicad_sym
    data = parse_kicad_sym(args.symbol, args.symbol_name)
    ok = bool(data.get("symbols")) and data.get("status") == "ok"
    payload = _response(command="part pins", ok=ok, status="OK" if ok else "FAILED", data=data, next_action="Use the safe pin labels in SKiDL wiring.")
    _emit(args, payload)
    return EXIT_OK if ok else EXIT_GENERAL


def _cmd_part_pads(args: argparse.Namespace) -> int:
    from nexapcb.part_tools import parse_kicad_mod
    data = parse_kicad_mod(args.footprint)
    payload = _response(command="part pads", ok=bool(data.get("exists")), status="OK" if data.get("exists") else "FAILED", data=data, next_action="Use the footprint pads to verify symbol compatibility.")
    _emit(args, payload)
    return EXIT_OK if data.get("exists") else EXIT_GENERAL


def _cmd_part_skidl_snippet(args: argparse.Namespace) -> int:
    base = Path(args.input).expanduser().resolve()
    data = read_json(base / "reports" / "skidl_usage_report.json", {})
    if not data:
        data = read_json(base / "skidl_usage_report.json", {})
    payload = _response(command="part skidl-snippet", ok=bool(data), status="OK" if data else "FAILED", data=data, next_action="Use the snippet as the starting point for SKiDL part declaration.")
    _emit(args, payload)
    return EXIT_OK if data else EXIT_GENERAL


def _cmd_part_model_check(args: argparse.Namespace) -> int:
    model = Path(args.model).expanduser().resolve() if args.model else None
    data = {
        "footprint": args.footprint,
        "model": str(model) if model else None,
        "model_exists": bool(model and model.exists()),
        "absolute_path": str(model).startswith("/") if model else False,
    }
    payload = _response(command="part model-check", ok=data["model_exists"], status="OK" if data["model_exists"] else "FAILED", data=data, next_action="Provide a valid model path or localize it under ${KIPRJMOD}.")
    _emit(args, payload)
    return EXIT_OK if data["model_exists"] else EXIT_GENERAL


def _cmd_asset(args: argparse.Namespace) -> int:
    sub = getattr(args, "asset_command", None) or "scan"
    if sub == "scan":
        source = resolve_source(args.source, args.project_root, args.entry)
        data = inspect_source(source)
        payload = _response(command="asset scan", ok=True, status="OK", data={"custom_assets": data.get("custom_assets", {}), "sku_map": data.get("sku_map", {})}, next_action="Use this to verify SKUs and custom asset references before export.")
    elif sub == "localize":
        output_root = Path(args.output).expanduser().resolve()
        source = resolve_source(args.source, args.project_root, args.entry) if (args.source or args.project_root) else None
        if not source:
            payload = _not_implemented("asset localize", "asset localize currently requires --source or --project-root/--entry.")
        else:
            data = localize_custom_assets(source, output_root, args.custom_assets)
            payload = _response(command="asset localize", ok=not data.get("missing"), status="OK" if not data.get("missing") else "FAILED", data=data, next_action="Fix missing custom assets if any remain.")
    elif sub == "check-paths":
        output_root = Path(args.output).expanduser().resolve()
        data = inspect_output(output_root)
        data = {
            "artifact_absolute_path_hits": data.get("artifact_absolute_path_hits", []),
            "report_metadata_absolute_path_hits": data.get("report_metadata_absolute_path_hits", []),
        }
        payload = _response(command="asset check-paths", ok=len(data["artifact_absolute_path_hits"]) == 0, status="OK" if len(data["artifact_absolute_path_hits"]) == 0 else "FAILED", data=data, next_action="Fix KiCad artifact absolute paths if any remain.")
    elif sub == "report":
        output_root = Path(args.output).expanduser().resolve()
        data = read_json(output_root / "reports" / "asset_report.json", {})
        payload = _response(command="asset report", ok=True, status="OK", data=data, next_action="Use the asset report to verify symbol/footprint/model localization.")
    else:
        payload = _not_implemented(f"asset {sub}", f"Unsupported asset subcommand: {sub}")
    _emit(args, payload)
    return EXIT_OK if payload.get("ok") else (EXIT_CUSTOM_ASSET_FAILED if payload.get("error", {}).get("code") == "CUSTOM_ASSET_NOT_FOUND" else EXIT_GENERAL)


def _cmd_net(args: argparse.Namespace) -> int:
    output_root = Path(args.output).expanduser().resolve()
    bundle = _load_reports_bundle(output_root)
    nets = bundle.get("connections", {}).get("nets", [])
    unconnected = bundle.get("unconnected", {})
    sub = getattr(args, "net_command", None) or "list"
    if sub == "list":
        data = {"nets": nets}
    elif sub == "show":
        data = {"nets": [n for n in nets if n.get("name") == args.net]}
    elif sub == "critical":
        critical = [n for n in nets if n.get("name") in {"GND","VBAT_RAW","VBAT_PROTECTED","VSYS_12V","SYS_5V","SYS_3V3","I2C_SCL","I2C_SDA","SPI_SCK","SPI_MOSI","SPI_MISO","VIDEO_MUX_OUT","VIDEO_OSD_IN","VIDEO_OSD_OUT"}]
        data = {"nets": critical}
    elif sub == "single-node":
        data = {"nets": [n for n in nets if n.get("node_count") == 1]}
    elif sub == "unconnected":
        data = unconnected
    else:
        payload = _not_implemented(f"net {sub}", f"Unsupported net subcommand: {sub}")
        _emit(args, payload)
        return EXIT_GENERAL
    payload = _response(command=f"net {sub}", ok=True, status="OK", data=data, next_action="Use net details to inspect connectivity or routing priority.")
    _emit(args, payload)
    return EXIT_OK


def _cmd_ref(args: argparse.Namespace) -> int:
    output_root = Path(args.output).expanduser().resolve()
    bundle = _load_reports_bundle(output_root)
    comps = bundle.get("components", {}).get("components", [])
    pinpad_components = {c.get("ref"): c for c in bundle.get("pin_pad_match", {}).get("components", [])}
    issues = bundle.get("issues", {}).get("issues", [])
    sub = getattr(args, "ref_command", None) or "list"
    if sub == "list":
        data = {"refs": [c.get("ref") for c in comps]}
    else:
        ref = args.ref
        comp = next((c for c in comps if c.get("ref") == ref), {})
        pp = pinpad_components.get(ref, {})
        if sub == "show":
            data = {"component": comp, "pin_pad": pp}
        elif sub == "pins":
            data = {"ref": ref, "pins": pp.get("symbol_pins", [])}
        elif sub == "pads":
            data = {"ref": ref, "pads": pp.get("footprint_pads", [])}
        elif sub == "nets":
            comp_nets = []
            for net in bundle.get("connections", {}).get("nets", []):
                if any(node.get("ref") == ref for node in net.get("nodes", [])):
                    comp_nets.append(net)
            data = {"ref": ref, "nets": comp_nets}
        elif sub == "issues":
            data = {"ref": ref, "issues": [i for i in issues if i.get("ref") == ref]}
        else:
            payload = _not_implemented(f"ref {sub}", f"Unsupported ref subcommand: {sub}")
            _emit(args, payload)
            return EXIT_GENERAL
    payload = _response(command=f"ref {sub}", ok=True, status="OK", data=data, next_action="Use the per-ref view to fix a specific component.")
    _emit(args, payload)
    return EXIT_OK


def _cmd_issue(args: argparse.Namespace) -> int:
    output_root = Path(args.output).expanduser().resolve() if getattr(args, "output", None) else None
    sub = getattr(args, "issue_command", None) or "list"
    if sub == "explain":
        payload = explain_error(args.code)
        _emit(args, _response(command=f"issue explain {args.code}", ok=payload.get("meaning") != "Unknown error code.", status="OK", data=payload, next_action="Use the explanation to guide fixes."))
        return EXIT_OK
    bundle = _load_reports_bundle(output_root)
    entries = bundle.get("issues", {}).get("issues", [])
    if sub == "list":
        data = {"issues": _filter_issue_entries(entries, getattr(args, "severity", None), getattr(args, "code", None), None, None)}
    elif sub == "show":
        data = {"issues": _filter_issue_entries(entries, getattr(args, "severity", None), args.code, args.ref, args.net)}
    elif sub == "by-ref":
        data = {"issues": [i for i in entries if i.get("ref") == args.ref]}
    elif sub == "by-net":
        data = {"issues": [i for i in entries if i.get("net") == args.net]}
    elif sub == "by-code":
        data = {"issues": [i for i in entries if i.get("code") == args.code]}
    else:
        payload = _not_implemented(f"issue {sub}", f"Unsupported issue subcommand: {sub}")
        _emit(args, payload)
        return EXIT_GENERAL
    payload = _response(command=f"issue {sub}", ok=True, status="OK", data=data, next_action="Use filtered issues to drive the next repair step.")
    _emit(args, payload)
    return EXIT_OK


def _cmd_stage(args: argparse.Namespace) -> int:
    sub = getattr(args, "stage_command", None) or "all"
    output_root = Path(args.output).expanduser().resolve() if getattr(args, "output", None) else None
    reports_dir = ensure_reports_dir(output_root) if output_root else ensure_reports_dir(Path.cwd())
    source = resolve_source(args.source, args.project_root, args.entry) if (getattr(args, "source", None) or getattr(args, "project_root", None)) else None
    python_exe = find_python_with_module("skidl", Path(args.project_root).expanduser().resolve() if getattr(args, "project_root", None) else (source.parent if source else Path.cwd())) or "python3"
    if sub == "ast":
        if not source:
            payload = _response(command="stage ast", ok=False, status="FAILED", error={"code":"SOURCE_FILE_NOT_FOUND","message":"Source file required for AST stage.","likely_cause":"Missing --source or --project-root/--entry.","suggested_fix":"Provide a valid source path."}, next_action="Provide source input.")
            _emit(args, payload)
            return EXIT_CHECK_FAILED
        from nexapcb.ast_parser import parse_and_write_report
        report = parse_and_write_report(source, reports_dir / "ast_parse_report.json")
        payload = _response(command="stage ast", ok=True, status="OK", data=report.to_dict() if hasattr(report, "to_dict") else report, reports={"ast_parse_report": str(reports_dir / "ast_parse_report.json")}, next_action="Use the AST report to inspect refs, imports, SKUs, and custom fields.")
        _emit(args, payload)
        return EXIT_OK
    if sub == "skidl-export":
        if not source or not output_root:
            payload = _response(command="stage skidl-export", ok=False, status="FAILED", error={"code":"MISSING_SOURCE_OR_OUTPUT","message":"skidl-export requires source and output.","likely_cause":"Missing --source or --output.","suggested_fix":"Pass both --source and --output."}, next_action="Provide source and output paths.")
            _emit(args, payload)
            return EXIT_CHECK_FAILED
        if not args.project_name:
            payload = _response(command="stage skidl-export", ok=False, status="FAILED", error={"code":"PROJECT_NAME_REQUIRED","message":"--project-name is required for skidl-export.","likely_cause":"Missing project name.","suggested_fix":"Pass --project-name."}, next_action="Provide --project-name.")
            _emit(args, payload)
            return EXIT_CHECK_FAILED
        result = export_project(source, args.project_name, output_root)
        payload = _response(command="stage skidl-export", ok=result.export_ok, status="OK" if result.export_ok else "FAILED", data=result.to_dict(), reports={"skidl_export_report": str(reports_dir / "skidl_export_report.json")}, next_action="Proceed to report generation or full export.")
        _emit(args, payload)
        return EXIT_OK if result.export_ok else EXIT_SKIDL_EXPORT_FAILED
    if sub == "netlist-parse":
        if not output_root:
            payload = _not_implemented("stage netlist-parse", "stage netlist-parse requires --output.")
        else:
            bundle = _load_reports_bundle(output_root)
            payload = _response(command="stage netlist-parse", ok=True, status="OK", data={"netlist": bundle.get("connections", {}), "components": bundle.get("components", {})}, next_action="Use parsed components/connections or proceed to validation.")
        _emit(args, payload)
        return EXIT_OK if payload.get("ok") else EXIT_GENERAL
    if sub == "jlc-import":
        if not output_root:
            payload = _response(command="stage jlc-import", ok=False, status="FAILED", error={"code":"OUTPUT_REQUIRED","message":"stage jlc-import requires --output.","likely_cause":"No output directory was provided.","suggested_fix":"Pass --output pointing at the working/generated project directory."}, next_action="Provide --output.")
            _emit(args, payload)
            return EXIT_GENERAL
        source = source or _recover_source_from_reports(output_root)
        reports_dir = ensure_reports_dir(output_root)
        ast_report = read_json(reports_dir / "ast_parse_report.json", {})
        check_report = read_json(reports_dir / "check_report.json", {})
        component_report = read_json(reports_dir / "component_report.json", {})
        comps = component_report.get("components", [])
        if not comps:
            sku_map = ast_report.get("sku_map") or {}
            if not sku_map and source:
                sku_map = parse_skidl_source(source).sku_map
            if not sku_map:
                payload = _response(command="stage jlc-import", ok=True, status="OK", data={"sku_count": 0, "message": "No LCSC/JLCPCB SKUs found."}, reports={"jlc_import_report": str(reports_dir / "jlc_import_report.json")}, next_action="Proceed without JLC import or add confirmed LCSC SKUs.")
                write_report_json(reports_dir / "jlc_import_report.json", payload["data"])
                write_report_markdown(reports_dir / "jlc_import_report.md", "JLC Import Report", payload["data"])
                _emit(args, payload)
                return EXIT_OK
            comps = [{"ref": ref, "LCSC": sku} for ref, sku in sku_map.items()]
        jlc_info = _detect_optional_module("JLC2KiCadLib")
        if not jlc_info["available"]:
            payload = _response(command="stage jlc-import", ok=False, status="FAILED", error={"code":"JLC2KICADLIB_NOT_FOUND","message":"JLC2KiCadLib is not available.","likely_cause":"Dependency not installed in the current environment.","suggested_fix":"Install JLC2KiCadLib or skip JLC import."}, next_action="Install JLC2KiCadLib or rerun without SKU import.")
            _emit(args, payload)
            return EXIT_ASSET_FAILED
        try:
            data = import_jlc_assets(output_root, comps, allow_generic_fallback=args.allow_generic_fallback, python_exe=python_exe)
            payload = _response(command="stage jlc-import", ok=True, status="OK", data=data, reports={"jlc_import_report": str(reports_dir / "jlc_import_report.json")}, next_action="Proceed to custom-assets or symbol-rewrite if imported symbols/footprints were added.")
            _emit(args, payload)
            return EXIT_OK
        except Exception as exc:
            payload = _response(command="stage jlc-import", ok=False, status="FAILED", error={"code":"LCSC_SKU_IMPORT_FAILED","message":"JLC import stage failed.","likely_cause":"SKU import command failed or produced incomplete outputs.","suggested_fix":"Read jlc_import_report.json and stdout/stderr, then fix the SKU or install missing dependency support."}, issues=[{"severity":"error","stage":"jlc-import","code":"LCSC_SKU_IMPORT_FAILED","message":str(exc),"file":str(output_root),"ref":None,"pin":None,"pad":None,"net":None,"coordinate":None,"likely_cause":"JLC2KiCadLib execution or imported asset localization failed.","suggested_fix":"Inspect the JLC import report and retry with confirmed SKUs.","raw":str(exc)}], reports={"jlc_import_report": str(reports_dir / "jlc_import_report.json")}, next_action="Fix the SKU import failure before proceeding.")
            _emit(args, payload)
            return EXIT_ASSET_FAILED
    if sub == "custom-assets":
        if not output_root:
            payload = _response(command="stage custom-assets", ok=False, status="FAILED", error={"code":"OUTPUT_REQUIRED","message":"stage custom-assets requires --output.","likely_cause":"No output directory was provided.","suggested_fix":"Pass --output pointing at the working/generated project directory."}, next_action="Provide --output.")
            _emit(args, payload)
            return EXIT_GENERAL
        source = source or _recover_source_from_reports(output_root)
        data = localize_custom_assets(source, output_root, args.custom_assets)
        issues = []
        for miss in data.get("missing", []):
            code = miss["field"]
            issues.append({"severity":"error","stage":"custom-assets","code":code if code in {"CUSTOM_SYMBOL_NOT_FOUND","CUSTOM_FOOTPRINT_NOT_FOUND","CUSTOM_MODEL_NOT_FOUND"} else miss["field"],"message":f"Missing custom asset {miss['field']} for {miss['ref']}.","file":miss["path"],"ref":miss["ref"],"pin":None,"pad":None,"net":None,"coordinate":None,"likely_cause":"Bad custom asset path or missing file.","suggested_fix":"Fix the custom asset path or add the missing asset file.","raw":miss})
        ok = not data.get("missing")
        payload = _response(command="stage custom-assets", ok=ok, status="OK" if ok else "FAILED", data=data, issues=issues, reports={"custom_asset_report": str(reports_dir / "custom_asset_report.json")}, next_action="Proceed to symbol-rewrite or fix missing custom assets.")
        _emit(args, payload)
        return EXIT_OK if ok else EXIT_CUSTOM_ASSET_FAILED
    if sub == "kicad-generate":
        if not output_root:
            payload = _response(command="stage kicad-generate", ok=False, status="FAILED", error={"code":"OUTPUT_REQUIRED","message":"stage kicad-generate requires --output.","likely_cause":"No output directory was provided.","suggested_fix":"Pass --output pointing at the working/generated project directory."}, next_action="Provide --output.")
            _emit(args, payload)
            return EXIT_GENERAL
        project_name = _project_name_for_stage(args, output_root)
        if not project_name:
            payload = _response(command="stage kicad-generate", ok=False, status="FAILED", error={"code":"MISSING_PROJECT_NAME","message":"Project name could not be determined.","likely_cause":"Missing --project-name and no existing project metadata found.","suggested_fix":"Pass --project-name explicitly."}, next_action="Provide --project-name.")
            _emit(args, payload)
            return EXIT_KICAD_FAILED
        xml_existing, net_existing = _ensure_canonical_netlist_files(output_root, project_name)
        if not xml_existing:
            payload = _response(command="stage kicad-generate", ok=False, status="FAILED", error={"code":"XML_NOT_FOUND","message":"No XML netlist found for KiCad generation.","likely_cause":"SKiDL export has not produced an XML file yet.","suggested_fix":"Run `nexapcb stage skidl-export` first."}, next_action="Generate the XML netlist first.")
            _emit(args, payload)
            return EXIT_KICAD_FAILED
        if not net_existing:
            payload = _response(command="stage kicad-generate", ok=False, status="FAILED", error={"code":"NETLIST_NOT_FOUND","message":"No .net file found for KiCad generation.","likely_cause":"SKiDL export has not produced a .net file yet.","suggested_fix":"Run `nexapcb stage skidl-export` first."}, next_action="Generate the .net file first.")
            _emit(args, payload)
            return EXIT_KICAD_FAILED
        source = source or _recover_source_from_reports(output_root)
        if not source:
            payload = _response(command="stage kicad-generate", ok=False, status="FAILED", error={"code":"MISSING_PREREQUISITE_AST_REPORT","message":"Could not recover source path for KiCad generation.","likely_cause":"ast_parse_report.json/check_report.json missing or source path no longer exists.","suggested_fix":"Pass --source explicitly or rerun `nexapcb stage ast` / `nexapcb check all`."}, next_action="Provide --source or regenerate AST/check reports.")
            _emit(args, payload)
            return EXIT_KICAD_FAILED
        paths = make_project_paths(output_root, project_name)
        paths.ensure_all()
        _write_fp_lib_table(paths, portable=False)
        _write_sym_lib_table(paths)
        _generate_schematic_inproc(source, paths, project_name)
        _sanitize_kicad_artifacts(paths)
        _write_kicad_pro(paths)
        pcb_ok, pcb_log = _generate_pcb_with_kicad_python(source, paths, project_name)
        if (Path("/Users/surajbhati/Desktop/temp/pcb/n-defender-kicad/N-defnder-local.pretty")).exists():
            copy_dir(Path("/Users/surajbhati/Desktop/temp/pcb/n-defender-kicad/N-defnder-local.pretty"), paths.footprints_dir / "N-defnder-local.pretty")
        _sanitize_kicad_artifacts(paths)
        _tune_project_rules(paths.kicad_pro)
        _add_board_outline(paths.kicad_pcb)
        _write_fp_lib_table(paths, portable=True)
        write_text(paths.logs_dir / "pcb_generation.log", pcb_log)
        data = {
            "project_name": project_name,
            "kicad_pro": str(paths.kicad_pro),
            "kicad_sch": str(paths.kicad_sch),
            "kicad_pcb": str(paths.kicad_pcb),
            "pcb_generation_ok": pcb_ok,
        }
        write_report_json(reports_dir / "kicad_generation_report.json", data)
        write_report_markdown(reports_dir / "kicad_generation_report.md", "KiCad Generation Report", data)
        payload = _response(command="stage kicad-generate", ok=paths.kicad_pro.exists() and paths.kicad_sch.exists() and paths.kicad_pcb.exists(), status="OK" if paths.kicad_pro.exists() and paths.kicad_sch.exists() and paths.kicad_pcb.exists() else "FAILED", data=data, reports={"kicad_generation_report": str(reports_dir / "kicad_generation_report.json")}, next_action="Proceed to symbol-rewrite or validation.")
        _emit(args, payload)
        return EXIT_OK if payload.get("ok") else EXIT_KICAD_FAILED
    if sub == "symbol-rewrite":
        if not output_root:
            payload = _response(command="stage symbol-rewrite", ok=False, status="FAILED", error={"code":"OUTPUT_REQUIRED","message":"stage symbol-rewrite requires --output.","likely_cause":"No output directory was provided.","suggested_fix":"Pass --output pointing at the working/generated project directory."}, next_action="Provide --output.")
            _emit(args, payload)
            return EXIT_GENERAL
        project_name = _project_name_for_stage(args, output_root)
        if not project_name:
            payload = _response(command="stage symbol-rewrite", ok=False, status="FAILED", error={"code":"MISSING_PROJECT_NAME","message":"Project name could not be determined.","likely_cause":"Missing --project-name and no existing project metadata found.","suggested_fix":"Pass --project-name explicitly."}, next_action="Provide --project-name.")
            _emit(args, payload)
            return EXIT_KICAD_FAILED
        sch = output_root / f"{project_name}.kicad_sch"
        if not sch.exists():
            payload = _response(command="stage symbol-rewrite", ok=False, status="FAILED", error={"code":"KICAD_SCHEMATIC_NOT_FOUND","message":"KiCad schematic not found for symbol rewrite.","likely_cause":"kicad-generate has not been run yet.","suggested_fix":"Run `nexapcb stage kicad-generate` first."}, next_action="Generate the schematic first.")
            _emit(args, payload)
            return EXIT_KICAD_FAILED
        from nexapcb.assets import refresh_project_lib_tables, _rewrite_symbol_instances, _extract_custom_props_from_schematic
        jlc_report = read_json(reports_dir / "jlc_import_report.json", {})
        custom_props = _extract_custom_props_from_schematic(sch)
        replacement_map = {}
        for item in jlc_report.get("succeeded", []):
            ref = item.get("ref")
            if not ref:
                continue
            replacement_map[ref] = {"lib_id": f'{item.get("symbol_lib")}:{item.get("symbol_name")}' if item.get("symbol_lib") and item.get("symbol_name") else None, "footprint": item.get("footprint"), "model": item.get("model")}
        for ref, props in custom_props.items():
            if props.get("CUSTOM_SYMBOL") and props.get("CUSTOM_SYMBOL_NAME"):
                lib_name = Path(props["CUSTOM_SYMBOL"]).stem
                replacement_map.setdefault(ref, {})["lib_id"] = f"{lib_name}:{props['CUSTOM_SYMBOL_NAME']}"
            if props.get("CUSTOM_FOOTPRINT"):
                replacement_map.setdefault(ref, {})["custom_footprint_prop"] = props["CUSTOM_FOOTPRINT"]
            if props.get("CUSTOM_MODEL"):
                replacement_map.setdefault(ref, {})["model"] = props["CUSTOM_MODEL"]
        before = read_text(sch).count('(lib_id "Device:') + read_text(sch).count('(lib_id "Connector:') + read_text(sch).count('(lib_id "power:')
        changed = _rewrite_symbol_instances(sch, replacement_map) if replacement_map else 0
        refresh_project_lib_tables(output_root)
        text = read_text(sch)
        after = text.count('(lib_id "Device:') + text.count('(lib_id "Connector:') + text.count('(lib_id "power:')
        imported_applied = len([i for i in jlc_report.get("succeeded", []) if i.get("ref")])
        custom_applied = len([r for r, p in custom_props.items() if p.get("CUSTOM_SYMBOL") and p.get("CUSTOM_SYMBOL_NAME")])
        data = {
            "schematic_symbols_total": text.count("(symbol "),
            "generic_before": before,
            "generic_after": after,
            "imported_symbols_applied": imported_applied,
            "custom_symbols_applied": custom_applied,
            "unresolved_symbols": max(after, 0),
            "changed_instances": changed,
        }
        write_report_json(reports_dir / "schematic_symbol_rewrite_report.json", data)
        write_report_markdown(reports_dir / "schematic_symbol_rewrite_report.md", "Schematic Symbol Rewrite Report", data)
        payload = _response(command="stage symbol-rewrite", ok=True, status="OK", data=data, reports={"schematic_symbol_rewrite_report": str(reports_dir / "schematic_symbol_rewrite_report.json")}, next_action="Proceed to validate/erc/drc or inspect remaining generic symbols.")
        _emit(args, payload)
        return EXIT_OK
    if sub == "validate":
        if not output_root:
            payload = _not_implemented("stage validate", "stage validate requires --output.")
        else:
            payload = _response(command="stage validate", ok=True, status="OK", data=read_json(reports_dir / "validation_report.json", {}), reports={"validation_report": str(reports_dir / "validation_report.json")}, next_action="Use validation to decide strictness or next fix loop.")
        _emit(args, payload)
        return EXIT_OK if payload.get("ok") else EXIT_GENERAL
    if sub == "all":
        if not source or not output_root or not args.project_name:
            payload = _response(command="stage all", ok=False, status="FAILED", error={"code":"MISSING_EXPORT_ARGUMENTS","message":"stage all requires source, project-name, and output.","likely_cause":"Missing one or more required arguments.","suggested_fix":"Pass --source/--project-root+--entry, --project-name, and --output."}, next_action="Provide full export arguments.")
            _emit(args, payload)
            return EXIT_CHECK_FAILED
        return _cmd_export(args)
    payload = _not_implemented(f"stage {sub}", f"Stage `{sub}` is not fully implemented yet.")
    _emit(args, payload)
    return EXIT_GENERAL


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nexapcb", description="CLI-only SKiDL-to-KiCad automation tool.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor")
    p.add_argument("--output")
    p.add_argument("--source")
    p.add_argument("--kicad-cli")
    p.add_argument("--format", choices=["json", "text"], default="text")
    p.set_defaults(func=_cmd_doctor)

    p = sub.add_parser("version")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_version)

    p = sub.add_parser("explain")
    p.add_argument("code", nargs="?")
    p.add_argument("--list", action="store_true")
    p.set_defaults(func=_cmd_explain)

    p = sub.add_parser("init")
    p.add_argument("--project-root", required=True)
    p.add_argument("--project-name", required=True)
    p.set_defaults(func=_cmd_init)

    p = sub.add_parser("check")
    p.add_argument("check_command", nargs="?", choices=["source", "syntax", "imports", "skidl", "assets", "paths", "all"], default="all")
    p.add_argument("--source")
    p.add_argument("--project-root")
    p.add_argument("--entry")
    p.add_argument("--output")
    p.add_argument("--custom-assets")
    p.add_argument("--format", choices=["json", "md", "text"], default="text")
    p.set_defaults(func=_cmd_check)

    p = sub.add_parser("export")
    p.add_argument("--source")
    p.add_argument("--project-root")
    p.add_argument("--entry")
    p.add_argument("--project-name", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--custom-assets")
    p.add_argument("--pin-map")
    p.add_argument("--allow-generic-fallback", action="store_true")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--allow-issues", action="store_true")
    p.set_defaults(func=_cmd_export)

    p = sub.add_parser("report")
    p.add_argument("report_command", nargs="?", choices=["summary", "components", "connections", "issues", "validation", "erc", "drc", "unconnected", "routing", "board-connectivity", "pin-pad", "assets", "final", "all", "nets", "footprints"], default=None)
    p.add_argument("--output", required=True)
    p.add_argument("--format", choices=["json", "md", "text"], default="text")
    p.add_argument("--report", choices=["summary", "components", "connections", "nets", "footprints", "issues", "validation", "erc", "drc", "pin-labels", "pin-pad-match", "unconnected", "routing-todo", "routing", "board-connectivity", "assets", "final-result", "final", "all"], default="summary")
    p.add_argument("--save", action="store_true")
    p.add_argument("--severity")
    p.add_argument("--code")
    p.add_argument("--ref")
    p.add_argument("--net")
    p.set_defaults(func=_cmd_report)

    p = sub.add_parser("erc")
    p.add_argument("erc_command", nargs="?", choices=["run", "parse", "report"], default="run")
    p.add_argument("--output", required=True)
    p.add_argument("--input")
    p.add_argument("--format", choices=["json", "md", "text"], default="text")
    p.add_argument("--kicad-cli")
    p.add_argument("--allow-errors", action="store_true")
    p.set_defaults(func=_cmd_erc)

    p = sub.add_parser("drc")
    p.add_argument("drc_command", nargs="?", choices=["run", "parse", "report"], default="run")
    p.add_argument("--output", required=True)
    p.add_argument("--input")
    p.add_argument("--format", choices=["json", "md", "text"], default="text")
    p.add_argument("--kicad-cli")
    p.add_argument("--allow-errors", action="store_true")
    p.set_defaults(func=_cmd_drc)

    p = sub.add_parser("inspect")
    p.add_argument("inspect_command", nargs="?", choices=["source", "output", "symbols", "footprints", "models", "nets", "refs", "paths", "pin-labels", "pin-pad-match"], default=None)
    p.add_argument("--source")
    p.add_argument("--project-root")
    p.add_argument("--entry")
    p.add_argument("--output")
    p.add_argument("--format", choices=["json", "md", "text"], default="text")
    p.add_argument("--net")
    p.add_argument("--ref")
    p.add_argument("--pin-labels", action="store_true")
    p.add_argument("--pin-pad-match", action="store_true")
    p.set_defaults(func=_cmd_inspect)

    p = sub.add_parser("examples")
    p.add_argument("--create", choices=list_examples())
    p.add_argument("--output", default=".")
    p.set_defaults(func=_cmd_examples)

    p = sub.add_parser("help")
    p.add_argument("topic", nargs="?")
    p.set_defaults(func=_cmd_help)

    p = sub.add_parser("stage")
    p.add_argument("stage_command", nargs="?", choices=["ast", "skidl-export", "netlist-parse", "jlc-import", "custom-assets", "kicad-generate", "symbol-rewrite", "validate", "all"], default="all")
    p.add_argument("--source")
    p.add_argument("--project-root")
    p.add_argument("--entry")
    p.add_argument("--project-name")
    p.add_argument("--output")
    p.add_argument("--custom-assets")
    p.add_argument("--allow-generic-fallback", action="store_true")
    p.add_argument("--format", choices=["json", "md", "text"], default="text")
    p.add_argument("--pin-map")
    p.set_defaults(func=_cmd_stage)

    p = sub.add_parser("part")
    part_sub = p.add_subparsers(dest="part_command", required=True)

    sp = part_sub.add_parser("lookup")
    sp.add_argument("--sku", required=True)
    sp.add_argument("--mpn")
    sp.add_argument("--ref", default="U1")
    sp.add_argument("--output")
    sp.add_argument("--format", choices=["json", "md", "text"], default="text")
    sp.set_defaults(func=_cmd_part_lookup)

    sp = part_sub.add_parser("inspect")
    sp.add_argument("--symbol")
    sp.add_argument("--symbol-name")
    sp.add_argument("--footprint")
    sp.add_argument("--model")
    sp.add_argument("--output")
    sp.add_argument("--mpn")
    sp.add_argument("--sku")
    sp.add_argument("--format", choices=["json", "md", "text"], default="text")
    sp.set_defaults(func=_cmd_part_inspect)

    sp = part_sub.add_parser("compare")
    sp.add_argument("--symbol", required=True)
    sp.add_argument("--symbol-name")
    sp.add_argument("--footprint", required=True)
    sp.add_argument("--model")
    sp.add_argument("--output")
    sp.add_argument("--mpn")
    sp.add_argument("--sku")
    sp.add_argument("--allow-fuzzy", action="store_true")
    sp.add_argument("--format", choices=["json", "md", "text"], default="text")
    sp.set_defaults(func=_cmd_part_compare)

    sp = part_sub.add_parser("request")
    sp.add_argument("--sku")
    sp.add_argument("--mpn")
    sp.add_argument("--symbol")
    sp.add_argument("--symbol-name")
    sp.add_argument("--footprint")
    sp.add_argument("--model")
    sp.add_argument("--output")
    sp.add_argument("--format", choices=["json", "md", "text"], default="text")
    sp.set_defaults(func=_cmd_part_request)

    sp = part_sub.add_parser("report")
    sp.add_argument("--input", required=True)
    sp.add_argument("--format", choices=["json", "md", "text"], default="text")
    sp.set_defaults(func=_cmd_part_report)

    sp = part_sub.add_parser("pins")
    sp.add_argument("--symbol", required=True)
    sp.add_argument("--symbol-name", required=True)
    sp.add_argument("--format", choices=["json", "md", "text"], default="text")
    sp.set_defaults(func=_cmd_part_pins)

    sp = part_sub.add_parser("pads")
    sp.add_argument("--footprint", required=True)
    sp.add_argument("--format", choices=["json", "md", "text"], default="text")
    sp.set_defaults(func=_cmd_part_pads)

    sp = part_sub.add_parser("skidl-snippet")
    sp.add_argument("--input", required=True)
    sp.add_argument("--ref")
    sp.add_argument("--format", choices=["json", "md", "text"], default="text")
    sp.set_defaults(func=_cmd_part_skidl_snippet)

    sp = part_sub.add_parser("model-check")
    sp.add_argument("--footprint")
    sp.add_argument("--model", required=True)
    sp.add_argument("--format", choices=["json", "md", "text"], default="text")
    sp.set_defaults(func=_cmd_part_model_check)

    p = sub.add_parser("asset")
    p.add_argument("asset_command", nargs="?", choices=["scan", "localize", "check-paths", "report"], default="scan")
    p.add_argument("--source")
    p.add_argument("--project-root")
    p.add_argument("--entry")
    p.add_argument("--output")
    p.add_argument("--custom-assets")
    p.add_argument("--format", choices=["json", "md", "text"], default="text")
    p.set_defaults(func=_cmd_asset)

    p = sub.add_parser("net")
    p.add_argument("net_command", nargs="?", choices=["list", "show", "critical", "single-node", "unconnected"], default="list")
    p.add_argument("--output", required=True)
    p.add_argument("--net")
    p.add_argument("--format", choices=["json", "md", "text"], default="text")
    p.set_defaults(func=_cmd_net)

    p = sub.add_parser("ref")
    p.add_argument("ref_command", nargs="?", choices=["list", "show", "pins", "pads", "nets", "issues"], default="list")
    p.add_argument("--output", required=True)
    p.add_argument("--ref")
    p.add_argument("--format", choices=["json", "md", "text"], default="text")
    p.set_defaults(func=_cmd_ref)

    p = sub.add_parser("issue")
    p.add_argument("issue_command", nargs="?", choices=["list", "show", "by-ref", "by-net", "by-code", "explain"], default="list")
    p.add_argument("--output")
    p.add_argument("--severity")
    p.add_argument("--code")
    p.add_argument("--ref")
    p.add_argument("--net")
    p.add_argument("--format", choices=["json", "md", "text"], default="text")
    p.set_defaults(func=_cmd_issue)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
