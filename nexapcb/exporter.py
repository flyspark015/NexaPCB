from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import sysconfig
from dataclasses import asdict, dataclass
from pathlib import Path
from pprint import pformat
import math

from nexapcb.ast_parser import parse_and_write_report
from nexapcb.config import make_project_paths
from nexapcb.reports import write_report_json, write_report_markdown
from nexapcb.utils.fs import copy_dir, copy_file, find_absolute_path_occurrences, read_text, write_text
from nexapcb.utils.process import run_command
from nexapcb.xml_parser import normalize_skidl_xml, write_xml_parse_report


KICAD_APP_ROOT = Path("/Volumes/ToyBook/KiCad/KiCad.app")
KICAD_SYMBOL_DIR = KICAD_APP_ROOT / "Contents" / "SharedSupport" / "symbols"
KICAD_FOOTPRINT_DIR = KICAD_APP_ROOT / "Contents" / "SharedSupport" / "footprints"
KICAD_CLI = KICAD_APP_ROOT / "Contents" / "MacOS" / "kicad-cli"
KICAD_PYTHON = KICAD_APP_ROOT / "Contents" / "Frameworks" / "Python.framework" / "Versions" / "Current" / "bin" / "python3"
LOCAL_PRETTY = Path("/Users/surajbhati/Desktop/temp/pcb/n-defender-kicad/N-defnder-local.pretty")
STANDARD_FOOTPRINT_LIBS = [
    "Package_SO",
    "Package_DFN_QFN",
    "Package_TO_SOT_SMD",
    "RF_Module",
    "LED_SMD",
    "Connector_AMASS",
    "Connector_USB",
    "Connector_JST",
    "Connector_PinHeader_2.54mm",
    "Buzzer_Beeper",
    "Package_QFP",
    "Package_SON",
    "Connector_Coaxial",
    "Diode_SMD",
    "Inductor_SMD",
    "Capacitor_SMD",
    "Resistor_SMD",
    "Connector_Card",
    "TestPoint",
    "Button_Switch_SMD",
]


@dataclass
class ExportResult:
    source: str
    project_root: str
    project_name: str
    kicad_pro: str
    kicad_sch: str
    kicad_pcb: str
    net_file: str
    xml_file: str
    reports_dir: str
    ast_ok: bool
    export_ok: bool
    validation: dict

    def to_dict(self) -> dict:
        return asdict(self)


def _set_kicad_env() -> None:
    for key in ["KICAD_SYMBOL_DIR", "KICAD6_SYMBOL_DIR", "KICAD7_SYMBOL_DIR", "KICAD8_SYMBOL_DIR", "KICAD9_SYMBOL_DIR"]:
        os.environ[key] = str(KICAD_SYMBOL_DIR)


def _load_source_module(source: Path):
    source_dir = str(source.parent)
    old_cwd = os.getcwd()
    inserted = False
    if source_dir not in sys.path:
        sys.path.insert(0, source_dir)
        inserted = True
    os.chdir(source_dir)
    spec = importlib.util.spec_from_file_location("nexa_source_module", source)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    try:
        spec.loader.exec_module(module)
    finally:
        os.chdir(old_cwd)
        if inserted and sys.path and sys.path[0] == source_dir:
            sys.path.pop(0)
    return module


def _count_xml_components(xml_file: Path) -> int:
    text = read_text(xml_file)
    return text.count("<comp ")


def _count_schematic_symbols(sch_file: Path) -> int:
    return read_text(sch_file).count("(symbol ")


def _count_board_footprints(pcb_file: Path) -> int:
    if not pcb_file.exists():
        return 0
    return read_text(pcb_file).count("(footprint ")


def _count_nets_from_xml(xml_file: Path) -> int:
    text = read_text(xml_file)
    return text.count("<net ")


