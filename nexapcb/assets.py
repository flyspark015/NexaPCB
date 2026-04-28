from __future__ import annotations

import re
import sys
from pathlib import Path

from nexapcb.ast_parser import parse_skidl_source
from nexapcb.project import load_custom_asset_manifest
from nexapcb.reports import write_report_json, write_report_markdown
from nexapcb.utils.fs import copy_dir, copy_file, kiprjmod_path, read_text, write_text
from nexapcb.utils.process import run_command


def _parse_symbol_name(symbol_file: Path) -> str | None:
    text = read_text(symbol_file)
    match = re.search(r'\(symbol\s+"([^"]+)"', text)
    return match.group(1) if match else None


def _rewrite_model_paths(footprint_dir: Path, model_base: str) -> None:
    for mod in footprint_dir.glob("*.kicad_mod"):
        text = read_text(mod)
        text = re.sub(r'\(model\s+"?packages3d/([^")]+)"?\)', lambda m: f'(model "{model_base}/{m.group(1)}")', text)
        write_text(mod, text)


def _iter_instance_symbol_blocks(text: str) -> list[tuple[int, int, str]]:
    blocks: list[tuple[int, int, str]] = []
    i = 0
    while True:
        start = text.find("(symbol", i)
        if start == -1:
            break
        depth = 0
        end = start
        for j in range(start, len(text)):
            ch = text[j]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    end = j + 1
                    break
        block = text[start:end]
        if "(lib_id " in block and '(property "Reference" "' in block:
            blocks.append((start, end, block))
        i = end
    return blocks


def _rewrite_symbol_instances(schematic: Path, replacement_map: dict[str, dict]) -> int:
    text = read_text(schematic)
    pieces: list[str] = []
    cursor = 0
    changed = 0
    for start, end, block in _iter_instance_symbol_blocks(text):
        ref_match = re.search(r'\(property "Reference" "([^"]+)"', block)
        ref = ref_match.group(1) if ref_match else ""
        replacement = replacement_map.get(ref)
        if not replacement:
            continue
        new_block = block
        lib_id = replacement.get("lib_id")
        footprint = replacement.get("footprint")
        model = replacement.get("model")
        custom_symbol_prop = replacement.get("custom_symbol_prop")
        custom_footprint_prop = replacement.get("custom_footprint_prop")
        if lib_id:
            new_block = re.sub(r'\(lib_id\s+"[^"]+"\)', f'(lib_id "{lib_id}")', new_block, count=1)
        if footprint:
            new_block = re.sub(r'\(property "Footprint" "[^"]*"', f'(property "Footprint" "{footprint}"', new_block, count=1)
        if custom_symbol_prop:
            if '(property "CUSTOM_SYMBOL"' in new_block:
                new_block = re.sub(r'\(property "CUSTOM_SYMBOL" "[^"]*"', f'(property "CUSTOM_SYMBOL" "{custom_symbol_prop}"', new_block, count=1)
        if custom_footprint_prop:
            if '(property "CUSTOM_FOOTPRINT"' in new_block:
                new_block = re.sub(r'\(property "CUSTOM_FOOTPRINT" "[^"]*"', f'(property "CUSTOM_FOOTPRINT" "{custom_footprint_prop}"', new_block, count=1)
        if model:
            if '(property "CUSTOM_MODEL"' in new_block:
                new_block = re.sub(r'\(property "CUSTOM_MODEL" "[^"]*"', f'(property "CUSTOM_MODEL" "{model}"', new_block, count=1)
            else:
                insert_at = new_block.find('(property "Datasheet"')
                if insert_at != -1:
                    prop = f'    (property "CUSTOM_MODEL" "{model}"\n      (at 0 0 0)\n      (effects (font (size 1.27 1.27)) (hide yes)))\n'
                    new_block = new_block[:insert_at] + prop + new_block[insert_at:]
        if new_block != block:
            pieces.append(text[cursor:start])
            pieces.append(new_block)
            cursor = end
            changed += 1
    if changed:
        pieces.append(text[cursor:])
        write_text(schematic, "".join(pieces))
    return changed


def _extract_custom_props_from_schematic(schematic: Path) -> dict[str, dict[str, str]]:
    props: dict[str, dict[str, str]] = {}
    text = read_text(schematic)
    for _, _, block in _iter_instance_symbol_blocks(text):
        ref_match = re.search(r'\(property "Reference" "([^"]+)"', block)
        if not ref_match:
            continue
        ref = ref_match.group(1)
        for key in ("CUSTOM_SYMBOL", "CUSTOM_SYMBOL_NAME", "CUSTOM_FOOTPRINT", "CUSTOM_MODEL"):
            m = re.search(rf'\(property "{key}" "([^"]+)"', block)
            if m:
                props.setdefault(ref, {})[key] = m.group(1)
    return props


