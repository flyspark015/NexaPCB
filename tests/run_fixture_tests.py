from __future__ import annotations

import json
import os
import signal
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv" / "bin" / "python"
FIXTURES = ROOT / "tests" / "fixtures"
OUT = ROOT / "test_runs" / "fixtures"
CASES = [
    "rc_filter",
    "modular_esp32",
    "custom_part_demo",
    "bad_unconnected_pins",
    "bad_pin_pad_mismatch",
    "bad_missing_custom_asset",
]


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 180) -> dict:
    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd or ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        if proc and proc.pid:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        return {
            "command": cmd,
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "timeout": timeout,
        }
    return {
        "command": cmd,
        "returncode": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
    }


def report_paths(output_dir: Path) -> dict:
    reports = output_dir / "reports"
    return {
        "exists": output_dir.exists(),
        "reports_dir": str(reports),
        "summary_report": (reports / "summary_report.json").exists(),
        "component_report": (reports / "component_report.json").exists(),
        "connection_report": (reports / "connection_report.json").exists(),
        "pin_pad_match_report": (reports / "pin_pad_match_report.json").exists(),
        "asset_report": (reports / "asset_report.json").exists(),
        "erc_report": (reports / "erc_report.json").exists(),
        "drc_report": (reports / "drc_report.json").exists(),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    results = {}
    for name in CASES:
        fixture = FIXTURES / name
        output = OUT / f"{name}_out"
        source = fixture / "main.py"
        results[name] = {
            "check": run([str(PY), "-m", "nexapcb.cli", "check", "--source", str(source)]),
            "export": run([str(PY), "-m", "nexapcb.cli", "export", "--source", str(source), "--project-name", name, "--output", str(output)]),
            "inspect_source": run([str(PY), "-m", "nexapcb.cli", "inspect", "--source", str(source)]),
            "inspect_output": run([str(PY), "-m", "nexapcb.cli", "inspect", "--output", str(output)]),
            "report_summary": run([str(PY), "-m", "nexapcb.cli", "report", "--output", str(output), "--report", "summary", "--format", "json"]),
            "report_pin_pad": run([str(PY), "-m", "nexapcb.cli", "report", "--output", str(output), "--report", "pin-pad-match", "--format", "json"]),
            "report_assets": run([str(PY), "-m", "nexapcb.cli", "report", "--output", str(output), "--report", "assets", "--format", "json"]),
            "erc": run([str(PY), "-m", "nexapcb.cli", "erc", "--output", str(output), "--allow-errors"], timeout=90),
            "drc": run([str(PY), "-m", "nexapcb.cli", "drc", "--output", str(output), "--allow-errors"], timeout=90),
            "reports": report_paths(output),
        }
    (OUT / "fixture_results.json").write_text(json.dumps(results, indent=2))
    print(str(OUT / "fixture_results.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
