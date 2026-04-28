from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from nexapcb.reports import write_report_json, write_report_markdown
from nexapcb.utils.fs import read_text, write_text


FIELDS_BLOCK_RE = re.compile(r"<fields>\s*(.*?)\s*</fields>", re.S)
LIBSOURCE_PART_RE = re.compile(r'part=""([^"]+)""')


def normalize_skidl_xml(xml_file: str | Path) -> Path:
    xml_file = Path(xml_file).expanduser().resolve()
    text = read_text(xml_file)

    def fix_fields(match: re.Match[str]) -> str:
        body = match.group(1)
        fields = re.findall(r'\(field \(name "([^"]+)"\) "([^"]*)"\)', body)
        if not fields:
            return "<fields></fields>"
        inner = "".join(f'<field name="{name}">{value}</field>' for name, value in fields)
        return f"<fields>{inner}</fields>"

    text = FIELDS_BLOCK_RE.sub(fix_fields, text)
    text = LIBSOURCE_PART_RE.sub(lambda m: f'part="{m.group(1)}"', text)
    text = text.replace("<value>\"", "<value>").replace("\"</value>", "</value>")
    text = text.replace("ref=\"\"","ref=\"").replace("\"\"/>","\"/>")
    write_text(xml_file, text)
    return xml_file


def parse_xml_strict(xml_file: str | Path) -> dict:
    xml_file = Path(xml_file).expanduser().resolve()
    try:
        tree = ET.parse(xml_file)
    except ET.ParseError as exc:
        return {
            "ok": False,
            "error": {
                "code": "XML_PARSE_FAILED",
                "file": str(xml_file),
                "line": getattr(exc, "position", (None, None))[0],
                "column": getattr(exc, "position", (None, None))[1],
                "message": str(exc),
            },
        }
    root = tree.getroot()
    components: list[dict] = []
    for comp in root.findall(".//components/comp"):
        fields = {}
        fields_node = comp.find("fields")
        if fields_node is not None:
            for f in fields_node.findall("field"):
                fields[f.attrib.get("name", "")] = f.text or ""
        libsource = comp.find("libsource")
        components.append(
            {
                "ref": comp.attrib.get("ref", ""),
                "value": (comp.findtext("value") or "").strip(),
                "footprint": (comp.findtext("footprint") or "").strip(),
                "fields": fields,
                "lib": libsource.attrib.get("lib", "") if libsource is not None else "",
                "part_name": libsource.attrib.get("part", "") if libsource is not None else "",
            }
        )
    nets: list[dict] = []
    for net in root.findall(".//nets/net"):
        nodes = []
        for node in net.findall("node"):
            nodes.append(
                {
                    "ref": node.attrib.get("ref", ""),
                    "pin": node.attrib.get("pin", ""),
                    "pintype": node.attrib.get("pintype", ""),
                }
            )
        nets.append(
            {
                "name": net.attrib.get("name", ""),
                "code": net.attrib.get("code", ""),
                "node_count": len(nodes),
                "nodes": nodes,
            }
        )
    return {
        "ok": True,
        "components": components,
        "component_count": len(components),
        "nets": nets,
        "net_count": len(nets),
        "node_count": sum(n["node_count"] for n in nets),
    }


def write_xml_parse_report(xml_file: str | Path, reports_dir: str | Path) -> dict:
    reports_dir = Path(reports_dir).expanduser().resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)
    result = parse_xml_strict(xml_file)
    write_report_json(reports_dir / "netlist_report.json", result)
    write_report_markdown(
        reports_dir / "netlist_report.md",
        "Netlist Report",
        {
            "Status": {"ok": result.get("ok", False)},
            "Counts": {
                "components": result.get("component_count", 0),
                "nets": result.get("net_count", 0),
                "nodes": result.get("node_count", 0),
            } if result.get("ok") else {},
            "Parse Error": result.get("error", {}),
        },
    )
    return result
