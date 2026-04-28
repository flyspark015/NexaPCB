from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from nexapcb.config import FORBIDDEN_ABSOLUTE_PATH_MARKERS

WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:\\\\")


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def write_text(path: str | Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: str | Path, default: Any | None = None) -> Any:
    path = Path(path)
    if not path.exists():
        return {} if default is None else default
    try:
        return json.loads(read_text(path))
    except Exception:
        return {} if default is None else default


def write_json(path: str | Path, data: Any) -> None:
    write_text(path, json.dumps(data, indent=2, ensure_ascii=False))


def copy_file(src: str | Path, dst: str | Path) -> Path:
    src = Path(src).expanduser().resolve()
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def copy_dir(src: str | Path, dst: str | Path) -> Path:
    src = Path(src).expanduser().resolve()
    dst = Path(dst)
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)
    return dst


def is_absolute_path_text(text: str) -> bool:
    if WINDOWS_PATH_RE.search(text):
        return True
    return any(marker in text for marker in FORBIDDEN_ABSOLUTE_PATH_MARKERS)


def find_absolute_path_occurrences(root: str | Path, suffixes: set[str] | None = None) -> list[str]:
    root = Path(root)
    suffixes = suffixes or {
        ".kicad_pro",
        ".kicad_sch",
        ".kicad_pcb",
        ".kicad_sym",
        ".kicad_mod",
        ".json",
        ".md",
    }
    hits: list[str] = []
    if not root.exists():
        return hits
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in suffixes:
            continue
        text = read_text(path)
        if is_absolute_path_text(text):
            hits.append(str(path))
    return hits


def kiprjmod_path(*parts: str) -> str:
    clean = "/".join(str(p).strip("/").replace("\\", "/") for p in parts if p)
    return f"${{KIPRJMOD}}/{clean}"

