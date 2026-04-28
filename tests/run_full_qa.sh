#!/usr/bin/env bash
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$ROOT/.venv/bin/python -m nexapcb.cli"
OUT_ROOT="/tmp/nexapcb_qa"
LOG_DIR="$OUT_ROOT/logs"
RESULTS_JSONL="$OUT_ROOT/qa_results.jsonl"

rm -rf "$OUT_ROOT"
mkdir -p "$OUT_ROOT" "$LOG_DIR"
: > "$RESULTS_JSONL"

run_cmd() {
  local level="$1"
  local name="$2"
  local expected="${3:-pass}"
  shift 3
  local logfile="$LOG_DIR/${level}_${name}.log"
  local rc=0
  local status="passed"
  local cmd_str="$*"
  (cd "$ROOT" && "$@") >"$logfile" 2>&1 || rc=$?
  if [[ "$expected" == "fail" ]]; then
    if [[ $rc -ne 0 ]]; then
      status="passed"
    else
      status="failed"
    fi
  elif [[ "$expected" == "skip-ok" ]]; then
    if [[ $rc -eq 0 ]]; then
      status="passed"
    else
      if grep -q "JLC2KICADLIB_NOT_FOUND\|SKIPPED_JLC_LOOKUP\|LCSC_SKU_IMPORT_FAILED" "$logfile"; then
        status="skipped"
      else
        status="failed"
      fi
    fi
  else
    if [[ $rc -ne 0 ]]; then
      status="failed"
    fi
  fi
  python3 - <<PY
import json, pathlib
path = pathlib.Path("$RESULTS_JSONL")
entry = {
  "level": "$level",
  "name": "$name",
  "expected": "$expected",
  "status": "$status",
  "return_code": $rc,
  "command": "$cmd_str",
  "log": "$logfile",
}
with path.open("a") as f:
  f.write(json.dumps(entry) + "\\n")
PY
}

# Level 1
run_cmd level1 help pass $ROOT/.venv/bin/python -m nexapcb.cli --help
run_cmd level1 help_commands pass $ROOT/.venv/bin/python -m nexapcb.cli help commands
run_cmd level1 doctor_json pass $ROOT/.venv/bin/python -m nexapcb.cli doctor --format json --output "$OUT_ROOT/doctor"
run_cmd level1 version_json pass $ROOT/.venv/bin/python -m nexapcb.cli version --json
run_cmd level1 explain_list pass $ROOT/.venv/bin/python -m nexapcb.cli explain --list
run_cmd level1 explain_pin_pad pass $ROOT/.venv/bin/python -m nexapcb.cli explain PIN_PAD_MISMATCH

# Help quality
for cmd in check stage report inspect erc drc part asset net ref issue doctor version explain examples; do
  run_cmd level1 "help_${cmd}" pass $ROOT/.venv/bin/python -m nexapcb.cli "$cmd" --help
done

