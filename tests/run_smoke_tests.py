from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv" / "bin" / "python"
OUT = ROOT / "test_runs"
EXAMPLES = ["rc_filter", "esp32_led_button", "modular_esp32", "custom_part_demo"]


def run(cmd: list[str], cwd: Path | None = None) -> dict:
    proc = subprocess.run(cmd, cwd=str(cwd or ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return {
        "command": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    results = {}
    for name in EXAMPLES:
        src = OUT / name
        gen = OUT / f"{name}_out"
        results[name] = {
            "create": run([str(PY), "-m", "nexapcb.cli", "examples", "--create", name, "--output", str(src)]),
            "check": run([str(PY), "-m", "nexapcb.cli", "check", "--project-root", str(src), "--entry", "main.py"]),
            "export": run([str(PY), "-m", "nexapcb.cli", "export", "--project-root", str(src), "--entry", "main.py", "--project-name", name, "--output", str(gen)]),
            "inspect_source": run([str(PY), "-m", "nexapcb.cli", "inspect", "--project-root", str(src), "--entry", "main.py"]),
            "inspect_output": run([str(PY), "-m", "nexapcb.cli", "inspect", "--output", str(gen)]),
            "report": run([str(PY), "-m", "nexapcb.cli", "report", "--output", str(gen), "--report", "summary", "--format", "json"]),
            "erc": run([str(PY), "-m", "nexapcb.cli", "erc", "--output", str(gen), "--allow-errors"]),
        }
    (OUT / "smoke_results.json").write_text(json.dumps(results, indent=2))
    print(str(OUT / "smoke_results.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
