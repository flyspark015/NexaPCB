from __future__ import annotations

import ast
from dataclasses import dataclass, asdict
from pathlib import Path

from nexapcb.ast_parser import parse_skidl_source
from nexapcb.project import load_custom_asset_manifest
from nexapcb.reports import write_report_json, write_report_markdown
from nexapcb.utils.fs import read_text
from nexapcb.utils.process import run_command


@dataclass
class CheckResult:
    ok: bool
    source: str
    syntax_ok: bool
    skidl_importable: bool
    source_exists: bool
    has_generate_netlist: bool
    has_generate_xml: bool
    has_erc: bool
    imports: list[str]
    refs: list[str]
    sku_count: int
    custom_asset_count: int
    custom_asset_missing: list[str]
    warnings: list[str]
    errors: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _extract_calls_and_imports(source_file: Path) -> tuple[set[str], list[str]]:
    tree = ast.parse(read_text(source_file), filename=str(source_file))
    calls: set[str] = set()
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            imports.append(base)
    return calls, sorted(i for i in imports if i)


def check_source(
    source: str | Path,
    reports_dir: str | Path,
    python_exe: str,
    custom_assets_path: str | None = None,
) -> CheckResult:
    source_file = Path(source).expanduser().resolve()
    reports_dir = Path(reports_dir).expanduser().resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    errors: list[str] = []
    source_exists = source_file.exists()
    syntax_ok = False
    skidl_importable = False
    has_generate_netlist = False
    has_generate_xml = False
    has_erc = False
    imports: list[str] = []
    refs: list[str] = []
    sku_count = 0
    custom_asset_count = 0
    custom_asset_missing: list[str] = []

    if not source_exists:
        errors.append(f"SOURCE_FILE_NOT_FOUND:{source_file}")
    else:
        syntax = run_command([python_exe, "-m", "py_compile", str(source_file)], cwd=source_file.parent)
        syntax_ok = syntax.ok
        if not syntax_ok:
            errors.append("PYTHON_SYNTAX_ERROR")
            warnings.extend(filter(None, [syntax.stdout.strip(), syntax.stderr.strip()]))

        skidl_import = run_command([python_exe, "-c", "import skidl; print('ok')"], cwd=source_file.parent)
        skidl_importable = skidl_import.ok
        if not skidl_importable:
            errors.append("SKIDL_IMPORT_FAILED")

        if syntax_ok:
            calls, imports = _extract_calls_and_imports(source_file)
            has_generate_netlist = "generate_netlist" in calls
            has_generate_xml = "generate_xml" in calls
            has_erc = "ERC" in calls
            if not has_generate_netlist:
                errors.append("GENERATE_NETLIST_MISSING")
            if not has_generate_xml:
                errors.append("GENERATE_XML_MISSING")
            if not has_erc:
                warnings.append("ERC_CALL_NOT_FOUND")

            parsed = parse_skidl_source(source_file)
            refs = parsed.refs
            sku_count = len(parsed.sku_map)
            custom_asset_count = len(parsed.custom_map)
            warnings.extend(parsed.errors)

            manifest = load_custom_asset_manifest(custom_assets_path) if custom_assets_path else {}
            merged_custom = {**parsed.custom_map}
            merged_custom.update(manifest)

            for ref, fields in merged_custom.items():
                for key in ("CUSTOM_SYMBOL", "CUSTOM_FOOTPRINT", "CUSTOM_MODEL"):
                    value = fields.get(key) or fields.get(key.lower())
                    if value:
                        if not Path(value).expanduser().exists():
                            custom_asset_missing.append(f"{ref}:{key}:{value}")
            if custom_asset_missing:
                errors.append("CUSTOM_ASSET_NOT_FOUND")

    if not refs:
        warnings.append("NO_REFS_DETECTED")

    result = CheckResult(
        ok=not errors,
        source=str(source_file),
        syntax_ok=syntax_ok,
        skidl_importable=skidl_importable,
        source_exists=source_exists,
        has_generate_netlist=has_generate_netlist,
        has_generate_xml=has_generate_xml,
        has_erc=has_erc,
        imports=imports,
        refs=refs,
        sku_count=sku_count,
        custom_asset_count=custom_asset_count,
        custom_asset_missing=custom_asset_missing,
        warnings=sorted(set(warnings)),
        errors=sorted(set(errors)),
    )

    write_report_json(reports_dir / "check_report.json", result.to_dict())
    write_report_markdown(
        reports_dir / "check_report.md",
        "Check Report",
        {
            "Source": {"path": result.source, "exists": result.source_exists},
            "Checks": {
                "syntax_ok": result.syntax_ok,
                "skidl_importable": result.skidl_importable,
                "has_generate_netlist": result.has_generate_netlist,
                "has_generate_xml": result.has_generate_xml,
                "has_erc": result.has_erc,
            },
            "Imports": result.imports,
            "Errors": result.errors,
            "Warnings": result.warnings,
        },
    )
    return result