# Level 2 rc_filter
RC_OUT="$OUT_ROOT/rc_filter"
run_cmd level2 check_all pass $ROOT/.venv/bin/python -m nexapcb.cli check all --source tests/fixtures/rc_filter/main.py --output "$RC_OUT" --format json
run_cmd level2 stage_ast pass $ROOT/.venv/bin/python -m nexapcb.cli stage ast --source tests/fixtures/rc_filter/main.py --output "$RC_OUT" --format json
run_cmd level2 stage_skidl_export pass $ROOT/.venv/bin/python -m nexapcb.cli stage skidl-export --source tests/fixtures/rc_filter/main.py --project-name rc_filter --output "$RC_OUT" --format json
run_cmd level2 stage_netlist_parse pass $ROOT/.venv/bin/python -m nexapcb.cli stage netlist-parse --output "$RC_OUT" --format json
run_cmd level2 stage_jlc_import skip-ok $ROOT/.venv/bin/python -m nexapcb.cli stage jlc-import --source tests/fixtures/rc_filter/main.py --output "$RC_OUT" --format json
run_cmd level2 stage_custom_assets pass $ROOT/.venv/bin/python -m nexapcb.cli stage custom-assets --source tests/fixtures/rc_filter/main.py --output "$RC_OUT" --format json
run_cmd level2 stage_kicad_generate pass $ROOT/.venv/bin/python -m nexapcb.cli stage kicad-generate --project-name rc_filter --output "$RC_OUT" --format json
run_cmd level2 stage_symbol_rewrite pass $ROOT/.venv/bin/python -m nexapcb.cli stage symbol-rewrite --project-name rc_filter --output "$RC_OUT" --format json
run_cmd level2 stage_validate pass $ROOT/.venv/bin/python -m nexapcb.cli stage validate --project-name rc_filter --output "$RC_OUT" --format json
run_cmd level2 export pass $ROOT/.venv/bin/python -m nexapcb.cli export --source tests/fixtures/rc_filter/main.py --project-name rc_filter --output "$RC_OUT" --allow-issues
run_cmd level2 report_all pass $ROOT/.venv/bin/python -m nexapcb.cli report all --output "$RC_OUT" --format json
run_cmd level2 inspect_output pass $ROOT/.venv/bin/python -m nexapcb.cli inspect output --output "$RC_OUT" --format json
run_cmd level2 net_list pass $ROOT/.venv/bin/python -m nexapcb.cli net list --output "$RC_OUT" --format json
run_cmd level2 ref_list pass $ROOT/.venv/bin/python -m nexapcb.cli ref list --output "$RC_OUT" --format json
run_cmd level2 issue_list pass $ROOT/.venv/bin/python -m nexapcb.cli issue list --output "$RC_OUT" --format json

# Level 3 modular
MOD_OUT="$OUT_ROOT/modular_esp32"
run_cmd level3 check_imports pass $ROOT/.venv/bin/python -m nexapcb.cli check imports --project-root tests/fixtures/modular_esp32 --entry main.py --format json
run_cmd level3 check_all pass $ROOT/.venv/bin/python -m nexapcb.cli check all --project-root tests/fixtures/modular_esp32 --entry main.py --output "$MOD_OUT" --format json
run_cmd level3 export pass $ROOT/.venv/bin/python -m nexapcb.cli export --project-root tests/fixtures/modular_esp32 --entry main.py --project-name modular_esp32 --output "$MOD_OUT" --allow-issues
run_cmd level3 report_all pass $ROOT/.venv/bin/python -m nexapcb.cli report all --output "$MOD_OUT" --format json

# Level 4 custom part demo
CUSTOM_OUT="$OUT_ROOT/custom_part_demo"
run_cmd level4 check_assets pass $ROOT/.venv/bin/python -m nexapcb.cli check assets --source tests/fixtures/custom_part_demo/main.py --output "$CUSTOM_OUT" --format json
run_cmd level4 asset_scan pass $ROOT/.venv/bin/python -m nexapcb.cli asset scan --source tests/fixtures/custom_part_demo/main.py --format json
run_cmd level4 asset_localize pass $ROOT/.venv/bin/python -m nexapcb.cli asset localize --source tests/fixtures/custom_part_demo/main.py --output "$CUSTOM_OUT" --format json
run_cmd level4 part_inspect pass $ROOT/.venv/bin/python -m nexapcb.cli part inspect --symbol tests/fixtures/custom_part_demo/custom_assets/symbols/demo.kicad_sym --symbol-name DEMO_CONN --footprint tests/fixtures/custom_part_demo/custom_assets/footprints/demo.kicad_mod --model tests/fixtures/custom_part_demo/custom_assets/3d_models/demo.step --output "$OUT_ROOT/part_custom_sensor" --format json
run_cmd level4 part_compare pass $ROOT/.venv/bin/python -m nexapcb.cli part compare --symbol tests/fixtures/custom_part_demo/custom_assets/symbols/demo.kicad_sym --symbol-name DEMO_CONN --footprint tests/fixtures/custom_part_demo/custom_assets/footprints/demo.kicad_mod --output "$OUT_ROOT/part_compare_custom" --format json
run_cmd level4 export pass $ROOT/.venv/bin/python -m nexapcb.cli export --source tests/fixtures/custom_part_demo/main.py --project-name custom_part_demo --output "$CUSTOM_OUT" --allow-issues

