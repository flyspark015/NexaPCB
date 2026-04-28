from __future__ import annotations

import json
import re
from pathlib import Path

from nexapcb.helptext import ERROR_EXPLANATIONS
from nexapcb.reports import write_report_json, write_report_markdown
from nexapcb.utils.fs import read_text, write_text


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


def _normalize(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", (value or "").upper())


def parse_kicad_sym(symbol_file: str | Path, symbol_name: str | None = None) -> dict:
    symbol_file = Path(symbol_file).expanduser().resolve()
    result = {
        "file": str(symbol_file),
        "exists": symbol_file.exists(),
        "symbols": [],
        "status": "ok",
        "error": None,
    }
    if not symbol_file.exists():
        result["status"] = "failed_missing_symbol"
        result["error"] = {"code": "CUSTOM_SYMBOL_NOT_FOUND", "file": str(symbol_file)}
        return result
    text = read_text(symbol_file)
    try:
        symbols = []
        for start, end in _iter_block_spans(text, '(symbol "'):
            block = text[start:end]
            name_m = re.match(r'\(symbol\s+"([^"]+)"', block)
            if not name_m:
                continue
            name = name_m.group(1)
            if symbol_name and name not in {symbol_name, f"{symbol_file.stem}:{symbol_name}"}:
                # allow matching either direct symbol name or lib-qualified name
                suffix = name.split(":", 1)[-1]
                if suffix != symbol_name:
                    continue
            pins = []
            for p_start, p_end in _iter_block_spans(block, "(pin "):
                pblock = block[p_start:p_end]
                head = re.match(r"\(pin\s+([^\s\)]+)", pblock)
                pin_type = head.group(1) if head else ""
                num_m = re.search(r'\(number\s+"([^"]+)"', pblock)
                name_pin_m = re.search(r'\(name\s+"([^"]+)"', pblock)
                at_m = re.search(r'\(at\s+([^\s\)]+)\s+([^\s\)]+)\s+([^\s\)]+)\)', pblock)
                pins.append(
                    {
                        "pin_number": num_m.group(1) if num_m else "",
                        "pin_name": name_pin_m.group(1) if name_pin_m else "",
                        "pin_type": pin_type,
                        "unit": 1,
                        "orientation": at_m.group(3) if at_m else "",
                        "position": {
                            "x": at_m.group(1) if at_m else "",
                            "y": at_m.group(2) if at_m else "",
                        },
                        "normalized_name": _normalize(name_pin_m.group(1) if name_pin_m else ""),
                        "raw": pblock,
                    }
                )
            symbols.append({"symbol_name": name, "pins": pins, "pin_count": len(pins)})
        result["symbols"] = symbols
        if not symbols:
            result["status"] = "failed_missing_symbol"
            result["error"] = {"code": "CUSTOM_SYMBOL_NOT_FOUND", "file": str(symbol_file), "symbol_name": symbol_name}
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = {
            "code": "PARSE_UNSUPPORTED",
            "file": str(symbol_file),
            "message": repr(exc),
            "suggested_next_action": "Verify the KiCad symbol file syntax or use a simpler library file.",
        }
    return result


def parse_kicad_mod(footprint_file: str | Path) -> dict:
    footprint_file = Path(footprint_file).expanduser().resolve()
    result = {
        "file": str(footprint_file),
        "exists": footprint_file.exists(),
        "footprint_name": "",
        "pads": [],
        "models": [],
        "status": "ok",
        "error": None,
    }
    if not footprint_file.exists():
        result["status"] = "failed_missing_footprint"
        result["error"] = {"code": "CUSTOM_FOOTPRINT_NOT_FOUND", "file": str(footprint_file)}
        return result
    text = read_text(footprint_file)
    try:
        head_m = re.match(r'\(footprint\s+"?([^"\s\)]+)"?', text)
        result["footprint_name"] = head_m.group(1) if head_m else footprint_file.stem
        pads = []
        for start, end in _iter_block_spans(text, "(pad "):
            block = text[start:end]
            pad_m = re.match(r'\(pad\s+"?([^"\s\)]+)"?\s+([^\s\)]+)\s+([^\s\)]+)', block)
            at_m = re.search(r'\(at\s+([^\s\)]+)\s+([^\s\)]+)', block)
            size_m = re.search(r'\(size\s+([^\s\)]+)\s+([^\s\)]+)\)', block)
            drill_m = re.search(r'\(drill\s+([^\s\)]+)', block)
            layers_m = re.search(r'\(layers\s+([^)]+)\)', block)
            if not pad_m:
                continue
            pad_number = pad_m.group(1)
            pads.append(
                {
                    "pad_number": pad_number,
                    "pad_name": pad_number,
                    "type": pad_m.group(2),
                    "shape": pad_m.group(3),
                    "layers": re.findall(r'"([^"]+)"', layers_m.group(1)) if layers_m else [],
                    "position": {"x": at_m.group(1) if at_m else "", "y": at_m.group(2) if at_m else ""},
                    "size": {"x": size_m.group(1) if size_m else "", "y": size_m.group(2) if size_m else ""},
                    "drill": drill_m.group(1) if drill_m else "",
                    "normalized_name": _normalize(pad_number),
                    "raw": block,
                }
            )
        models = []
        for start, end in _iter_block_spans(text, "(model "):
            block = text[start:end]
            model_m = re.match(r'\(model\s+"?([^"\)]+)"?', block)
            if model_m:
                models.append(
                    {
                        "path": model_m.group(1),
                        "absolute_path": model_m.group(1).startswith("/") or re.match(r"^[A-Za-z]:\\", model_m.group(1) or ""),
                        "kiprjmod_compatible": "${KIPRJMOD}" in model_m.group(1),
                    }
                )
        result["pads"] = pads
        result["models"] = models
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = {
            "code": "PARSE_UNSUPPORTED",
            "file": str(footprint_file),
            "message": repr(exc),
            "suggested_next_action": "Verify the KiCad footprint file syntax or use a simpler footprint file.",
        }
    return result


def compare_symbol_footprint(symbol_info: dict, footprint_info: dict, allow_fuzzy: bool = False) -> dict:
    symbol = (symbol_info.get("symbols") or [{}])[0]
    symbol_pins = symbol.get("pins", [])
    footprint_pads = footprint_info.get("pads", [])
    pad_numbers = {p["pad_number"]: p for p in footprint_pads}
    matched = []
    missing = []
    extra_pads = []
    for pin in symbol_pins:
        pin_num = pin.get("pin_number", "")
        pin_name = pin.get("pin_name", "")
        candidates = []
        if pin_num in pad_numbers:
            candidates.append({"pad": pin_num, "confidence": 1.0, "reason": "exact numeric pin/pad match"})
        for pad in footprint_pads:
            if _normalize(pin_name) and _normalize(pin_name) == pad.get("normalized_name", ""):
                candidates.append({"pad": pad["pad_number"], "confidence": 0.9, "reason": "normalized pin-name/pad-name match"})
        if candidates:
            best = sorted(candidates, key=lambda c: (-c["confidence"], c["pad"]))[0]
            if best["confidence"] >= 0.9 or allow_fuzzy:
                matched.append(
                    {
                        "symbol_pin_number": pin_num,
                        "symbol_pin_name": pin_name,
                        "footprint_pad": best["pad"],
                        "confidence": best["confidence"],
                        "reason": best["reason"],
                    }
                )
                continue
        missing.append(
            {
                "symbol_pin_number": pin_num,
                "symbol_pin_name": pin_name,
                "candidate_pads": candidates,
                "reason": "PAD_NOT_FOUND" if not candidates else "UNCERTAIN_MATCH",
                "suggested_fix": (
                    f"Use numeric SKiDL pin {pin_num}" if pin_num in pad_numbers else
                    f"Use a matching footprint or explicit pin map for {pin_name or pin_num}"
                ),
            }
        )
    matched_pad_set = {m["footprint_pad"] for m in matched}
    for pad in footprint_pads:
        if pad["pad_number"] not in matched_pad_set:
            extra_pads.append({"pad_number": pad["pad_number"], "reason": "Footprint pad has no matching symbol pin"})
    status = "ready_to_use"
    if missing:
        status = "failed_pin_pad_mismatch"
    elif extra_pads:
        status = "ready_with_warnings"
    return {
        "status": status,
        "symbol_pin_count": len(symbol_pins),
        "footprint_pad_count": len(footprint_pads),
        "matched": matched,
        "missing": missing,
        "extra_pads": extra_pads,
    }


def _safe_pin_labels(symbol_info: dict) -> list[str]:
    symbol = (symbol_info.get("symbols") or [{}])[0]
    labels = []
    for pin in symbol.get("pins", []):
        pin_name = pin.get("pin_name", "")
        pin_num = pin.get("pin_number", "")
        if pin_name:
            labels.append(f'U1["{pin_name}"]')
        if pin_num:
            labels.append(f"U1[{pin_num}]")
    return labels[:20]


def write_part_reports(
    output_dir: str | Path,
    *,
    mpn: str = "",
    sku: str = "",
    symbol_file: str | Path | None = None,
    symbol_name: str | None = None,
    footprint_file: str | Path | None = None,
    model_file: str | Path | None = None,
    source_type: str = "manual",
) -> dict:
    output_dir = Path(output_dir).expanduser().resolve()
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    symbol_info = parse_kicad_sym(symbol_file, symbol_name) if symbol_file else {"status": "missing", "symbols": []}
    footprint_info = parse_kicad_mod(footprint_file) if footprint_file else {"status": "missing", "pads": [], "models": []}
    compare = compare_symbol_footprint(symbol_info, footprint_info)

    model_path = Path(model_file).expanduser().resolve() if model_file else None
    model_report = {
        "model_exists": bool(model_path and model_path.exists()),
        "model_type": model_path.suffix if model_path else "",
        "model_path": str(model_path) if model_path else "",
        "absolute_path_warning": bool(model_path and model_path.is_absolute()),
        "kiprjmod_compatibility": False,
        "footprint_model_reference_status": "present" if footprint_info.get("models") else "missing",
    }

    part_summary = {
        "mpn": mpn,
        "sku": sku,
        "value_name": mpn or symbol_name or (symbol_info.get("symbols") or [{}])[0].get("symbol_name", ""),
        "source_type": source_type,
        "symbol_file": str(Path(symbol_file).expanduser().resolve()) if symbol_file else "",
        "symbol_name": symbol_name or ((symbol_info.get("symbols") or [{}])[0].get("symbol_name", "")),
        "footprint_file": str(Path(footprint_file).expanduser().resolve()) if footprint_file else "",
        "footprint_library_id": footprint_info.get("footprint_name", ""),
        "model_path": model_report["model_path"],
        "status": (
            "failed_missing_symbol" if symbol_file and symbol_info.get("status") != "ok" else
            "failed_missing_footprint" if footprint_file and footprint_info.get("status") != "ok" else
            compare["status"]
        ),
    }

    symbol_pin_report = {
        "symbol_file": part_summary["symbol_file"],
        "symbol_name": part_summary["symbol_name"],
        "pins": (symbol_info.get("symbols") or [{}])[0].get("pins", []),
    }
    for pin in symbol_pin_report["pins"]:
        pin_name = pin.get("pin_name", "")
        pin_num = pin.get("pin_number", "")
        pin["recommended_skidl_access"] = f'U1["{pin_name}"]' if pin_name else (f"U1[{pin_num}]" if pin_num else "")

    footprint_pad_report = {
        "footprint_file": part_summary["footprint_file"],
        "footprint_name": footprint_info.get("footprint_name", ""),
        "pads": footprint_info.get("pads", []),
    }

    skidl_usage = {
        "recommended_skidl_code_snippet": (
            "from skidl import *\n\n"
            f'U1 = Part("Custom", "{part_summary["value_name"] or "PART"}", ref="U1", value="{part_summary["value_name"] or "PART"}")\n'
            + (f'U1.footprint = "{footprint_info.get("footprint_name", "")}"\n' if footprint_info.get("footprint_name") else "")
            + (f'U1.fields["LCSC"] = "{sku}"\n' if sku else "")
        ),
        "recommended_fields": {
            "LCSC": sku or "",
            "CUSTOM_SYMBOL": part_summary["symbol_file"],
            "CUSTOM_SYMBOL_NAME": part_summary["symbol_name"],
            "CUSTOM_FOOTPRINT": part_summary["footprint_file"],
            "CUSTOM_MODEL": model_report["model_path"],
        },
        "safe_pin_labels": _safe_pin_labels(symbol_info),
        "warning_labels_not_to_use": [
            item["symbol_pin_name"] or item["symbol_pin_number"]
            for item in compare.get("missing", [])
        ],
    }

    write_report_json(reports_dir / "part_summary_report.json", part_summary)
    write_report_markdown(reports_dir / "part_summary_report.md", "Part Summary Report", part_summary)
    write_report_json(reports_dir / "symbol_pin_report.json", symbol_pin_report)
    write_report_markdown(
        reports_dir / "symbol_pin_report.md",
        "Symbol Pin Report",
        {"Pins": [f'{p["pin_number"]} {p["pin_name"]} {p["pin_type"]}' for p in symbol_pin_report["pins"]]},
    )
    write_report_json(reports_dir / "footprint_pad_report.json", footprint_pad_report)
    write_report_markdown(
        reports_dir / "footprint_pad_report.md",
        "Footprint Pad Report",
        {"Pads": [f'{p["pad_number"]} {p["type"]} {p["shape"]}' for p in footprint_pad_report["pads"]]},
    )
    write_report_json(reports_dir / "pin_pad_compare_report.json", compare)
    write_report_markdown(
        reports_dir / "pin_pad_compare_report.md",
        "Pin / Pad Compare Report",
        {
            "Summary": {
                "status": compare["status"],
                "symbol_pin_count": compare["symbol_pin_count"],
                "footprint_pad_count": compare["footprint_pad_count"],
                "matched": len(compare["matched"]),
                "missing": len(compare["missing"]),
                "extra_pads": len(compare["extra_pads"]),
            },
            "Missing": compare["missing"][:50],
            "Extra Pads": compare["extra_pads"][:50],
        },
    )
    write_report_json(reports_dir / "model_report.json", model_report)
    write_report_markdown(reports_dir / "model_report.md", "Model Report", model_report)
    write_report_json(reports_dir / "skidl_usage_report.json", skidl_usage)
    write_report_markdown(
        reports_dir / "skidl_usage_report.md",
        "SKiDL Usage Report",
        {
            "Safe Pin Labels": skidl_usage["safe_pin_labels"],
            "Warnings": skidl_usage["warning_labels_not_to_use"],
            "Snippet": skidl_usage["recommended_skidl_code_snippet"],
        },
    )
    return {
        "summary": part_summary,
        "symbol_pins": symbol_pin_report,
        "footprint_pads": footprint_pad_report,
        "compare": compare,
        "model": model_report,
        "skidl_usage": skidl_usage,
        "reports_dir": str(reports_dir),
    }


def print_part_report(input_dir: str | Path, fmt: str = "text") -> dict:
    input_dir = Path(input_dir).expanduser().resolve()
    reports_dir = input_dir / "reports"
    payload = {
        "summary": json.loads((reports_dir / "part_summary_report.json").read_text()) if (reports_dir / "part_summary_report.json").exists() else {},
        "symbol_pins": json.loads((reports_dir / "symbol_pin_report.json").read_text()) if (reports_dir / "symbol_pin_report.json").exists() else {},
        "footprint_pads": json.loads((reports_dir / "footprint_pad_report.json").read_text()) if (reports_dir / "footprint_pad_report.json").exists() else {},
        "compare": json.loads((reports_dir / "pin_pad_compare_report.json").read_text()) if (reports_dir / "pin_pad_compare_report.json").exists() else {},
        "model": json.loads((reports_dir / "model_report.json").read_text()) if (reports_dir / "model_report.json").exists() else {},
        "skidl_usage": json.loads((reports_dir / "skidl_usage_report.json").read_text()) if (reports_dir / "skidl_usage_report.json").exists() else {},
    }
    if fmt == "json":
        return payload
    return payload


def explain_error(code: str) -> dict:
    payload = ERROR_EXPLANATIONS.get(code, {})
    return {"code": code, **payload} if payload else {"code": code, "meaning": "Unknown error code."}


def list_error_codes() -> list[str]:
    return sorted(ERROR_EXPLANATIONS)