def refresh_project_lib_tables(output_root: str | Path) -> None:
    output_root = Path(output_root).expanduser().resolve()
    sym_entries = []
    for sym in sorted((output_root / "symbols").rglob("*.kicad_sym")):
        lib_name = sym.stem
        rel = sym.relative_to(output_root).as_posix()
        sym_entries.append(f'  (lib (name "{lib_name}")(type "KiCad")(uri "${{KIPRJMOD}}/{rel}")(options "")(descr "Localized symbol lib"))')
    sym_table = "(sym_lib_table\n" + ("\n".join(sym_entries) + "\n" if sym_entries else "") + ")\n"
    write_text(output_root / "sym-lib-table", sym_table)

    existing_fp = read_text(output_root / "fp-lib-table") if (output_root / "fp-lib-table").exists() else "(fp_lib_table\n)\n"
    fp_entries = []
    for fp_dir in sorted((output_root / "footprints").glob("*.pretty")):
        lib_name = fp_dir.stem
        rel = fp_dir.relative_to(output_root).as_posix()
        entry = f'  (lib (name "{lib_name}")(type "KiCad")(uri "${{KIPRJMOD}}/{rel}")(options "")(descr "Localized footprint lib"))'
        if f'(name "{lib_name}")' not in existing_fp:
            fp_entries.append(entry)
    fp_table = existing_fp.rstrip()
    if fp_table.endswith(")"):
        fp_table = fp_table[:-1]
    if fp_entries:
        fp_table += ("\n" if not fp_table.endswith("\n") else "") + "\n".join(fp_entries) + "\n"
    fp_table += ")\n"
    write_text(output_root / "fp-lib-table", fp_table)


def localize_custom_assets(
    source: str | Path | None,
    output_root: str | Path,
    custom_manifest: str | None = None,
) -> dict:
    output_root = Path(output_root).expanduser().resolve()
    report = {
        "localized": [],
        "missing": [],
        "manifest_used": custom_manifest,
        "schematic_replacements": [],
    }

    merged = {}
    if source is not None:
        source = Path(source).expanduser().resolve()
        parsed = parse_skidl_source(source)
        merged = {**parsed.custom_map}
    if custom_manifest:
        merged.update(load_custom_asset_manifest(custom_manifest))
    schematic = next(output_root.glob("*.kicad_sch"), None)
    if schematic:
        for ref, fields in _extract_custom_props_from_schematic(schematic).items():
            merged.setdefault(ref, {}).update(fields)

    sym_dir = output_root / "symbols" / "custom"
    fp_dir = output_root / "footprints" / "custom.pretty"
    model_dir = output_root / "3d_models" / "custom"
    sym_dir.mkdir(parents=True, exist_ok=True)
    fp_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    replacement_map: dict[str, dict] = {}
    for ref, fields in merged.items():
        replacement = {}
        for key, dst_dir in (
            ("CUSTOM_SYMBOL", sym_dir),
            ("CUSTOM_FOOTPRINT", fp_dir),
            ("CUSTOM_MODEL", model_dir),
        ):
            value = fields.get(key) or fields.get(key.lower())
            if not value:
                continue
            if str(value).startswith("${KIPRJMOD}/"):
                replacement[key] = str(value)
                continue
            src = Path(value).expanduser()
            if not src.exists():
                report["missing"].append({"ref": ref, "field": key, "path": str(src)})
                continue
            dst = copy_file(src, dst_dir / src.name)
            localized = {
                "ref": ref,
                "field": key,
                "source": str(src.resolve()),
                "dest": str(dst),
                "kiprjmod": kiprjmod_path(dst.relative_to(output_root).as_posix()),
            }
            report["localized"].append(localized)
            replacement[key] = localized["kiprjmod"]

        symbol_name = fields.get("CUSTOM_SYMBOL_NAME") or fields.get("custom_symbol_name")
        if replacement.get("CUSTOM_SYMBOL") and symbol_name:
            lib_name = Path(replacement["CUSTOM_SYMBOL"]).stem
            replacement_map.setdefault(ref, {})["lib_id"] = f"{lib_name}:{symbol_name}"
            replacement_map.setdefault(ref, {})["custom_symbol_prop"] = replacement["CUSTOM_SYMBOL"]
        if replacement.get("CUSTOM_FOOTPRINT"):
            fp_rel = Path(replacement["CUSTOM_FOOTPRINT"]).name
            replacement_map.setdefault(ref, {})["footprint"] = f"custom:{Path(fp_rel).stem}"
            replacement_map.setdefault(ref, {})["custom_footprint_prop"] = replacement["CUSTOM_FOOTPRINT"]
        if replacement.get("CUSTOM_MODEL"):
            replacement_map.setdefault(ref, {})["model"] = replacement["CUSTOM_MODEL"]

    if schematic and replacement_map:
        changed = _rewrite_symbol_instances(schematic, replacement_map)
        report["schematic_replacements"].append({"changed_instances": changed})

    refresh_project_lib_tables(output_root)

    reports_dir = output_root / "reports"
    write_report_json(reports_dir / "custom_asset_report.json", report)
    write_report_markdown(
        reports_dir / "custom_asset_report.md",
        "Custom Asset Report",
        {
            "Localized": [f"{x['ref']} {x['field']} -> {x['kiprjmod']}" for x in report["localized"]],
            "Missing": [f"{x['ref']} {x['field']} -> {x['path']}" for x in report["missing"]],
            "Schematic Replacements": report["schematic_replacements"],
        },
    )
    return report


