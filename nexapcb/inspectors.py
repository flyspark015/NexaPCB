from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
import re

from nexapcb.ast_parser import parse_skidl_source
from nexapcb.reports import write_report_json, write_report_markdown
from nexapcb.utils.fs import find_absolute_path_occurrences, read_json, read_text, write_text
from nexapcb.xml_parser import normalize_skidl_xml, parse_xml_strict, write_xml_parse_report


KICAD_ARTIFACT_SUFFIXES = {".kicad_pro", ".kicad_sch", ".kicad_pcb", ".kicad_sym", ".kicad_mod"}
REPORT_SUFFIXES = {".json", ".md"}
STANDARD_SYMBOL_ROOTS = [
    Path("/Volumes/ToyBook/KiCad/KiCad.app/Contents/SharedSupport/symbols"),
    Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols"),
]


def _find_first_xml(output_root: Path) -> Path | None:
    xml_files = sorted((output_root / "netlist").glob("*.xml"))
    return xml_files[0] if xml_files else None


def _load_xml_result(output_root: Path) -> dict:
    xml_file = _find_first_xml(output_root)
    if not xml_file:
        return {
            "ok": False,
            "error": {
                "code": "XML_NOT_FOUND",
                "file": str(output_root / "netlist"),
                "message": "No XML netlist found.",
            },
            "components": [],
            "component_count": 0,
            "nets": [],
            "net_count": 0,
            "node_count": 0,
        }
    normalize_skidl_xml(xml_file)
    return parse_xml_strict(xml_file)


def _classify_component(component: dict, jlc_report: dict, custom_report: dict) -> str:
    ref = component.get("ref", "")
    fields = component.get("fields", {})
    if any(fields.get(k) for k in ("CUSTOM_SYMBOL", "CUSTOM_SYMBOL_NAME", "CUSTOM_FOOTPRINT", "CUSTOM_MODEL")):
        return "custom"

    localized_custom = {
        item["ref"]
        for item in custom_report.get("localized", [])
        if isinstance(item, dict) and item.get("ref")
    }
    if ref in localized_custom:
        return "custom"

    jlc_success = {
        item["ref"]
        for item in jlc_report.get("succeeded", [])
        if isinstance(item, dict) and item.get("ref")
    }
    if ref in jlc_success:
        return "imported_jlc"

    footprint = component.get("footprint", "")
    lib_name = component.get("lib", "")
    if footprint and (lib_name.startswith("Device") or lib_name.startswith("Connector") or lib_name.startswith("power")):
        return "generic"
    if footprint:
        return "manual_footprint"
    return "generic"