def _write_kicad_pro(paths) -> None:
    data = {
        "board": {"design_settings": {}, "layer_presets": [], "viewports": []},
        "boards": [],
        "cvpcb": {},
        "erc": {},
        "libraries": {
            "pinned_footprint_libs": [],
            "pinned_symbol_libs": [],
        },
        "meta": {"filename": paths.kicad_pro.name, "version": 1},
        "net_settings": {
            "classes": [
                {
                    "name": "Default",
                    "track_width": 0.2,
                    "clearance": 0.1,
                    "via_diameter": 0.6,
                    "via_drill": 0.3,
                    "microvia_diameter": 0.3,
                    "microvia_drill": 0.1,
                    "diff_pair_width": 0.2,
                    "diff_pair_gap": 0.25,
                    "diff_pair_via_gap": 0.25,
                    "bus_width": 12,
                    "wire_width": 6,
                    "line_style": 0,
                    "pcb_color": "rgba(0, 0, 0, 0.000)",
                    "schematic_color": "rgba(0, 0, 0, 0.000)",
                    "priority": 2147483647,
                    "tuning_profile": "",
                }
            ],
            "last_net_id": 0,
            "meta": {"version": 5},
            "net_colors": None,
            "netclass_assignments": None,
            "netclass_patterns": [],
        },
        "pcbnew": {},
        "schematic": {
            "annotate_start_num": 0,
            "drawing": {"default_line_thickness": 6.0, "default_text_size": 50.0},
        },
        "sheets": [],
        "text_variables": {},
    }
    write_text(paths.kicad_pro, json.dumps(data, indent=2))


def _write_fp_lib_table(paths, portable: bool = True) -> None:
    libs: list[str] = []
    for lib in STANDARD_FOOTPRINT_LIBS:
        uri = f"${{KICAD9_FOOTPRINT_DIR}}/{lib}.pretty" if portable else str(KICAD_FOOTPRINT_DIR / f"{lib}.pretty")
        libs.append(f'  (lib (name "{lib}")(type "KiCad")(uri "{uri}")(options "")(descr "KiCad standard library"))')
    libs.append('  (lib (name "N-defnder-local")(type "KiCad")(uri "${KIPRJMOD}/footprints/N-defnder-local.pretty")(options "")(descr "Local custom footprints"))')
    table = "(fp_lib_table\n" + "\n".join(libs) + "\n)\n"
    write_text(paths.root / "fp-lib-table", table)


def _write_sym_lib_table(paths) -> None:
    table = (
        "(sym_lib_table\n"
        '  (lib (name "NexaPCB_Embedded")(type "KiCad")(uri "${KIPRJMOD}/symbols/NexaPCB_Embedded.kicad_sym")(options "")(descr "Generated embedded symbols"))\n'
        ")\n"
    )
    write_text(paths.root / "sym-lib-table", table)


ABS_SYMBOL_DEF_RE = re.compile(
    r'(\(symbol\s+")(?:[A-Za-z]:\\\\|/)[^"\n)]*/symbols/([^/":]+)(?:\.kicad_sym)?:([^"]+)(")'
)
ABS_LIB_ID_RE = re.compile(
    r'(\(lib_id\s+")(?:[A-Za-z]:\\\\|/)[^"\n)]*/symbols/([^/":]+)(?:\.kicad_sym)?:([^"]+)(")'
)
ABS_CUSTOM_PROP_RE = re.compile(
    r'(\(property\s+"CUSTOM_SYMBOL"\s+")((?:[A-Za-z]:\\\\|/)[^"]+?)(/)??([^/"]+\.kicad_sym)(")'
)
AT_COORD_RE = re.compile(r'(\(at\s+)([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)(\s+[-+]?\d*\.?\d+)?(\))')
PAIR_COORD_RE = re.compile(r'(\((?:start|end|xy)\s+)([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)(\))')
SYMBOL_DEF_NAME_RE = re.compile(r'\(symbol\s+"([^"]+:[^"]+)"')


def _fmt_coord(value: float) -> str:
    txt = f"{value:.3f}".rstrip("0").rstrip(".")
    return txt if txt not in {"-0", ""} else "0"


def _extract_block(text: str, start_marker: str) -> tuple[str, int, int] | None:
    start = text.find(start_marker)
    if start == -1:
        return None
    depth = 0
    for idx in range(start, len(text)):
        if text[idx] == "(":
            depth += 1
        elif text[idx] == ")":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1], start, idx + 1
    return None