def import_jlc_assets(
    output_root: str | Path,
    components: list[dict],
    allow_generic_fallback: bool = False,
    python_exe: str | None = None,
) -> dict:
    output_root = Path(output_root).expanduser().resolve()
    python_exe = python_exe or sys.executable
    report = {
        "attempted": [],
        "succeeded": [],
        "failed": [],
        "allow_generic_fallback": allow_generic_fallback,
    }
    replacement_map: dict[str, dict] = {}

    for component in components:
        ref = component.get("ref", "")
        sku = component.get("LCSC") or component.get("fields", {}).get("LCSC")
        if not sku:
            continue
        raw_dir = output_root / "import_raw" / f"{ref}_{sku}"
        symbol_lib = f"imported_{sku}"
        footprint_lib = f"jlc_{sku}"
        cmd = [
            python_exe,
            "-m",
            "JLC2KiCadLib.JLC2KiCadLib",
            sku,
            "-dir",
            str(raw_dir),
            "-symbol_lib",
            symbol_lib,
            "-symbol_lib_dir",
            "symbol",
            "-footprint_lib",
            footprint_lib,
            "--skip_existing",
        ]
        result = run_command(cmd, cwd=output_root, timeout=900)
        attempt = {
            "ref": ref,
            "sku": sku,
            "command": cmd,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "ok": result.ok,
        }
        report["attempted"].append(attempt)
        if not result.ok:
            report["failed"].append(
                {
                    **attempt,
                    "code": "LCSC_SKU_IMPORT_FAILED",
                }
            )
            continue

        symbol_file = raw_dir / "symbol" / f"{symbol_lib}.kicad_sym"
        footprint_dir = raw_dir / footprint_lib
        model_dir = footprint_dir / "packages3d"
        if not symbol_file.exists() or not footprint_dir.exists():
            report["failed"].append(
                {
                    **attempt,
                    "code": "LCSC_SKU_IMPORT_FAILED",
                    "reason": "Expected imported symbol/footprint output not found.",
                }
            )
            continue

        dst_sym = copy_file(symbol_file, output_root / "symbols" / symbol_file.name)
        dst_fp_dir = copy_dir(footprint_dir, output_root / "footprints" / f"{footprint_lib}.pretty")
        model_kiprj = ""
        if model_dir.exists():
            dst_model_dir = copy_dir(model_dir, output_root / "3d_models" / "imported_jlc" / sku)
            model_kiprj = kiprjmod_path(dst_model_dir.relative_to(output_root).as_posix())
            _rewrite_model_paths(dst_fp_dir, model_kiprj)

        footprint_files = sorted(dst_fp_dir.glob("*.kicad_mod"))
        footprint_name = f"{footprint_lib}:{footprint_files[0].stem}" if footprint_files else component.get("footprint", "")
        symbol_name = _parse_symbol_name(dst_sym) or component.get("name", "")
        lib_id = f"{dst_sym.stem}:{symbol_name}" if symbol_name else ""

        replacement_map[ref] = {
            "lib_id": lib_id or None,
            "footprint": footprint_name or None,
            "model": model_kiprj or None,
        }
        report["succeeded"].append(
            {
                "ref": ref,
                "sku": sku,
                "symbol_lib": dst_sym.stem,
                "symbol_name": symbol_name,
                "footprint": footprint_name,
                "model": model_kiprj,
            }
        )

    schematic = next(output_root.glob("*.kicad_sch"), None)
    if schematic and replacement_map:
        _rewrite_symbol_instances(schematic, replacement_map)
    refresh_project_lib_tables(output_root)

    reports_dir = output_root / "reports"
    write_report_json(reports_dir / "jlc_import_report.json", report)
    write_report_markdown(
        reports_dir / "jlc_import_report.md",
        "JLC Import Report",
        {
            "Attempted": [f"{x['ref']}:{x['sku']}" for x in report["attempted"]],
            "Succeeded": [f"{x['ref']}:{x['sku']}" for x in report["succeeded"]],
            "Failed": [f"{x.get('ref')}:{x.get('sku')}:{x.get('code', 'FAIL')}" for x in report["failed"]],
            "Fallback": {"allow_generic_fallback": allow_generic_fallback},
        },
    )

    if report["failed"] and not allow_generic_fallback:
        raise RuntimeError("LCSC_SKU_IMPORT_FAILED")
    return report