# Level 5 part request
PART_ROOT="$OUT_ROOT/part_requests"
run_cmd level5 lookup_c25804 skip-ok $ROOT/.venv/bin/python -m nexapcb.cli part lookup --sku C25804 --output "$PART_ROOT/part_c25804" --format json
run_cmd level5 inspect_custom pass $ROOT/.venv/bin/python -m nexapcb.cli part inspect --symbol tests/fixtures/custom_part_demo/custom_assets/symbols/demo.kicad_sym --symbol-name DEMO_CONN --footprint tests/fixtures/custom_part_demo/custom_assets/footprints/demo.kicad_mod --model tests/fixtures/custom_part_demo/custom_assets/3d_models/demo.step --output "$PART_ROOT/custom_sensor" --format json
run_cmd level5 compare_match pass $ROOT/.venv/bin/python -m nexapcb.cli part compare --symbol tests/fixtures/custom_part_demo/custom_assets/symbols/demo.kicad_sym --symbol-name DEMO_CONN --footprint tests/fixtures/custom_part_demo/custom_assets/footprints/demo.kicad_mod --output "$PART_ROOT/custom_sensor_compare" --format json
run_cmd level5 compare_mismatch pass $ROOT/.venv/bin/python -m nexapcb.cli part compare --symbol tests/fixtures/custom_part_demo/custom_assets/symbols/demo.kicad_sym --symbol-name DEMO_CONN --footprint /Users/surajbhati/Desktop/temp/pcb/n-defender-kicad/N-defnder-local.pretty/JS1300AQ_Nav_Switch.kicad_mod --output "$PART_ROOT/mismatch_compare" --format json
run_cmd level5 pins pass $ROOT/.venv/bin/python -m nexapcb.cli part pins --symbol tests/fixtures/custom_part_demo/custom_assets/symbols/demo.kicad_sym --symbol-name DEMO_CONN --format json
run_cmd level5 pads pass $ROOT/.venv/bin/python -m nexapcb.cli part pads --footprint tests/fixtures/custom_part_demo/custom_assets/footprints/demo.kicad_mod --format json
run_cmd level5 skidl_snippet pass $ROOT/.venv/bin/python -m nexapcb.cli part skidl-snippet --input "$PART_ROOT/custom_sensor_compare" --format json
run_cmd level5 report_json pass $ROOT/.venv/bin/python -m nexapcb.cli part report --input "$PART_ROOT/custom_sensor_compare" --format json

# Level 6 negative
NEG1="$OUT_ROOT/bad_unconnected_pins"
NEG2="$OUT_ROOT/bad_pin_pad_mismatch"
NEG3="$OUT_ROOT/bad_missing_custom_asset"
run_cmd level6 bad_unconnected_export pass $ROOT/.venv/bin/python -m nexapcb.cli export --source tests/fixtures/bad_unconnected_pins/main.py --project-name bad_unconnected_pins --output "$NEG1" --allow-issues
run_cmd level6 bad_pinpad_export pass $ROOT/.venv/bin/python -m nexapcb.cli export --source tests/fixtures/bad_pin_pad_mismatch/main.py --project-name bad_pin_pad_mismatch --output "$NEG2" --allow-issues
run_cmd level6 bad_missing_check fail $ROOT/.venv/bin/python -m nexapcb.cli check all --source tests/fixtures/bad_missing_custom_asset/main.py --output "$NEG3" --format json
run_cmd level6 bad_missing_export fail $ROOT/.venv/bin/python -m nexapcb.cli export --source tests/fixtures/bad_missing_custom_asset/main.py --project-name bad_missing_custom_asset --output "$NEG3"