def _snap_coord(value: float, grid: float = 1.27) -> float:
    return round(value / grid) * grid


def _externalize_embedded_symbols(paths) -> None:
    if not paths.kicad_sch.exists():
        return
    text = read_text(paths.kicad_sch)
    block_info = _extract_block(text, "(lib_symbols")
    if not block_info:
        return
    block, start, end = block_info
    inner = block[len("(lib_symbols") : -1].strip()
    symbol_names = sorted(set(SYMBOL_DEF_NAME_RE.findall(inner)), key=len, reverse=True)
    if not symbol_names:
        return

    rewritten_inner = inner
    rewritten_pre = text[:start]
    rewritten_post = text[end:]
    for old_name in symbol_names:
        new_name = f'NexaPCB_Embedded:{old_name.split(":", 1)[1]}'
        rewritten_inner = rewritten_inner.replace(f'(symbol "{old_name}"', f'(symbol "{new_name}"')
        rewritten_pre = rewritten_pre.replace(f'(lib_id "{old_name}"', f'(lib_id "{new_name}"')
        rewritten_post = rewritten_post.replace(f'(lib_id "{old_name}"', f'(lib_id "{new_name}"')

    rewritten_block = "(lib_symbols\n" + rewritten_inner + "\n)"
    write_text(paths.kicad_sch, rewritten_pre + rewritten_block + rewritten_post)

    symbols_dir = paths.root / "symbols"
    symbols_dir.mkdir(parents=True, exist_ok=True)
    write_text(
        symbols_dir / "NexaPCB_Embedded.kicad_sym",
        '(kicad_symbol_lib (version 20231120) (generator "nexapcb")\n'
        + rewritten_inner
        + "\n)\n",
    )


def _snap_schematic_grid(sch_file: Path, grid: float = 1.27) -> None:
    if not sch_file.exists():
        return
    text = read_text(sch_file)
    block_info = _extract_block(text, "(lib_symbols")
    if block_info:
        _, start, end = block_info
        pre = text[:start]
        lib_block = text[start:end]
        post = text[end:]
    else:
        pre, lib_block, post = text, "", ""

    def repl_at(match: re.Match[str]) -> str:
        x = _fmt_coord(_snap_coord(float(match.group(2)), grid))
        y = _fmt_coord(_snap_coord(float(match.group(3)), grid))
        angle = match.group(4) or ""
        return f"{match.group(1)}{x} {y}{angle}{match.group(5)}"

    def repl_pair(match: re.Match[str]) -> str:
        x = _fmt_coord(_snap_coord(float(match.group(2)), grid))
        y = _fmt_coord(_snap_coord(float(match.group(3)), grid))
        return f"{match.group(1)}{x} {y}{match.group(4)}"

    pre = AT_COORD_RE.sub(repl_at, pre)
    pre = PAIR_COORD_RE.sub(repl_pair, pre)
    post = AT_COORD_RE.sub(repl_at, post)
    post = PAIR_COORD_RE.sub(repl_pair, post)
    write_text(sch_file, pre + lib_block + post)


def _sanitize_kicad_artifacts(paths) -> None:
    if paths.kicad_sch.exists():
        text = read_text(paths.kicad_sch)
        text = ABS_SYMBOL_DEF_RE.sub(lambda m: f'{m.group(1)}{m.group(2)}:{m.group(3)}{m.group(4)}', text)
        text = ABS_LIB_ID_RE.sub(lambda m: f'{m.group(1)}{m.group(2)}:{m.group(3)}{m.group(4)}', text)
        text = ABS_CUSTOM_PROP_RE.sub(lambda m: f'{m.group(1)}${{KIPRJMOD}}/symbols/{m.group(4)}{m.group(5)}', text)
        write_text(paths.kicad_sch, text)
        _externalize_embedded_symbols(paths)
        _snap_schematic_grid(paths.kicad_sch)


