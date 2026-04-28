from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from nexapcb.utils.fs import write_json, write_text


def serializable(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {str(k): serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serializable(v) for v in obj]
    if isinstance(obj, tuple):
        return [serializable(v) for v in obj]
    return obj


def write_report_json(path: str | Path, data: Any) -> None:
    write_json(path, serializable(data))


def write_report_markdown(path: str | Path, title: str, sections: dict[str, Any]) -> None:
    lines: list[str] = [f"# {title}", ""]
    for section_title, content in sections.items():
        lines.append(f"## {section_title}")
        lines.append("")
        if isinstance(content, dict):
            for key, value in content.items():
                lines.append(f"- **{key}:** `{value}`")
        elif isinstance(content, list):
            if content:
                for item in content:
                    lines.append(f"- `{item}`")
            else:
                lines.append("- None")
        else:
            lines.append(str(content))
        lines.append("")
    write_text(path, "\n".join(lines))