# Level 7 ERC/DRC
run_cmd level7 erc_run pass $ROOT/.venv/bin/python -m nexapcb.cli erc run --output "$RC_OUT" --allow-errors
run_cmd level7 erc_parse pass $ROOT/.venv/bin/python -m nexapcb.cli erc parse --output "$RC_OUT" --input "$RC_OUT/reports/final_erc.json" --allow-errors
run_cmd level7 erc_report pass $ROOT/.venv/bin/python -m nexapcb.cli erc report --output "$RC_OUT" --format json
run_cmd level7 drc_run pass $ROOT/.venv/bin/python -m nexapcb.cli drc run --output "$RC_OUT" --allow-errors
run_cmd level7 drc_parse pass $ROOT/.venv/bin/python -m nexapcb.cli drc parse --output "$RC_OUT" --input "$RC_OUT/reports/final_drc.json" --allow-errors
run_cmd level7 drc_report pass $ROOT/.venv/bin/python -m nexapcb.cli drc report --output "$RC_OUT" --format json

# Level 8 stress
STRESS_OUT="$OUT_ROOT/n_defender_stress"
run_cmd level8 check pass $ROOT/.venv/bin/python -m nexapcb.cli check all --source /Users/surajbhati/Desktop/temp/pcb/neha/nexapcb_fresh_skidl/n_defender_clean.py --output "$STRESS_OUT" --format json
run_cmd level8 export pass $ROOT/.venv/bin/python -m nexapcb.cli export --source /Users/surajbhati/Desktop/temp/pcb/neha/nexapcb_fresh_skidl/n_defender_clean.py --project-name n_defender_clean --output "$STRESS_OUT" --allow-issues
run_cmd level8 report_all pass $ROOT/.venv/bin/python -m nexapcb.cli report all --output "$STRESS_OUT" --format json

python3 - <<'PY'
import json
from pathlib import Path

root = Path("/tmp/nexapcb_qa")
results = [json.loads(line) for line in (root / "qa_results.jsonl").read_text().splitlines() if line.strip()]
passed = sum(1 for r in results if r["status"] == "passed")
failed = sum(1 for r in results if r["status"] == "failed")
skipped = sum(1 for r in results if r["status"] == "skipped")
summary = {
    "total_tests": len(results),
    "passed": passed,
    "failed": failed,
    "skipped": skipped,
    "commands": results,
    "output_paths": {
        "rc_filter": "/tmp/nexapcb_qa/rc_filter",
        "modular_esp32": "/tmp/nexapcb_qa/modular_esp32",
        "custom_part_demo": "/tmp/nexapcb_qa/custom_part_demo",
        "bad_unconnected_pins": "/tmp/nexapcb_qa/bad_unconnected_pins",
        "bad_pin_pad_mismatch": "/tmp/nexapcb_qa/bad_pin_pad_mismatch",
        "bad_missing_custom_asset": "/tmp/nexapcb_qa/bad_missing_custom_asset",
        "part_requests": "/tmp/nexapcb_qa/part_requests",
        "n_defender_stress": "/tmp/nexapcb_qa/n_defender_stress",
    },
    "failure_details": [r for r in results if r["status"] == "failed"],
    "github_readiness_recommendation": "ready" if failed == 0 else "not ready",
}
(root / "qa_summary.json").write_text(json.dumps(summary, indent=2))
md = [
    "# NexaPCB QA Summary",
    "",
    f"- total tests: {summary['total_tests']}",
    f"- passed: {passed}",
    f"- failed: {failed}",
    f"- skipped: {skipped}",
    f"- GitHub readiness recommendation: {summary['github_readiness_recommendation']}",
    "",
    "## Failed commands",
]
if summary["failure_details"]:
    for item in summary["failure_details"]:
        md.append(f"- {item['level']} / {item['name']} / rc={item['return_code']} / log={item['log']}")
else:
    md.append("- none")
(root / "qa_summary.md").write_text("\n".join(md) + "\n")
print((root / "qa_summary.json").as_posix())
PY
