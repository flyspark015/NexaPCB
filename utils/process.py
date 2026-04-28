from __future__ import annotations

import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Sequence


@dataclass
class CommandResult:
    ok: bool
    return_code: int | None
    command: list[str]
    cwd: str
    duration_s: float
    stdout: str
    stderr: str = ""
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def run_command(
    command: Sequence[str],
    cwd: str | Path | None = None,
    timeout: int = 600,
) -> CommandResult:
    cwd_path = Path(cwd).expanduser().resolve() if cwd else Path.cwd()
    start = time.time()

    try:
        proc = subprocess.run(
            list(command),
            cwd=str(cwd_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

        return CommandResult(
            ok=proc.returncode == 0,
            return_code=proc.returncode,
            command=list(command),
            cwd=str(cwd_path),
            duration_s=round(time.time() - start, 3),
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            ok=False,
            return_code=124,
            command=list(command),
            cwd=str(cwd_path),
            duration_s=round(time.time() - start, 3),
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
            error="TIMEOUT",
        )

    except Exception as exc:
        return CommandResult(
            ok=False,
            return_code=None,
            command=list(command),
            cwd=str(cwd_path),
            duration_s=round(time.time() - start, 3),
            stdout="",
            stderr="",
            error=repr(exc),
        )


def python_can_import(python_exe: str | Path, module_name: str) -> bool:
    result = run_command(
        [str(python_exe), "-c", f"import {module_name}; print('ok')"],
        timeout=20,
    )
    return result.ok


def find_python_with_module(module_name: str, project_root: str | Path | None = None) -> str | None:
    candidates: list[str] = []

    if project_root:
        root = Path(project_root).expanduser().resolve()
        candidates.extend(
            [
                str(root / ".venv" / "bin" / "python"),
                str(root / "venv" / "bin" / "python"),
            ]
        )

    candidates.append(sys.executable)

    for name in ["python3", "python"]:
        found = shutil.which(name)
        if found:
            candidates.append(found)

    seen: set[str] = set()

    for candidate in candidates:
        if not candidate or candidate in seen:
            continue

        seen.add(candidate)

        path = Path(candidate)
        if not path.exists():
            continue

        if python_can_import(path, module_name):
            return str(path)

    return None


def find_executable(names: list[str], project_root: str | Path | None = None) -> str | None:
    candidates: list[Path] = []

    if project_root:
        root = Path(project_root).expanduser().resolve()
        for name in names:
            candidates.append(root / ".venv" / "bin" / name)
            candidates.append(root / "venv" / "bin" / name)

    for path in candidates:
        if path.exists():
            return str(path)

    for name in names:
        found = shutil.which(name)
        if found:
            return found

    return None
