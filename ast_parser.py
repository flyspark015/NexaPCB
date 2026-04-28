from __future__ import annotations

import ast
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from nexapcb.utils.fs import read_text, write_json


SKU_RE = re.compile(r"^C\d+$", re.IGNORECASE)


@dataclass
class AstParseResult:
    ok: bool
    source_file: str
    sku_map: dict[str, str]
    fields_map: dict[str, dict[str, str]]
    custom_map: dict[str, dict[str, str]]
    refs: list[str]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _is_sku(value: str) -> bool:
    return bool(SKU_RE.match(str(value).strip()))


def _literal_str(node: ast.AST) -> str | None:
    try:
        value = ast.literal_eval(node)
    except Exception:
        return None

    if isinstance(value, str):
        return value

    return None


def _ref_from_part_assignment(node: ast.Assign) -> str | None:
    if not node.targets:
        return None

    target = node.targets[0]

    if isinstance(target, ast.Name):
        return target.id

    return None


def _ref_from_fields_assignment(node: ast.Assign) -> tuple[str, str, str] | None:
    """
    Detect:
      R1.fields["LCSC"] = "C25804"
      U1.fields["CUSTOM_SYMBOL"] = "/path/file.kicad_sym"
    """
    if not node.targets:
        return None

    target = node.targets[0]

    if not isinstance(target, ast.Subscript):
        return None

    sub = target

    if not isinstance(sub.value, ast.Attribute):
        return None

    if sub.value.attr != "fields":
        return None

    if not isinstance(sub.value.value, ast.Name):
        return None

    ref = sub.value.value.id
    key = _literal_str(sub.slice)
    value = _literal_str(node.value)

    if not key or value is None:
        return None

    return ref, key, value


def _part_ref_kw_from_call(call: ast.Call, assigned_name: str | None = None) -> str | None:
    """
    Detect ref in:
      R1 = Part(..., ref="R1")
    Fallback to assigned name if ref kw is missing.
    """
    for kw in call.keywords:
        if kw.arg == "ref":
            value = _literal_str(kw.value)
            if value:
                return value

    return assigned_name


def _sku_from_part_call(call: ast.Call) -> str | None:
    """
    Detect:
      Part(..., sku="C123")
      Part(..., lcsc="C123")
      Part(..., LCSC="C123")
    """
    for kw in call.keywords:
        if kw.arg in {"sku", "lcsc", "LCSC", "jlc", "JLC"}:
            value = _literal_str(kw.value)
            if value and _is_sku(value):
                return value.upper()

    return None


def _custom_fields_from_part_call(call: ast.Call) -> dict[str, str]:
    out: dict[str, str] = {}

    key_map = {
        "custom_symbol": "CUSTOM_SYMBOL",
        "custom_symbol_name": "CUSTOM_SYMBOL_NAME",
        "custom_footprint": "CUSTOM_FOOTPRINT",
        "custom_model": "CUSTOM_MODEL",
    }

    for kw in call.keywords:
        if kw.arg in key_map:
            value = _literal_str(kw.value)
            if value:
                out[key_map[kw.arg]] = value

    return out


def parse_skidl_source(source_file: str | Path) -> AstParseResult:
    source_file = Path(source_file).expanduser().resolve()
    errors: list[str] = []
    sku_map: dict[str, str] = {}
    fields_map: dict[str, dict[str, str]] = {}
    custom_map: dict[str, dict[str, str]] = {}
    refs: set[str] = set()

    try:
        source = read_text(source_file)
    except Exception as exc:
        return AstParseResult(
            ok=False,
            source_file=str(source_file),
            sku_map={},
            fields_map={},
            custom_map={},
            refs=[],
            errors=[f"SOURCE_READ_FAILED:{repr(exc)}"],
        )

    try:
        tree = ast.parse(source, filename=str(source_file))
    except Exception as exc:
        return AstParseResult(
            ok=False,
            source_file=str(source_file),
            sku_map={},
            fields_map={},
            custom_map={},
            refs=[],
            errors=[f"AST_PARSE_FAILED:{repr(exc)}"],
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            # Detect Part assignment.
            assigned_name = _ref_from_part_assignment(node)

            if isinstance(node.value, ast.Call):
                call = node.value

                call_name = ""
                if isinstance(call.func, ast.Name):
                    call_name = call.func.id
                elif isinstance(call.func, ast.Attribute):
                    call_name = call.func.attr

                if call_name == "Part":
                    ref = _part_ref_kw_from_call(call, assigned_name)
                    if ref:
                        refs.add(ref)

                        sku = _sku_from_part_call(call)
                        if sku:
                            sku_map[ref] = sku

                        custom_fields = _custom_fields_from_part_call(call)
                        if custom_fields:
                            fields_map.setdefault(ref, {}).update(custom_fields)
                            custom_map.setdefault(ref, {}).update(custom_fields)

            # Detect fields assignment.
            field_data = _ref_from_fields_assignment(node)
            if field_data:
                ref, key, value = field_data
                refs.add(ref)
                fields_map.setdefault(ref, {})[key] = value

                if key.upper() in {"LCSC", "JLC", "SKU", "JLCPCB"} and _is_sku(value):
                    sku_map[ref] = value.upper()

                if key.upper() in {
                    "CUSTOM_SYMBOL",
                    "CUSTOM_SYMBOL_NAME",
                    "CUSTOM_FOOTPRINT",
                    "CUSTOM_MODEL",
                }:
                    custom_map.setdefault(ref, {})[key.upper()] = value

    return AstParseResult(
        ok=not errors,
        source_file=str(source_file),
        sku_map=sku_map,
        fields_map=fields_map,
        custom_map=custom_map,
        refs=sorted(refs),
        errors=errors,
    )


def parse_and_write_report(source_file: str | Path, report_file: str | Path) -> AstParseResult:
    result = parse_skidl_source(source_file)
    write_json(report_file, result.to_dict())
    return result