def _iter_block_spans(text: str, marker: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    idx = 0
    while True:
        start = text.find(marker, idx)
        if start == -1:
            break
        depth = 0
        end = None
        for pos in range(start, len(text)):
            if text[pos] == "(":
                depth += 1
            elif text[pos] == ")":
                depth -= 1
                if depth == 0:
                    end = pos + 1
                    break
        if end is None:
            break
        spans.append((start, end))
        idx = end
    return spans


def _normalize_token(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", (value or "").upper())


def _parse_pinmap_string(value: str) -> dict[str, str]:
    value = (value or "").strip()
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in parsed.items()}
    except Exception:
        pass
    out: dict[str, str] = {}
    for item in value.split(","):
        if "=" not in item:
            continue
        left, right = item.split("=", 1)
        left = left.strip()
        right = right.strip()
        if left and right:
            out[left] = right
    return out


def _load_pinmap_file(pin_map_path: str | Path | None) -> dict[str, dict[str, str]]:
    if not pin_map_path:
        return {}
    path = Path(pin_map_path).expanduser().resolve()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except Exception:
        return {}
    result: dict[str, dict[str, str]] = {}
    if not isinstance(data, dict):
        return result
    for ref, mapping in data.items():
        if isinstance(mapping, dict):
            result[str(ref)] = {str(k): str(v) for k, v in mapping.items()}
    return result


def _parse_schematic_instances(sch_file: Path) -> dict[str, dict]:
    if not sch_file.exists():
        return {}
    text = read_text(sch_file)
    instances: dict[str, dict] = {}
    for start, end in _iter_block_spans(text, "(symbol "):
        block = text[start:end]
        if "(instances" not in block:
            continue
        ref_match = re.search(r'\(property "Reference" "([^"]+)"', block)
        lib_match = re.search(r'\(lib_id "([^"]+)"', block)
        if not ref_match:
            continue
        ref = ref_match.group(1)
        props = {}
        for key in ("CUSTOM_SYMBOL", "CUSTOM_SYMBOL_NAME", "CUSTOM_FOOTPRINT", "CUSTOM_MODEL", "NEXAPCB_PINMAP"):
            m = re.search(rf'\(property "{key}" "([^"]*)"', block)
            if m:
                props[key] = m.group(1)
        instances[ref] = {
            "lib_id": lib_match.group(1) if lib_match else "",
            "properties": props,
            "block": block,
        }
    return instances


def _resolve_symbol_library_paths(output_root: Path, lib_id: str, component_library: str) -> list[Path]:
    candidates: list[Path] = []
    if ":" in lib_id:
        lib_name = lib_id.split(":", 1)[0]
        candidates.append(output_root / "symbols" / f"{lib_name}.kicad_sym")
        candidates.append(output_root / "symbols" / "custom" / f"{lib_name}.kicad_sym")
    if component_library:
        lib_path = Path(component_library)
        if lib_path.exists():
            candidates.append(lib_path)
        elif lib_path.name:
            for root in STANDARD_SYMBOL_ROOTS:
                candidates.append(root / lib_path.name)
    seen = set()
    resolved = []
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        resolved.append(candidate)
    return resolved


def _parse_symbol_pins_from_library(lib_file: Path, symbol_name: str) -> list[dict]:
    if not lib_file.exists():
        return []
    text = read_text(lib_file)
    target = f'(symbol "{symbol_name}"'
    start = text.find(target)
    if start == -1:
        return []
    depth = 0
    end = None
    for idx in range(start, len(text)):
        if text[idx] == "(":
            depth += 1
        elif text[idx] == ")":
            depth -= 1
            if depth == 0:
                end = idx + 1
                break
    if end is None:
        return []
    block = text[start:end]
    pins: list[dict] = []
    for p_start, p_end in _iter_block_spans(block, "(pin "):
        pblock = block[p_start:p_end]
        head = re.match(r"\(pin\s+([^\s\)]+)", pblock)
        pin_type = head.group(1) if head else ""
        name_m = re.search(r'\(name\s+"([^"]+)"', pblock)
        num_m = re.search(r'\(number\s+"([^"]+)"', pblock)
        pins.append(
            {
                "pin_number": num_m.group(1) if num_m else "",
                "pin_name": name_m.group(1) if name_m else "",
                "pin_type": pin_type,
                "raw": pblock,
            }
        )
    return pins


def _get_symbol_pins(output_root: Path, component: dict, instance_info: dict) -> tuple[list[dict], str]:
    lib_id = instance_info.get("lib_id", "")
    symbol_name = lib_id.split(":", 1)[1] if ":" in lib_id else component.get("name", "")
    for lib_path in _resolve_symbol_library_paths(output_root, lib_id, component.get("library", "")):
        pins = _parse_symbol_pins_from_library(lib_path, lib_id or symbol_name)
        if not pins and symbol_name and lib_id != symbol_name:
            pins = _parse_symbol_pins_from_library(lib_path, symbol_name)
        if pins:
            return pins, str(lib_path)
    return [], ""


def _parse_pcb_footprints(pcb_file: Path) -> dict[str, dict]:
    if not pcb_file.exists():
        return {}
    text = read_text(pcb_file)
    footprint_map: dict[str, dict] = {}
    for start, end in _iter_block_spans(text, "(footprint "):
        block = text[start:end]
        ref_match = re.search(r'\(property\s+"Reference"\s+"([^"]+)"', block)
        fp_name = re.match(r'\(footprint\s+"([^"]+)"', block)
        if not ref_match:
            continue
        ref = ref_match.group(1)
        pads: list[dict] = []
        for p_start, p_end in _iter_block_spans(block, "(pad "):
            pblock = block[p_start:p_end]
            pad_head = re.match(r'\(pad\s+"([^"]+)"\s+([^\s\)]+)\s+([^\s\)]+)', pblock)
            layers_match = re.search(r'\(layers\s+([^)]+)\)', pblock)
            net_match = re.search(r'\(net\s+"([^"]*)"\)', pblock)
            if not pad_head:
                continue
            pad_number = pad_head.group(1)
            pad_type = pad_head.group(2)
            pad_shape = pad_head.group(3)
            layers = re.findall(r'"([^"]+)"', layers_match.group(1)) if layers_match else []
            pads.append(
                {
                    "pad_number": pad_number,
                    "pad_name": pad_number,
                    "pad_type": pad_type,
                    "pad_shape": pad_shape,
                    "layers": layers,
                    "current_net": net_match.group(1) if net_match else None,
                    "raw": pblock,
                }
            )
        footprint_map[ref] = {
            "footprint": fp_name.group(1) if fp_name else "",
            "pads": pads,
            "pad_map": {p["pad_number"]: p for p in pads},
        }
    return footprint_map


def _xml_pin_entries(nets: list[dict]) -> tuple[dict[str, list[dict]], int]:
    out: dict[str, list[dict]] = {}
    single_node = 0
    for net in nets:
        node_count = net.get("node_count", 0)
        if node_count == 1:
            single_node += 1
        for node in net.get("nodes", []):
            ref = node.get("ref", "")
            pin = str(node.get("pin", ""))
            if not ref or not pin:
                continue
            out.setdefault(ref, []).append(
                {
                    "xml_pin": pin,
                    "net": net.get("name", ""),
                    "source": "SKiDL",
                    "node": f"{ref}.{pin}",
                    "node_count": node_count,
                    "connected": node_count > 1,
                    "pintype": node.get("pintype", ""),
                    "original_xml_node": node,
                }
            )
    return out, single_node


def _candidate_matches(xml_pin: str, symbol_pins: list[dict], footprint_pads: list[dict], pin_override: str | None = None) -> tuple[list[dict], dict[str, str]]:
    candidates: list[dict] = []
    recommended: dict[str, str] = {}
    pads = [p["pad_number"] for p in footprint_pads]
    if pin_override:
        candidates.append(
            {
                "pad": pin_override,
                "score": 1.0 if pin_override in pads else 0.0,
                "reason": "explicit pin-map override",
            }
        )
    for pad in pads:
        if xml_pin == pad:
            candidates.append({"pad": pad, "score": 1.0, "reason": "exact string match"})
        elif _normalize_token(xml_pin) and _normalize_token(xml_pin) == _normalize_token(pad):
            candidates.append({"pad": pad, "score": 0.95, "reason": "normalized exact match"})
    for pin in symbol_pins:
        pin_name = pin.get("pin_name", "")
        pin_number = pin.get("pin_number", "")
        if not pin_name or not pin_number:
            continue
        if xml_pin == pin_name:
            recommended[pin_name] = pin_number
            candidates.append(
                {
                    "pad": pin_number,
                    "score": 0.9 if pin_number in pads else 0.3,
                    "reason": "symbol pin name matched XML pin; suggested symbol-number to pad mapping",
                }
            )
        elif _normalize_token(xml_pin) and _normalize_token(xml_pin) == _normalize_token(pin_name):
            recommended[pin_name] = pin_number
            candidates.append(
                {
                    "pad": pin_number,
                    "score": 0.8 if pin_number in pads else 0.2,
                    "reason": "normalized symbol pin name matched XML pin",
                }
            )
    uniq = []
    seen = set()
    for c in sorted(candidates, key=lambda x: (-x["score"], x["pad"])):
        key = (c["pad"], c["reason"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(c)
    return uniq, recommended


def _package_specific_candidates(component: dict, xml_pin: str) -> tuple[list[dict], dict[str, str]]:
    footprint = component.get("footprint", "")
    ref = component.get("ref", "")
    value = component.get("value", "")
    candidates: list[dict] = []
    recommended: dict[str, str] = {}
    if "SOT-23" in footprint and (ref.startswith("Q") or "3904" in value.upper()):
        known = {"B": "1", "C": "2", "E": "3"}
        if xml_pin in known:
            recommended[xml_pin] = known[xml_pin]
            candidates.append(
                {
                    "pad": known[xml_pin],
                    "score": 0.7,
                    "reason": "package-specific known mapping for SOT-23 B/C/E, requires confirmation",
                }
            )
    return candidates, recommended


def _suggested_fix_options(ref: str, xml_pin: str, candidate_matches: list[dict], symbol_pins: list[dict], footprint_pads: list[dict], reason: str) -> list[str]:
    opts = []
    if candidate_matches:
        best = candidate_matches[0]
        if "symbol pin name" in best["reason"] or "package-specific" in best["reason"]:
            opts.append(f"Use numeric SKiDL pin reference {ref}[{best['pad']}] instead of {ref}['{xml_pin}'] if pad {best['pad']} is confirmed.")
            opts.append(f"Add explicit pin_map for {ref}: {{'{xml_pin}':'{best['pad']}'}}.")
    if reason == "PAD_NOT_FOUND":
        opts.append("Use a symbol whose pin numbers match the chosen footprint pads.")
        opts.append("Use a different footprint if the current footprint does not expose the required pads.")
    if reason == "PINMAP_INVALID":
        opts.append("Fix or remove the invalid pin-map entry; the target pad does not exist on the footprint.")
    if not opts:
        opts.append("Review symbol pin names, XML node pins, and footprint pad numbers, then add an explicit pin-map override if needed.")
    return opts


def _infer_symbol_source(component: dict, instance_info: dict) -> str:
    lib_id = instance_info.get("lib_id", "")
    if component.get("custom_symbol"):
        return "custom"
    if component.get("classification") == "imported_jlc":
        return "imported_jlc"
    if lib_id.startswith("NexaPCB_Embedded:"):
        return "generated"
    return "generic"


def _infer_footprint_source(component: dict) -> str:
    if component.get("custom_footprint"):
        return "custom"
    if component.get("classification") == "imported_jlc":
        return "imported_jlc"
    if component.get("classification") == "manual_footprint":
        return "manual"
    return "generic"


def _format_available_pin_labels(component_rows: list[dict]) -> list[str]:
    lines = []
    for row in sorted(component_rows, key=lambda x: x["ref"]):
        symbol_labels = [f'{p.get("pin_name") or "?"}:{p.get("pin_number") or "?"}' for p in row.get("symbol_pins", [])]
        xml_labels = [p.get("xml_pin", "") for p in row.get("xml_connected_pins", [])]
        pad_labels = [p.get("pad_number", "") for p in row.get("footprint_pads", [])]
        lines.append(
            f'{row["ref"]}: symbol=[{", ".join(symbol_labels)}] xml=[{", ".join(xml_labels)}] pads=[{", ".join(pad_labels)}]'
        )
    return lines


def _load_pinmaps(pin_map_path: str | Path | None, components: list[dict]) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    file_map = _load_pinmap_file(pin_map_path)
    field_map: dict[str, dict[str, str]] = {}
    for comp in components:
        ref = comp.get("ref", "")
        fields = comp.get("fields", {})
        parsed = _parse_pinmap_string(fields.get("NEXAPCB_PINMAP", ""))
        if parsed:
            field_map[ref] = parsed
    return file_map, field_map


def _analyze_pin_pad_mappings(output_root: Path, components: list[dict], nets: list[dict], pin_map_path: str | Path | None = None) -> tuple[dict, dict]:
    sch_file = next(output_root.glob("*.kicad_sch"), None)
    pcb_file = next(output_root.glob("*.kicad_pcb"), None)
    instance_map = _parse_schematic_instances(sch_file) if sch_file else {}
    pcb_footprints = _parse_pcb_footprints(pcb_file) if pcb_file else {}
    xml_pin_map, single_node_count = _xml_pin_entries(nets)
    file_pinmap, field_pinmap = _load_pinmaps(pin_map_path, components)

    component_rows: list[dict] = []
    missing_pad_nets: list[dict] = []
    matched_pad_nets = 0
    matched_pad_entries: list[dict] = []
    unused_footprint_pad_total = 0
    invalid_pinmaps: list[dict] = []

    seen_component_refs = {c.get("ref", "") for c in components}
    for ref, mapping in file_pinmap.items():
        if ref not in seen_component_refs:
            invalid_pinmaps.append(
                {
                    "ref": ref,
                    "xml_pin": "*",
                    "mapped_pad": "",
                    "issue": "PINMAP_INVALID",
                    "source": "pin_map_file",
                    "reason": "Ref not found in exported components",
                }
            )

    for component in components:
        ref = component.get("ref", "")
        instance_info = instance_map.get(ref, {})
        symbol_pins, symbol_lib_path = _get_symbol_pins(output_root, component, instance_info)
        footprint_info = pcb_footprints.get(ref, {"footprint": component.get("footprint", ""), "pads": [], "pad_map": {}})
        footprint_pads = footprint_info.get("pads", [])
        pad_map = footprint_info.get("pad_map", {})
        xml_pins = xml_pin_map.get(ref, [])
        matched_mappings: list[dict] = []
        missing_mappings: list[dict] = []
        used_pads: set[str] = set()
        recommended_pin_map: dict[str, str] = {}

        explicit_map = {}
        explicit_source = {}
        for src_name, mapping in (("skidl_field", field_pinmap.get(ref, {})), ("pin_map_file", file_pinmap.get(ref, {}))):
            for k, v in mapping.items():
                explicit_map[k] = v
                explicit_source[k] = src_name

        for key, mapped_pad in explicit_map.items():
            if mapped_pad not in pad_map:
                invalid_pinmaps.append(
                    {
                        "ref": ref,
                        "xml_pin": key,
                        "mapped_pad": mapped_pad,
                        "issue": "PINMAP_INVALID",
                        "source": explicit_source.get(key, "unknown"),
                    }
                )

        for xml_entry in xml_pins:
            xml_pin = xml_entry["xml_pin"]
            net_name = xml_entry["net"]
            explicit_pad = explicit_map.get(xml_pin)
            mapping_source = explicit_source.get(xml_pin, "")
            status = ""
            mapped_pad = None
            candidate_matches, rec_map = _candidate_matches(xml_pin, symbol_pins, footprint_pads, explicit_pad)
            package_candidates, package_rec = _package_specific_candidates(component, xml_pin)
            candidate_matches = sorted(candidate_matches + package_candidates, key=lambda x: (-x["score"], x["pad"]))
            recommended_pin_map.update(rec_map)
            recommended_pin_map.update(package_rec)

            if explicit_pad:
                if explicit_pad in pad_map:
                    mapped_pad = explicit_pad
                    status = "MATCHED"
                else:
                    status = "PINMAP_INVALID"
            elif xml_pin in pad_map:
                mapped_pad = xml_pin
                mapping_source = "direct"
                status = "MATCHED"
            else:
                normalized_matches = [p["pad"] for p in footprint_pads if _normalize_token(xml_pin) and _normalize_token(xml_pin) == _normalize_token(p["pad_number"])]
                if len(normalized_matches) == 1:
                    mapped_pad = normalized_matches[0]
                    mapping_source = "normalized"
                    status = "MATCHED"
                elif len(normalized_matches) > 1:
                    status = "AMBIGUOUS_PAD_MATCH"
                elif symbol_pins and not any(p.get("pin_name") == xml_pin or p.get("pin_number") == xml_pin for p in symbol_pins):
                    status = "SYMBOL_PIN_NOT_FOUND"
                elif not footprint_pads:
                    status = "FOOTPRINT_MISSING"
                elif candidate_matches and candidate_matches[0]["pad"] in pad_map and "symbol pin name" in candidate_matches[0]["reason"]:
                    status = "PIN_NAME_NUMBER_MISMATCH"
                else:
                    status = "PAD_NOT_FOUND"

            if mapped_pad and mapped_pad in pad_map:
                pcb_pad = pad_map[mapped_pad]
                used_pads.add(mapped_pad)
                if pcb_pad.get("current_net") == net_name:
                    matched_pad_nets += 1
                matched_pad_entries.append(
                    {
                        "ref": ref,
                        "xml_pin": xml_pin,
                        "footprint_pad": mapped_pad,
                        "net": net_name,
                        "mapping_source": mapping_source or "direct",
                        "status": status,
                    }
                )
                matched_mappings.append(
                    {
                        "xml_pin": xml_pin,
                        "footprint_pad": mapped_pad,
                        "net": net_name,
                        "mapping_source": mapping_source or "direct",
                        "status": status,
                    }
                )
            else:
                missing = {
                    "xml_pin": xml_pin,
                    "net": net_name,
                    "reason": status or "PAD_NOT_FOUND",
                    "available_footprint_pads": [p["pad_number"] for p in footprint_pads],
                    "available_symbol_pins": [p["pin_name"] or p["pin_number"] for p in symbol_pins],
                    "candidate_matches": candidate_matches,
                    "suggested_fix_options": _suggested_fix_options(ref, xml_pin, candidate_matches, symbol_pins, footprint_pads, status or "PAD_NOT_FOUND"),
                    "mapping_source": mapping_source or "unresolved",
                }
                if explicit_pad:
                    missing["mapped_pad"] = explicit_pad
                missing_mappings.append(missing)
                missing_pad_nets.append(
                    {
                        "ref": ref,
                        "pin": xml_pin,
                        "net": net_name,
                        "issue": status or "PAD_NOT_FOUND",
                        "mapping_source": mapping_source or "unresolved",
                        "candidate_matches": candidate_matches,
                    }
                )

        unused_pads = [
            {"pad": p["pad_number"], "reason": "Pad exists in footprint but no XML/SKiDL node mapped to it"}
            for p in footprint_pads
            if p["pad_number"] not in used_pads
        ]
        unused_footprint_pad_total += len(unused_pads)

        component_rows.append(
            {
                "ref": ref,
                "value": component.get("value", ""),
                "footprint": component.get("footprint", ""),
                "LCSC": component.get("LCSC", ""),
                "fields": component.get("fields", {}),
                "custom_symbol": component.get("custom_symbol", ""),
                "custom_symbol_name": component.get("custom_symbol_name", ""),
                "custom_footprint": component.get("custom_footprint", ""),
                "custom_model": component.get("custom_model", ""),
                "classification": component.get("classification", ""),
                "symbol_source": _infer_symbol_source(component, instance_info),
                "footprint_source": _infer_footprint_source(component),
                "symbol_lib_id": instance_info.get("lib_id", ""),
                "symbol_library_path": symbol_lib_path,
                "symbol_pins": symbol_pins,
                "xml_connected_pins": xml_pins,
                "footprint_pads": footprint_pads,
                "matched_mappings": matched_mappings,
                "missing_mappings": missing_mappings,
                "unused_footprint_pads": unused_pads,
                "recommended_pin_map": recommended_pin_map,
                "skidl_rewrite_suggestion": [
                    f"Replace {ref}['{name}'] with {ref}[{pad}]"
                    for name, pad in sorted(recommended_pin_map.items())
                ],
            }
        )

    components_with_mismatch = [c for c in component_rows if c["missing_mappings"]]
    pin_label_report = {
        "project_name": output_root.name,
        "status": "has_pin_pad_mismatches" if missing_pad_nets or invalid_pinmaps else "ok",
        "summary": {
            "component_count": len(components),
            "components_with_mismatch": len(components_with_mismatch),
            "missing_pad_mapping_count": len(missing_pad_nets),
            "matched_pin_pad_count": matched_pad_nets,
            "unused_footprint_pad_count": unused_footprint_pad_total,
            "unconnected_xml_pin_count": single_node_count,
            "invalid_pinmap_count": len(invalid_pinmaps),
        },
        "components": component_rows,
        "invalid_pinmaps": invalid_pinmaps,
    }
    pad_mapping_report = {
        "footprint_refs": len(pcb_footprints),
        "xml_component_refs": len(xml_pin_map),
        "matched_pad_nets": matched_pad_nets,
        "matched_mappings": matched_pad_entries,
        "missing_pad_nets": missing_pad_nets,
        "missing_pad_net_count": len(missing_pad_nets),
        "invalid_pinmaps": invalid_pinmaps,
    }
    return pin_label_report, pad_mapping_report


def _write_pin_label_reports(reports_dir: Path, pin_label_report: dict, pad_mapping_report: dict) -> None:
    write_report_json(reports_dir / "pin_label_report.json", pin_label_report)

    unresolved_rows = []
    for comp in pin_label_report["components"]:
        for miss in comp["missing_mappings"]:
            unresolved_rows.append(
                f'{comp["ref"]} | {comp["value"]} | {miss["xml_pin"]} | {miss["net"]} | {comp["footprint"]} | {", ".join(miss["available_footprint_pads"])} | {miss["reason"]} | {" / ".join(miss["suggested_fix_options"][:2])}'
            )

    detail_lines = [
        "# Pin / Pad Label Report",
        "",
        "## Summary",
        f'- total components: {pin_label_report["summary"]["component_count"]}',
        f'- components with mismatches: {pin_label_report["summary"]["components_with_mismatch"]}',
        f'- matched mappings: {pin_label_report["summary"]["matched_pin_pad_count"]}',
        f'- missing mappings: {pin_label_report["summary"]["missing_pad_mapping_count"]}',
        "",
        "## Unresolved Mismatches",
        "| Ref | Value | XML/SKiDL Pin | Net | Footprint | Available Pads | Reason | Suggested Fix |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in unresolved_rows[:500]:
        detail_lines.append(f"| {row} |")
    detail_lines.extend(["", "## Component Details"])

    for comp in [c for c in pin_label_report["components"] if c["missing_mappings"]][:100]:
        detail_lines.extend(
            [
                "",
                f"### {comp['ref']} — {comp['value']}",
                f"Footprint: `{comp['footprint']}`",
                "",
                "#### XML/SKiDL connected pins",
                "| XML Pin | Net |",
                "|---|---|",
            ]
        )
        for pin in comp["xml_connected_pins"]:
            detail_lines.append(f"| {pin['xml_pin']} | {pin['net']} |")
        detail_lines.extend(["", "#### Symbol pins", "| Pin Number | Pin Name | Type |", "|---|---|---|"])
        for pin in comp["symbol_pins"]:
            detail_lines.append(f"| {pin['pin_number']} | {pin['pin_name']} | {pin['pin_type']} |")
        detail_lines.extend(["", "#### Footprint pads", "| Pad | Current Net |", "|---|---|"])
        for pad in comp["footprint_pads"]:
            detail_lines.append(f"| {pad['pad_number']} | {pad.get('current_net') or ''} |")
        detail_lines.extend(["", "#### Missing mappings", "| XML Pin | Net | Reason | Candidates |", "|---|---|---|---|"])
        for miss in comp["missing_mappings"]:
            candidates = ", ".join(f"{c['pad']} ({c['reason']})" for c in miss["candidate_matches"][:3])
            detail_lines.append(f"| {miss['xml_pin']} | {miss['net']} | {miss['reason']} | {candidates} |")
        detail_lines.extend(["", "#### Suggested rewrite", "```python"])
        if comp["skidl_rewrite_suggestion"]:
            detail_lines.extend(comp["skidl_rewrite_suggestion"])
        elif comp["recommended_pin_map"]:
            detail_lines.append(f'{comp["ref"]}.fields["NEXAPCB_PINMAP"] = "{",".join(f"{k}={v}" for k, v in comp["recommended_pin_map"].items())}"')
        else:
            detail_lines.append("# Review symbol pins / footprint pads and add explicit pin-map if needed")
        detail_lines.extend(["```", ""])

    detail_lines.extend(
        [
            "## Fully Matched Components",
            ", ".join(sorted(c["ref"] for c in pin_label_report["components"] if not c["missing_mappings"])) or "None",
            "",
            "## Unused Footprint Pads",
        ]
    )
    for comp in pin_label_report["components"]:
        if comp["unused_footprint_pads"]:
            detail_lines.append(f'- {comp["ref"]}: {", ".join(p["pad"] for p in comp["unused_footprint_pads"])}')
    detail_lines.extend(["", "## Available Pin Labels by Component"])
    detail_lines.extend([f"- {line}" for line in _format_available_pin_labels(pin_label_report["components"])[:500]])

    write_text(reports_dir / "pin_label_report.md", "\n".join(detail_lines) + "\n")
    write_report_json(reports_dir / "pin_pad_match_report.json", pin_label_report)
    write_text(reports_dir / "pin_pad_match_report.md", "\n".join(detail_lines) + "\n")

    write_report_json(reports_dir / "pad_mapping_report.json", pad_mapping_report)
    write_report_markdown(
        reports_dir / "pad_mapping_report.md",
        "Pad Mapping Report",
        {
            "Counts": {
                "footprint_refs": pad_mapping_report["footprint_refs"],
                "xml_component_refs": pad_mapping_report["xml_component_refs"],
                "matched_pad_nets": pad_mapping_report["matched_pad_nets"],
                "missing_pad_net_count": pad_mapping_report["missing_pad_net_count"],
                "matched_mapping_entries": len(pad_mapping_report.get("matched_mappings", [])),
                "invalid_pinmaps": len(pad_mapping_report.get("invalid_pinmaps", [])),
            },
            "Matched Mappings": pad_mapping_report.get("matched_mappings", [])[:100],
            "Missing Pad Nets": pad_mapping_report["missing_pad_nets"][:100],
            "Invalid Pinmaps": pad_mapping_report.get("invalid_pinmaps", [])[:100],
        },
    )


def build_asset_report(output_root: str | Path) -> dict:
    output_root = Path(output_root).expanduser().resolve()
    reports_dir = output_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    component_report = read_json(reports_dir / "component_report.json", {})
    jlc_report = read_json(reports_dir / "jlc_import_report.json", {})
    custom_report = read_json(reports_dir / "custom_asset_report.json", {})
    output_info = inspect_output(output_root, reports_dir=reports_dir)

    components = component_report.get("components", [])
    symbols_used = sorted(
        set(
            c.get("symbol_lib_id", "") or f'{c.get("library", "")}:{c.get("name", "")}'.strip(":")
            for c in components
            if c.get("symbol_lib_id") or c.get("library") or c.get("name")
        )
    )
    footprints_used = sorted(set(c.get("footprint", "") for c in components if c.get("footprint")))
    models_used = sorted(
        set(
            c.get("custom_model", "")
            for c in components
            if c.get("custom_model")
        )
    )
    missing_symbols = [c["ref"] for c in components if not (c.get("symbol_lib_id") or c.get("library") or c.get("name") or c.get("custom_symbol"))]
    missing_footprints = [c["ref"] for c in components if not c.get("footprint")]
    missing_models = [c["ref"] for c in components if c.get("custom_model") and not Path(c["custom_model"]).exists()]

    report = {
        "project_name": output_root.name,
        "status": "ok" if not (missing_symbols or missing_footprints or missing_models or output_info.get("artifact_absolute_path_hits")) else "has_asset_issues",
        "symbols_used": symbols_used,
        "footprints_used": footprints_used,
        "models_used": models_used,
        "missing_symbols": missing_symbols,
        "missing_footprints": missing_footprints,
        "missing_3d_models": missing_models,
        "absolute_path_violations": output_info.get("artifact_absolute_path_hits", []),
        "kiprjmod_compliant": not output_info.get("artifact_absolute_path_hits"),
        "jlc_import": jlc_report,
        "custom_assets": custom_report,
    }
    write_report_json(reports_dir / "asset_report.json", report)
    write_report_markdown(
        reports_dir / "asset_report.md",
        "Asset Report",
        {
            "Summary": {
                "symbols_used": len(symbols_used),
                "footprints_used": len(footprints_used),
                "models_used": len(models_used),
                "missing_symbols": len(missing_symbols),
                "missing_footprints": len(missing_footprints),
                "missing_3d_models": len(missing_models),
                "absolute_path_violations": len(output_info.get("artifact_absolute_path_hits", [])),
            },
            "Missing Symbols": missing_symbols[:100],
            "Missing Footprints": missing_footprints[:100],
            "Missing 3D Models": missing_models[:100],
        },
    )
    return report


PAD_DESC_RE = re.compile(r'Pad\s+([^\s]+)\s+\[([^\]]*)\]\s+of\s+(\S+)')


def _parse_drc_pad_desc(desc: str) -> dict:
    m = PAD_DESC_RE.search(desc or "")
    if not m:
        return {"raw": desc}
    return {
        "pad": m.group(1),
        "net": m.group(2),
        "ref": m.group(3),
        "raw": desc,
    }


def _classify_routing_subsystem(net: str | None, refs: list[str]) -> str:
    net = net or ""
    ref_text = " ".join(refs)
    if net.startswith(("VBAT", "VSYS", "USB_VBUS", "BUZZER_5V")):
        return "Power input / battery"
    if net.startswith(("SYS_5V", "SYS_3V3")):
        return "Regulators / rails"
    if net.startswith(("I2C_", "SPI_", "UART_", "ESP_", "PD_", "CHG_", "FG_", "POWER_MON_", "VIDEO_SEL_", "RSSI_SEL_")):
        return "MCU / control"
    if net.startswith("I2C_"):
        return "I2C"
    if net.startswith("SPI_"):
        return "SPI"
    if net.startswith(("VIDEO_", "LCD_")):
        return "Video path"
    if net.startswith(("VRX",)):
        return "VRX / RF"
    if net.startswith(("RGB_", "LED_", "BUZZER_")) or any(r.startswith(("SW", "D", "BZ")) for r in refs):
        return "UI / indicators"
    if any(r.startswith(("J27", "J28", "J3", "J4", "J9")) for r in refs):
        return "Storage / debug"
    return "Unknown / other"


def _classify_net_class(net: str | None) -> str:
    net = net or ""
    if net in {"VBAT_RAW", "VBAT_PROTECTED", "VSYS_12V", "SYS_5V", "SYS_3V3", "USB_VBUS", "BUZZER_5V"}:
        return "power"
    if net == "GND":
        return "ground"
    if net.startswith(("I2C_", "SPI_", "UART_", "ESP_", "PD_", "CHG_", "FG_", "VIDEO_SEL_", "RSSI_SEL_", "SD_")):
        return "digital control"
    if net.startswith(("VIDEO_", "VRX")) and ("RSSI" not in net):
        return "high-speed / RF / video"
    if "RSSI" in net:
        return "analog/RSSI"
    return "low priority"


def _routing_priority(net: str | None) -> str:
    net = net or ""
    if net in {"GND", "VBAT_RAW", "VBAT_PROTECTED", "VSYS_12V", "SYS_5V", "SYS_3V3"}:
        return "high"
    if net in {"I2C_SCL", "I2C_SDA", "SPI_SCK", "SPI_MOSI", "SPI_MISO"}:
        return "high"
    if net.startswith(("VIDEO_", "VRX")) and ("RSSI" not in net):
        return "high"
    if "RSSI" in net:
        return "medium"
    return "low"


def _routing_action(net: str | None) -> str:
    net = net or ""
    if net == "GND":
        return "Add solid ground zones/planes and stitch return paths before signal routing."
    if net in {"VBAT_RAW", "VBAT_PROTECTED", "VSYS_12V", "SYS_5V", "SYS_3V3", "USB_VBUS", "BUZZER_5V"}:
        return "Route power rails first with short, low-impedance traces and close decoupling loops."
    if net in {"I2C_SCL", "I2C_SDA"}:
        return "Route short control traces with pullups placed close to the main controller side."
    if net in {"SPI_SCK", "SPI_MOSI", "SPI_MISO"}:
        return "Route clean SPI fanout with short branches and controlled return paths."
    if net.startswith(("VIDEO_", "VRX")) and ("RSSI" not in net):
        return "Route manually as controlled-impedance/short-return-path signal; avoid blind autorouting."
    if "RSSI" in net:
        return "Keep analog RSSI traces away from noisy power and fast video/control traces."
    return "Manual routing required; lower priority after power and critical buses."


def build_board_reports(output_root: str | Path) -> tuple[dict, dict, dict]:
    output_root = Path(output_root).expanduser().resolve()
    reports_dir = output_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    drc_path = reports_dir / "final_drc.json"
    pcb_path = next(output_root.glob("*.kicad_pcb"), None)
    drc = read_json(drc_path, {})

    violations = drc.get("violations", [])
    unconnected = drc.get("unconnected_items", [])

    violation_breakdown = Counter(v.get("type", "unknown") for v in violations)
    classified = []
    type_causes = {
        "clearance": ("footprint geometry conflict", "Board rule/footprint pitch mismatch or footprint overlap; review board rules and package pitch."),
        "drill_out_of_range": ("generated PCB constraints issue", "Board drill constraint too strict for chosen footprints; lower min through-hole diameter or choose different footprint."),
        "invalid_outline": ("invalid board outline", "Generate a valid Edge.Cuts outline around placed footprints."),
    }
    for viol in violations:
        cause, suggestion = type_causes.get(viol.get("type", "unknown"), ("generated PCB syntax/structure issue", "Review generated board structure and DRC settings."))
        items = []
        for item in viol.get("items", []):
            parsed = _parse_drc_pad_desc(item.get("description", ""))
            parsed["pos"] = item.get("pos")
            items.append(parsed)
        classified.append(
            {
                "type": viol.get("type", "unknown"),
                "severity": viol.get("severity", ""),
                "description": viol.get("description", ""),
                "items": items,
                "cause_classification": cause,
                "suggested_fix": suggestion,
            }
        )

    by_net = Counter()
    by_ref = Counter()
    gnd_items = []
    power_nets = {"VBAT_RAW", "VBAT_PROTECTED", "VSYS_12V", "SYS_5V", "SYS_3V3", "GND"}
    critical_nets = power_nets | {
        "I2C_SCL", "I2C_SDA", "SPI_SCK", "SPI_MOSI", "SPI_MISO",
        "VIDEO_MUX_OUT", "VIDEO_OSD_IN", "VIDEO_OSD_OUT",
        "VRX1_VIDEO", "VRX2_VIDEO", "VRX3_VIDEO", "VRX4_VIDEO",
        "VRX1_RSSI", "VRX2_RSSI", "VRX3_RSSI", "VRX4_RSSI",
    }
    critical = {n: [] for n in critical_nets}
    parsed_unconnected = []
    by_subsystem = Counter()
    by_net_class = Counter()
    for item in unconnected:
        drc_items = item.get("items", [])
        first = drc_items[0] if len(drc_items) > 0 else {}
        second = drc_items[1] if len(drc_items) > 1 else {}
        a = _parse_drc_pad_desc(first.get("description", ""))
        b = _parse_drc_pad_desc(second.get("description", ""))
        net = a.get("net") if a.get("net") not in {"", "<no net>", None} else b.get("net")
        refa = a.get("ref")
        refb = b.get("ref")
        refs = [r for r in [refa, refb] if r]
        if net and net not in {"<no net>"}:
            by_net[net] += 1
            by_subsystem[_classify_routing_subsystem(net, refs)] += 1
            by_net_class[_classify_net_class(net)] += 1
            if net == "GND":
                gnd_items.append({"from": a, "to": b})
            if net in critical:
                critical[net].append({"from": a, "to": b})
        if refa:
            by_ref[refa] += 1
        if refb:
            by_ref[refb] += 1
        parsed_unconnected.append(
            {
                "from": a,
                "to": b,
                "net": net,
                "refs": refs,
                "subsystem": _classify_routing_subsystem(net, refs),
                "net_class": _classify_net_class(net),
                "reason": "unrouted by design / manual routing required",
            }
        )

    component_report = read_json(reports_dir / "component_report.json", {})
    pad_mapping = read_json(reports_dir / "pad_mapping_report.json", {})
    board_connectivity = {
        "project_name": output_root.name,
        "status": "has_board_connectivity_gaps" if unconnected else "ok",
        "component_count": component_report.get("component_count", 0),
        "pcb_footprint_count": inspect_output(output_root, reports_dir=reports_dir).get("pcb_footprint_count", 0),
        "matched_pad_nets": pad_mapping.get("matched_pad_nets", 0),
        "missing_pad_net_count": pad_mapping.get("missing_pad_net_count", 0),
        "missing_pad_mappings": pad_mapping.get("missing_pad_nets", []),
        "interpretation": "Pad-net assignment is structurally correct where mapped. Remaining board connectivity failures are primarily unrouted items unless missing_pad_net_count is non-zero.",
    }

    board_drc_analysis = {
        "project_name": output_root.name,
        "total_violation_count": len(violations),
        "violation_breakdown": dict(violation_breakdown),
        "violations": classified,
    }
    unconnected_report = {
        "project_name": output_root.name,
        "total_unconnected_count": len(unconnected),
        "by_net": dict(by_net),
        "by_ref": dict(by_ref),
        "by_subsystem": dict(by_subsystem),
        "by_net_class": dict(by_net_class),
        "top_30_nets": by_net.most_common(30),
        "power_nets_with_unconnected": {k: critical[k] for k in sorted(power_nets) if critical[k]},
        "gnd_unconnected": gnd_items,
        "critical_nets": {k: critical[k] for k in sorted(critical) if critical[k]},
        "items": parsed_unconnected,
    }

    routing_todo = {
        "project_name": output_root.name,
        "status": "first-pass generated, manual routing required" if unconnected else "fully connected",
        "total_unrouted_items": len(unconnected),
        "by_subsystem": dict(by_subsystem),
        "by_net_class": dict(by_net_class),
        "critical_nets": [
            {
                "net": net,
                "unconnected_count": len(critical[net]),
                "involved_refs_pads": critical[net],
                "routing_priority": _routing_priority(net),
                "recommended_routing_action": _routing_action(net),
            }
            for net in sorted(critical)
            if critical[net]
        ],
        "suggested_routing_strategy": [
            "Route power rails first.",
            "Add ground zones/planes.",
            "Route short decoupling loops.",
            "Route I2C with pullups and short control traces.",
            "Route SPI/control buses with clean fanout.",
            "Treat RF/video paths as manual controlled-impedance/short-return-path routes.",
            "Keep analog RSSI away from noisy power/video where possible.",
        ],
        "github_ready_distinction": {
            "cli_reporting_tool": "can be GitHub-ready once reports are robust and generator output is structurally correct",
            "proof_board": "first-pass generated, manual routing required",
        },
    }

    write_report_json(reports_dir / "board_drc_analysis.json", board_drc_analysis)
    write_report_markdown(
        reports_dir / "board_drc_analysis.md",
        "Board DRC Analysis",
        {
            "Summary": {
                "total_violation_count": len(violations),
                **dict(violation_breakdown),
            },
            "Top Violations": classified[:100],
        },
    )
    write_report_json(
        reports_dir / "drc_report.json",
        {
            "total": len(violations),
            "breakdown": dict(violation_breakdown),
            "unconnected_count": len(unconnected),
            "raw": drc,
        },
    )
    write_report_markdown(
        reports_dir / "drc_report.md",
        "DRC Report",
        {
            "Counts": {
                "total": len(violations),
                "unconnected_count": len(unconnected),
                **dict(violation_breakdown),
            },
            "Top Violations": classified[:100],
        },
    )
    write_report_json(reports_dir / "unconnected_report.json", unconnected_report)
    write_report_markdown(
        reports_dir / "unconnected_report.md",
        "Unconnected Report",
        {
            "Summary": {
                "total_unconnected_count": len(unconnected),
                "top_30_nets": unconnected_report["top_30_nets"],
                "by_subsystem": unconnected_report["by_subsystem"],
                "by_net_class": unconnected_report["by_net_class"],
            },
            "Power Nets": unconnected_report["power_nets_with_unconnected"],
            "Critical Nets": unconnected_report["critical_nets"],
        },
    )
    write_report_json(reports_dir / "routing_todo_report.json", routing_todo)
    write_report_markdown(
        reports_dir / "routing_todo_report.md",
        "Routing TODO Report",
        {
            "Summary": {
                "total_unrouted_items": routing_todo["total_unrouted_items"],
                "by_subsystem": routing_todo["by_subsystem"],
                "by_net_class": routing_todo["by_net_class"],
            },
            "Critical Nets": routing_todo["critical_nets"],
            "Suggested Routing Strategy": routing_todo["suggested_routing_strategy"],
            "GitHub-ready Distinction": routing_todo["github_ready_distinction"],
        },
    )
    write_report_json(reports_dir / "board_connectivity_report.json", board_connectivity)
    write_report_markdown(
        reports_dir / "board_connectivity_report.md",
        "Board Connectivity Report",
        {
            "Summary": board_connectivity,
        },
    )
    return board_drc_analysis, unconnected_report, board_connectivity


def apply_pinmap_to_pcb(output_root: str | Path, pin_map_path: str | Path | None = None) -> dict:
    output_root = Path(output_root).expanduser().resolve()
    reports_dir = output_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    xml_result = _load_xml_result(output_root)
    component_report, _, pin_label_report, _ = build_component_and_connection_reports(
        output_root,
        source=None,
        pin_map_path=pin_map_path,
        write_reports=False,
    )
    pcb_file = next(output_root.glob("*.kicad_pcb"), None)
    if not pcb_file:
        return {"applied": 0, "mappings": [], "invalid": []}

    explicit_matches = []
    invalid = pin_label_report.get("invalid_pinmaps", [])
    for comp in pin_label_report["components"]:
        for match in comp["matched_mappings"]:
            if match.get("mapping_source") in {"pin_map_file", "skidl_field"}:
                explicit_matches.append(
                    {
                        "ref": comp["ref"],
                        "xml_pin": match["xml_pin"],
                        "pad": match["footprint_pad"],
                        "net": match["net"],
                        "mapping_source": match["mapping_source"],
                    }
                )

    if not explicit_matches:
        return {"applied": 0, "mappings": [], "invalid": invalid}

    text = read_text(pcb_file)
    pieces: list[str] = []
    cursor = 0
    applied = 0
    by_ref_pad = {(m["ref"], m["pad"]): m for m in explicit_matches}
    for f_start, f_end in _iter_block_spans(text, "(footprint "):
        block = text[f_start:f_end]
        ref_match = re.search(r'\(property\s+"Reference"\s+"([^"]+)"', block)
        if not ref_match:
            continue
        ref = ref_match.group(1)
        if not any(r == ref for (r, _) in by_ref_pad):
            continue
        block_cursor = 0
        new_block_parts: list[str] = []
        changed = False
        for p_start, p_end in _iter_block_spans(block, "(pad "):
            pblock = block[p_start:p_end]
            pad_match = re.match(r'\(pad\s+"([^"]+)"', pblock)
            if not pad_match:
                continue
            pad = pad_match.group(1)
            mapping = by_ref_pad.get((ref, pad))
            if not mapping:
                continue
            new_block_parts.append(block[block_cursor:p_start])
            if re.search(r'\(net\s+"[^"]*"\)', pblock):
                new_pblock = re.sub(r'\(net\s+"[^"]*"\)', f'(net "{mapping["net"]}")', pblock, count=1)
            else:
                insert_pos = pblock.rfind(")")
                new_pblock = pblock[:insert_pos] + f'\n\t\t\t(net "{mapping["net"]}")' + pblock[insert_pos:]
            new_block_parts.append(new_pblock)
            block_cursor = p_end
            changed = True
            applied += 1
        if changed:
            new_block_parts.append(block[block_cursor:])
            pieces.append(text[cursor:f_start])
            pieces.append("".join(new_block_parts))
            cursor = f_end
    if applied:
        pieces.append(text[cursor:])
        write_text(pcb_file, "".join(pieces))
    return {"applied": applied, "mappings": explicit_matches, "invalid": invalid}


def inspect_source(source: str | Path, reports_dir: str | Path | None = None) -> dict:
    source = Path(source).expanduser().resolve()
    parsed = parse_skidl_source(source)
    text = read_text(source)
    generate_targets = []
    for needle in ('generate_netlist(file_="', "generate_xml(file_=\""):
        idx = 0
        while True:
            pos = text.find(needle, idx)
            if pos == -1:
                break
            start = pos + len(needle)
            end = text.find('"', start)
            if end != -1:
                generate_targets.append(text[start:end])
            idx = start
    result = {
        "source": str(source),
        "refs": parsed.refs,
        "ref_count": len(parsed.refs),
        "sku_map": parsed.sku_map,
        "fields_map": parsed.fields_map,
        "custom_assets": parsed.custom_map,
        "generate_targets": generate_targets,
        "imports": sorted(set(line.split()[1] for line in text.splitlines() if line.startswith("import ") or line.startswith("from "))),
    }
    if reports_dir:
        reports_dir = Path(reports_dir).expanduser().resolve()
        reports_dir.mkdir(parents=True, exist_ok=True)
        write_report_json(reports_dir / "source_inspect_report.json", result)
        write_report_markdown(
            reports_dir / "source_inspect_report.md",
            "Source Inspect Report",
            {
                "Source": {"path": result["source"], "ref_count": result["ref_count"]},
                "Generate Targets": result["generate_targets"],
                "Imports": result["imports"],
            },
        )
    return result


def inspect_output(output_root: str | Path, reports_dir: str | Path | None = None) -> dict:
    output_root = Path(output_root).expanduser().resolve()
    reports_dir = Path(reports_dir).expanduser().resolve() if reports_dir else output_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    xml_result = _load_xml_result(output_root)
    write_xml_parse_report(_find_first_xml(output_root), reports_dir) if _find_first_xml(output_root) else None

    sch_files = list(output_root.glob("*.kicad_sch"))
    pcb_files = list(output_root.glob("*.kicad_pcb"))

    artifact_hits = find_absolute_path_occurrences(output_root, suffixes=KICAD_ARTIFACT_SUFFIXES)
    report_hits = find_absolute_path_occurrences(output_root / "reports", suffixes=REPORT_SUFFIXES)

    result = {
        "output_root": str(output_root),
        "kicad_files": [str(p) for p in output_root.glob("*.kicad_*")],
        "component_count": xml_result.get("component_count", 0),
        "net_count": xml_result.get("net_count", 0),
        "node_count": xml_result.get("node_count", 0),
        "schematic_symbol_count": read_text(sch_files[0]).count("(symbol ") if sch_files else 0,
        "pcb_footprint_count": read_text(pcb_files[0]).count("(footprint ") if pcb_files else 0,
        "artifact_absolute_path_hits": artifact_hits,
        "report_metadata_absolute_path_hits": report_hits,
        "xml_ok": xml_result.get("ok", False),
        "xml_error": xml_result.get("error"),
        "nets": xml_result.get("nets", []),
        "components": [c.get("ref", "") for c in xml_result.get("components", [])],
    }
    if reports_dir:
        write_report_json(reports_dir / "summary_report.json", result)
        write_report_markdown(
            reports_dir / "summary_report.md",
            "Summary Report",
            {
                "Counts": {
                    "components": result["component_count"],
                    "nets": result["net_count"],
                    "nodes": result["node_count"],
                    "schematic_symbols": result["schematic_symbol_count"],
                    "pcb_footprints": result["pcb_footprint_count"],
                },
                "XML": {"ok": result["xml_ok"], "error": result["xml_error"] or "None"},
                "Path Checks": {
                    "artifact_absolute_path_hits": len(result["artifact_absolute_path_hits"]),
                    "report_metadata_absolute_path_hits": len(result["report_metadata_absolute_path_hits"]),
                },
            },
        )
    return result


def build_component_and_connection_reports(
    output_root: str | Path,
    source: str | Path | None = None,
    pin_map_path: str | Path | None = None,
    write_reports: bool = True,
) -> tuple[dict, dict, dict, dict]:
    output_root = Path(output_root).expanduser().resolve()
    reports_dir = output_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    xml_result = _load_xml_result(output_root)
    if write_reports:
        write_report_json(reports_dir / "netlist_report.json", xml_result)
        write_report_markdown(
            reports_dir / "netlist_report.md",
            "Netlist Report",
            {
                "Status": {"ok": xml_result.get("ok", False)},
                "Counts": {
                    "components": xml_result.get("component_count", 0),
                    "nets": xml_result.get("net_count", 0),
                    "nodes": xml_result.get("node_count", 0),
                },
                "Parse Error": xml_result.get("error", {}),
            },
        )

    source_info = inspect_source(source) if source else {"sku_map": {}, "fields_map": {}, "custom_assets": {}, "refs": []}
    jlc_report = read_json(reports_dir / "jlc_import_report.json", {})
    custom_report = read_json(reports_dir / "custom_asset_report.json", {})

    components: list[dict] = []
    for comp in xml_result.get("components", []):
        ref = comp.get("ref", "")
        merged_fields = dict(comp.get("fields", {}))
        merged_fields.update(source_info.get("fields_map", {}).get(ref, {}))
        sku = merged_fields.get("LCSC") or source_info.get("sku_map", {}).get(ref, "")
        custom_symbol = merged_fields.get("CUSTOM_SYMBOL", "")
        custom_symbol_name = merged_fields.get("CUSTOM_SYMBOL_NAME", "")
        custom_footprint = merged_fields.get("CUSTOM_FOOTPRINT", "")
        custom_model = merged_fields.get("CUSTOM_MODEL", "")
        classification = _classify_component({**comp, "fields": merged_fields}, jlc_report, custom_report)
        warnings = []
        if not comp.get("footprint"):
            warnings.append("MISSING_FOOTPRINT")
        if not comp.get("value"):
            warnings.append("MISSING_VALUE")
        if sku and ref not in {item.get("ref") for item in jlc_report.get("succeeded", []) if isinstance(item, dict)}:
            warnings.append("SKU_PRESENT_NOT_IMPORTED")
        components.append(
            {
                "ref": ref,
                "value": comp.get("value", ""),
                "library": comp.get("lib", ""),
                "name": comp.get("part_name", ""),
                "footprint": comp.get("footprint", ""),
                "LCSC": sku,
                "fields": merged_fields,
                "custom_symbol": custom_symbol,
                "custom_symbol_name": custom_symbol_name,
                "custom_footprint": custom_footprint,
                "custom_model": custom_model,
                "classification": classification,
                "warnings": warnings,
            }
        )

    nets = xml_result.get("nets", [])
    connection_report = {
        "nets": nets,
        "net_count": xml_result.get("net_count", 0),
        "node_count": xml_result.get("node_count", 0),
        "single_node_nets": [n["name"] for n in nets if n.get("node_count", 0) <= 1],
        "power_nets": [n["name"] for n in nets if n["name"].startswith(("SYS_", "VBAT", "VSYS", "VIN")) or n["name"] in {"GND", "VCC"}],
        "possible_unconnected_pins": [{"net": n["name"], "nodes": n["nodes"]} for n in nets if n.get("node_count", 0) == 1],
    }
    component_report = {
        "components": components,
        "component_count": len(components),
        "warnings": [c["ref"] + ":" + w for c in components for w in c["warnings"]],
    }

    pin_label_report, pad_mapping_report = _analyze_pin_pad_mappings(output_root, components, nets, pin_map_path)
    pin_rows_by_ref = {row["ref"]: row for row in pin_label_report["components"]}
    for comp in components:
        row = pin_rows_by_ref.get(comp["ref"], {})
        comp["pin_count"] = len(row.get("symbol_pins", []))
        comp["pad_count"] = len(row.get("footprint_pads", []))
        comp["mismatch_status"] = "mismatch" if row.get("missing_mappings") else "matched"
        comp["symbol_source"] = row.get("symbol_source", comp.get("classification", "unknown"))
        comp["footprint_source"] = row.get("footprint_source", comp.get("classification", "unknown"))
        comp["symbol_lib_id"] = row.get("symbol_lib_id", "")

    if write_reports:
        write_report_json(reports_dir / "component_report.json", component_report)
        write_report_markdown(
            reports_dir / "component_report.md",
            "Component Report",
            {
                "Counts": {"components": component_report["component_count"]},
                "Classifications": dict(Counter(c["classification"] for c in components)),
                "Warnings": component_report["warnings"][:50],
            },
        )
        write_report_json(reports_dir / "connection_report.json", connection_report)
        write_report_markdown(
            reports_dir / "connection_report.md",
            "Connection Report",
            {
                "Counts": {"nets": connection_report["net_count"], "nodes": connection_report["node_count"]},
                "Single Node Nets": connection_report["single_node_nets"][:100],
            },
        )
        _write_pin_label_reports(reports_dir, pin_label_report, pad_mapping_report)

    return component_report, connection_report, pin_label_report, pad_mapping_report


def build_issue_report(output_root: str | Path) -> dict:
    output_root = Path(output_root).expanduser().resolve()
    reports_dir = output_root / "reports"
    validation = read_json(reports_dir / "validation_report.json", {})
    erc = read_json(reports_dir / "final_erc.json", {})
    netlist = read_json(reports_dir / "netlist_report.json", {})
    issues: list[dict] = []

    if not netlist.get("ok", True):
        err = netlist.get("error", {})
        issues.append(
            {
                "severity": "error",
                "stage": "netlist",
                "code": err.get("code", "XML_PARSE_FAILED"),
                "message": err.get("message", ""),
                "file": err.get("file", ""),
                "line": err.get("line"),
                "column": err.get("column"),
                "ref": None,
                "pin": None,
                "pad": None,
                "net": None,
                "coordinate": None,
                "likely_cause": "Generated XML/netlist was malformed or incomplete.",
                "suggested_fix": "Fix invalid XML generation before relying on report data.",
                "raw": err,
            }
        )

    has_real_erc_violations = any(sheet.get("violations") for sheet in erc.get("sheets", []))
    if has_real_erc_violations:
        total = sum(len(sheet.get("violations", [])) for sheet in erc.get("sheets", []))
        issues.append({
            "severity": "warning",
            "stage": "erc",
            "code": "ERC_SUMMARY",
            "message": f"Found {total} violations",
            "file": next(output_root.glob("*.kicad_sch"), None).name if list(output_root.glob("*.kicad_sch")) else "",
            "ref": None,
            "pin": None,
            "pad": None,
            "net": None,
            "coordinate": None,
            "likely_cause": "KiCad ERC found at least one violation.",
            "suggested_fix": "Inspect detailed ERC violations below.",
            "raw": {"total": total},
        })

    for sheet in erc.get("sheets", []):
        for violation in sheet.get("violations", []):
            items = violation.get("items", [])
            first = items[0] if items else {}
            desc = first.get("description", "")
            ref = None
            pin = None
            pad = None
            net = None
            coordinate = None
            m = re.search(r"Symbol\s+(\S+)\s+Pin\s+(\S+)", desc)
            if m:
                ref, pin = m.group(1), m.group(2)
            pad_m = re.search(r"Pad\s+(\S+)", desc)
            if pad_m:
                pad = pad_m.group(1)
            net_m = re.search(r"Net\s+(\S+)", desc)
            if net_m:
                net = net_m.group(1)
            pos = first.get("pos") if isinstance(first, dict) else None
            if isinstance(pos, dict) and "x" in pos and "y" in pos:
                coordinate = {"x": pos.get("x"), "y": pos.get("y")}
            issues.append(
                {
                    "severity": violation.get("severity", "error"),
                    "stage": "erc",
                    "code": violation.get("type", "unknown").upper(),
                    "message": violation.get("description", ""),
                    "file": next(output_root.glob("*.kicad_sch"), None).name if list(output_root.glob("*.kicad_sch")) else "",
                    "ref": ref,
                    "pin": pin,
                    "pad": pad,
                    "net": net,
                    "coordinate": coordinate,
                    "items": items,
                    "likely_cause": "Mismatch between SKiDL intent and generated schematic connectivity or symbol electrical types.",
                    "suggested_fix": "Inspect the exact refs/pins/nets in KiCad ERC and correct source or generated geometry.",
                    "raw": violation,
                }
            )

    custom_assets = read_json(reports_dir / "custom_asset_report.json", {})
    for miss in custom_assets.get("missing", []):
        issues.append(
            {
                "severity": "error",
                "stage": "assets",
                "code": miss.get("field", "CUSTOM_ASSET_NOT_FOUND"),
                "message": f'Missing custom asset for {miss.get("ref")}: {miss.get("field")}',
                "file": miss.get("path", ""),
                "ref": miss.get("ref"),
                "pin": None,
                "pad": None,
                "net": None,
                "coordinate": None,
                "likely_cause": "Custom asset path does not exist or was not copied into the project.",
                "suggested_fix": "Provide a valid custom asset file or remove the broken custom asset reference.",
                "raw": miss,
            }
        )

    report = {"issue_count": len(issues), "issues": issues}
    write_report_json(reports_dir / "issue_report.json", report)
    write_report_markdown(reports_dir / "issue_report.md", "Issue Report", {"Counts": dict(Counter(i["code"] for i in issues)), "Issues": issues[:100]})
    return report