def _tune_project_rules(kicad_pro: Path) -> None:
    if not kicad_pro.exists():
        return
    try:
        data = json.loads(read_text(kicad_pro))
    except Exception:
        return

    board = data.setdefault("board", {})
    design = board.setdefault("design_settings", {})
    defaults = design.setdefault("defaults", {})
    zones = defaults.setdefault("zones", {})
    zones["min_clearance"] = 0.1

    rules = design.setdefault("rules", {})
    rules["min_clearance"] = 0.1
    rules["min_connection"] = 0.0
    rules["min_copper_edge_clearance"] = 0.2
    rules["min_hole_clearance"] = 0.2
    rules["min_hole_to_hole"] = 0.2
    rules["min_microvia_diameter"] = 0.2
    rules["min_microvia_drill"] = 0.1
    rules["min_through_hole_diameter"] = 0.2
    rules["min_track_width"] = 0.15
    rules["min_via_diameter"] = 0.45

    net_settings = data.setdefault("net_settings", {})
    classes = net_settings.setdefault("classes", [])
    if not classes:
        classes.append({"name": "Default"})
    for cls in classes:
        cls["clearance"] = 0.1
        cls["track_width"] = 0.15
        cls["via_diameter"] = 0.45
        cls["via_drill"] = 0.2
        cls["microvia_diameter"] = 0.2
        cls["microvia_drill"] = 0.1

    write_text(kicad_pro, json.dumps(data, indent=2))


def _add_board_outline(pcb_file: Path, margin: float = 5.0) -> None:
    if not pcb_file.exists():
        return
    text = read_text(pcb_file)
    if 'Edge.Cuts' in text and ('(gr_line' in text or '(gr_rect' in text):
        return

    at_matches = re.findall(r'\(footprint\s+"[^"]+"\s.*?\(at\s+([-+]?\d*\.?\d+)\s+([-+]?\d*\.?\d+)', text, re.S)
    if not at_matches:
        return
    xs = [float(x) for x, _ in at_matches]
    ys = [float(y) for _, y in at_matches]
    min_x = math.floor((min(xs) - margin) * 1000) / 1000
    max_x = math.ceil((max(xs) + margin) * 1000) / 1000
    min_y = math.floor((min(ys) - margin) * 1000) / 1000
    max_y = math.ceil((max(ys) + margin) * 1000) / 1000

    uid = [str(uuid) for uuid in (
        __import__("uuid").uuid4(),
        __import__("uuid").uuid4(),
        __import__("uuid").uuid4(),
        __import__("uuid").uuid4(),
    )]
    outline = f"""
\t(gr_line
\t\t(start {min_x} {min_y})
\t\t(end {max_x} {min_y})
\t\t(stroke (width 0.05) (type solid))
\t\t(layer "Edge.Cuts")
\t\t(uuid "{uid[0]}")
\t)
\t(gr_line
\t\t(start {max_x} {min_y})
\t\t(end {max_x} {max_y})
\t\t(stroke (width 0.05) (type solid))
\t\t(layer "Edge.Cuts")
\t\t(uuid "{uid[1]}")
\t)
\t(gr_line
\t\t(start {max_x} {max_y})
\t\t(end {min_x} {max_y})
\t\t(stroke (width 0.05) (type solid))
\t\t(layer "Edge.Cuts")
\t\t(uuid "{uid[2]}")
\t)
\t(gr_line
\t\t(start {min_x} {max_y})
\t\t(end {min_x} {min_y})
\t\t(stroke (width 0.05) (type solid))
\t\t(layer "Edge.Cuts")
\t\t(uuid "{uid[3]}")
\t)
"""
    txt = text.rstrip()
    if txt.endswith(")"):
        txt = txt[:-1] + outline + "\n)\n"
    else:
        txt += outline
    write_text(pcb_file, txt)


def _run_source_exports(source: Path, python_exe: str):
    env = os.environ.copy()
    for key in ["KICAD_SYMBOL_DIR", "KICAD6_SYMBOL_DIR", "KICAD7_SYMBOL_DIR", "KICAD8_SYMBOL_DIR", "KICAD9_SYMBOL_DIR"]:
        env[key] = str(KICAD_SYMBOL_DIR)
    env["PYTHONPATH"] = str(source.parent) + os.pathsep + env.get("PYTHONPATH", "")
    cmd = [python_exe, str(source)]
    return run_command(cmd, cwd=source.parent, timeout=600, env=env)


