from __future__ import annotations

import json
from pathlib import Path


COMMON_KICAD_CLI_PATHS = [
    Path("/Volumes/ToyBook/KiCad/KiCad.app/Contents/MacOS/kicad-cli"),
    Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"),
]


def detect_kicad_cli(explicit: str | None = None) -> str | None:
    if explicit:
        p = Path(explicit).expanduser().resolve()
        return str(p) if p.exists() else None
    for p in COMMON_KICAD_CLI_PATHS:
        if p.exists():
            return str(p)
    return None


def resolve_source(source: str | None = None, project_root: str | None = None, entry: str | None = None) -> Path:
    if source:
        return Path(source).expanduser().resolve()
    if project_root and entry:
        return (Path(project_root).expanduser().resolve() / entry).resolve()
    raise ValueError("Either --source or --project-root with --entry is required.")


def ensure_reports_dir(output_root: str | Path) -> Path:
    reports = Path(output_root).expanduser().resolve() / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    return reports


def load_custom_asset_manifest(path: str | None) -> dict[str, dict[str, str]]:
    if not path:
        return {}
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"CUSTOM_ASSET_MANIFEST_NOT_FOUND:{p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("CUSTOM_ASSET_MANIFEST_INVALID")
    return data