def _move_generated_export(source_dir: Path, dst: Path, suffix: str) -> None:
    matches = sorted(source_dir.glob(f"*{suffix}"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not matches:
        raise FileNotFoundError(f"{suffix.upper().lstrip('.')}_NOT_FOUND_IN:{source_dir}")
    matches[0].replace(dst)


def _generate_schematic_inproc(source: Path, paths, project_name: str):
    _set_kicad_env()
    module = _load_source_module(source)
    if hasattr(module, "build_design"):
        module.build_design()
    from skidl import ERC, generate_schematic
    ERC()
    generate_schematic(
        filepath=str(paths.root),
        top_name=project_name,
        title=project_name,
        flatness=1.0,
        auto_stub=True,
        auto_stub_fanout=1,
        auto_stub_max_wire_pins=0,
        auto_stub_max_wire_dist=0,
        auto_stub_fallback="labels",
    )


def _generate_pcb_with_kicad_python(source: Path, paths, project_name: str) -> tuple[bool, str]:
    env = os.environ.copy()
    venv_site = sysconfig.get_paths().get("purelib", "")
    extra_paths = [str(source.parent)]
    if venv_site:
        extra_paths.append(venv_site)
    if env.get("PYTHONPATH"):
        extra_paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(extra_paths)
    inline = f"""
import os, importlib.util, sys
from pathlib import Path
for key in ['KICAD_SYMBOL_DIR','KICAD6_SYMBOL_DIR','KICAD7_SYMBOL_DIR','KICAD8_SYMBOL_DIR','KICAD9_SYMBOL_DIR']:
    os.environ[key] = {str(KICAD_SYMBOL_DIR)!r}
src = Path({str(source)!r})
sys.path.insert(0, str(src.parent))
os.chdir(str(src.parent))
spec = importlib.util.spec_from_file_location('nexa_source_module_pcb', src)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
if hasattr(mod, 'build_design'):
    mod.build_design()
from skidl import generate_pcb
fp_libs = {pformat([str(KICAD_FOOTPRINT_DIR), str(paths.footprints_dir)])}
generate_pcb(file_={str(paths.kicad_pcb)!r}, fp_libs=fp_libs)
print('PCB_DONE')
"""
    result = run_command([str(KICAD_PYTHON), "-c", inline], cwd=paths.root, timeout=900, env=env)
    return result.ok and paths.kicad_pcb.exists(), result.stdout + "\n" + result.stderr


def export_project(source: str | Path, project_name: str, project_root: str | Path) -> ExportResult:
    source = Path(source).expanduser().resolve()
    paths = make_project_paths(project_root, project_name)
    paths.ensure_all()

    if LOCAL_PRETTY.exists():
        copy_dir(LOCAL_PRETTY, paths.footprints_dir / "N-defnder-local.pretty")

    _write_fp_lib_table(paths, portable=False)
    _write_sym_lib_table(paths)

    ast_result = parse_and_write_report(source, paths.reports_dir / "ast_parse_report.json")

    source_export = _run_source_exports(source, sys.executable)
    if not source_export.ok:
        raise RuntimeError(f"SKiDL source export failed:\nCMD: {' '.join(source_export.command)}\nSTDOUT:\n{source_export.stdout}\nSTDERR:\n{source_export.stderr}")
    _move_generated_export(source.parent, paths.net_file, ".net")
    _move_generated_export(source.parent, paths.xml_file, ".xml")
    normalize_skidl_xml(paths.xml_file)
    xml_report = write_xml_parse_report(paths.xml_file, paths.reports_dir)

    _generate_schematic_inproc(source, paths, project_name)
    _sanitize_kicad_artifacts(paths)
    _write_kicad_pro(paths)

    pcb_ok, pcb_log = _generate_pcb_with_kicad_python(source, paths, project_name)
    if not pcb_ok:
        placeholder = f"""(kicad_pcb (version 20221018) (generator \"nexapcb\")\n  (general (thickness 1.6))\n  (paper \"A4\")\n  (layers\n    (0 \"F.Cu\" signal)\n    (31 \"B.Cu\" signal)\n    (36 \"B.SilkS\" user)\n    (37 \"F.SilkS\" user)\n    (38 \"B.Mask\" user)\n    (39 \"F.Mask\" user)\n    (44 \"Edge.Cuts\" user)\n  )\n)\n"""
        write_text(paths.kicad_pcb, placeholder)
    _sanitize_kicad_artifacts(paths)
    _tune_project_rules(paths.kicad_pro)
    _add_board_outline(paths.kicad_pcb)
    _write_fp_lib_table(paths, portable=True)
    write_text(paths.logs_dir / "pcb_generation.log", pcb_log)

    validation: dict[str, object] = {
        "source_export_ok": source_export.ok,
        "pcb_generation_ok": pcb_ok,
        "artifact_absolute_path_hits": find_absolute_path_occurrences(paths.root, suffixes={".kicad_pro", ".kicad_sch", ".kicad_pcb", ".kicad_sym", ".kicad_mod"}),
        "report_metadata_absolute_path_hits": find_absolute_path_occurrences(paths.reports_dir, suffixes={".json", ".md"}),
        "kicad_cli_available": KICAD_CLI.exists(),
    }

    if KICAD_CLI.exists():
        sch_net = run_command([str(KICAD_CLI), "sch", "export", "netlist", str(paths.kicad_sch), "-o", str(paths.reports_dir / "from_schematic.net")], cwd=paths.root, timeout=900)
        erc = run_command([str(KICAD_CLI), "sch", "erc", str(paths.kicad_sch), "--format", "json", "-o", str(paths.reports_dir / "final_erc.json")], cwd=paths.root, timeout=900)
        validation["sch_export_netlist"] = sch_net.to_dict()
        validation["erc"] = erc.to_dict()
        if paths.kicad_pcb.exists():
            drc = run_command([str(KICAD_CLI), "pcb", "drc", str(paths.kicad_pcb), "--output", str(paths.reports_dir / "pcb_drc.rpt")], cwd=paths.root, timeout=900)
            validation["drc"] = drc.to_dict()

    counts = {
        "components": xml_report.get("component_count", _count_xml_components(paths.xml_file) if paths.xml_file.exists() else 0),
        "schematic_symbols": _count_schematic_symbols(paths.kicad_sch) if paths.kicad_sch.exists() else 0,
        "pcb_footprints": _count_board_footprints(paths.kicad_pcb) if paths.kicad_pcb.exists() else 0,
        "nets": xml_report.get("net_count", _count_nets_from_xml(paths.xml_file) if paths.xml_file.exists() else 0),
        "nodes": xml_report.get("node_count", 0),
    }
    validation["counts"] = counts
    validation["xml_parse"] = {
        "ok": xml_report.get("ok", False),
        "error": xml_report.get("error"),
    }

    write_report_json(paths.reports_dir / "validation_report.json", validation)
    write_report_markdown(
        paths.reports_dir / "validation_report.md",
        "NexaPCB Validation Report",
        {
            "Project": {
                "source": str(source),
                "project_root": str(paths.root),
                "project_name": project_name,
            },
            "Counts": counts,
            "Validation": {
                "source_export_ok": source_export.ok,
                "pcb_generation_ok": pcb_ok,
                "artifact_absolute_path_hits": len(validation["artifact_absolute_path_hits"]),
                "report_metadata_absolute_path_hits": len(validation["report_metadata_absolute_path_hits"]),
                "xml_parse_ok": xml_report.get("ok", False),
            },
        },
    )

    return ExportResult(
        source=str(source),
        project_root=str(paths.root),
        project_name=project_name,
        kicad_pro=str(paths.kicad_pro),
        kicad_sch=str(paths.kicad_sch),
        kicad_pcb=str(paths.kicad_pcb),
        net_file=str(paths.net_file),
        xml_file=str(paths.xml_file),
        reports_dir=str(paths.reports_dir),
        ast_ok=ast_result.ok,
        export_ok=source_export.ok,
        validation=validation,
    )
