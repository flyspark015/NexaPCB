# 📊 NexaPCB Reports
> Structured report outputs for humans, AI agents, and automation pipelines.

[!IMPORTANT]
NexaPCB is **report-first**. The generated KiCad project matters, but the reports are the primary feedback loop for fixing SKiDL, asset, ERC, DRC, and connectivity issues.

## 🧭 Overview

All canonical reports are written under:

```text
output/reports/
```

NexaPCB emits both:

- **JSON** for automation and AI loops
- **Markdown** for human review and GitHub/code-review readability

## 🧠 AI Read Order

Use this order for the fastest debugging loop:

1. `final_result.json`
2. `validation_report.json`
3. `issue_report.json`
4. `pin_pad_match_report.json`
5. `erc_report.json`
6. `drc_report.json`
7. `unconnected_report.json`
8. `board_connectivity_report.json`
9. focused CLI queries:
   - `nexapcb issue by-code`
   - `nexapcb ref show`
   - `nexapcb net show`

[!TIP]
For automation, prefer JSON over Markdown. Markdown is for scanning and review, not as the primary machine interface.

## 📁 Report Catalog

| Report | Purpose | Why it matters |
|---|---|---|
| `final_result` | Top-level final command result | First file an AI agent should read |
| `summary_report` | High-level project summary | Quick sanity check |
| `check_report` | Source readiness before export | Catch syntax/import/asset issues early |
| `ast_parse_report` | Source metadata discovery | Refs, fields, SKUs, custom assets |
| `skidl_export_report` | SKiDL execution/export status | Confirms XML/netlist generation |
| `netlist_report` | Parsed XML/netlist summary | Components, nets, node counts |
| `component_report` | One entry per part | Metadata, SKU, footprint, warnings |
| `connection_report` | Net-to-node connectivity | Debug wiring and single-node nets |
| `issue_report` | Normalized issue list | Main actionable issue feed |
| `validation_report` | End-to-end artifact status | Export success vs issues vs failure |
| `erc_report` | Normalized KiCad ERC data | Schematic electrical rule feedback |
| `drc_report` | Normalized KiCad DRC data | PCB geometry/rule feedback |
| `unconnected_report` | PCB unrouted/unconnected grouping | Routing planning |
| `routing_todo_report` | Routing priorities by subsystem/net class | Manual routing guidance |
| `board_connectivity_report` | Pad-net assignment correctness | Distinguishes generator bug vs unrouted board |
| `pin_pad_match_report` | Symbol pin vs XML vs footprint pad analysis | Prevents pin/pad mismatches |
| `asset_report` | Symbols/footprints/models used | Asset localization and path compliance |

## 🧩 Common JSON Envelope

Many CLI JSON responses use this shape:

```json
{
  "ok": true,
  "command": "nexapcb report all",
  "status": "OK",
  "data": {},
  "issues": [],
  "reports": {},
  "next_action": "Read final_result.json first."
}
```

Error responses use:

```json
{
  "ok": false,
  "command": "nexapcb export",
  "status": "FAILED",
  "error": {
    "code": "XML_NOT_FOUND",
    "message": "XML export file is missing.",
    "likely_cause": "SKiDL export did not run successfully.",
    "suggested_fix": "Run nexapcb stage skidl-export or nexapcb export again."
  },
  "issues": []
}
```

## 📄 Report Details

### `final_result.json` / `final_result.md`

**Purpose:** final status summary for the command run.

**Typical fields:**

- `project_name`
- `source`
- `output`
- `status`
- `exit_code`
- `generated_files`
- `reports`
- `issue_counts`
- `erc_count`
- `drc_count`
- `unconnected_count`
- `pin_pad_mismatch_count`
- `absolute_path_violation_count`
- `next_recommended_action`

**AI usage:** read this first to decide whether to continue, inspect issues, or abort.

---

### `summary_report.json` / `summary_report.md`

**Purpose:** project summary at a glance.

**Typical fields:**

- project name
- component count
- footprint count
- net count
- status

**AI usage:** quick health check before deeper inspection.

---

### `check_report.json` / `check_report.md`

**Purpose:** source readiness before export.

**Typical fields:**

- source existence
- syntax status
- import status
- export-call presence
- asset references

**AI usage:** fix source/import/configuration problems before running full export.

---

### `ast_parse_report.json`

**Purpose:** source-level discovery of refs, fields, SKUs, and custom metadata.

**Typical fields:**

- discovered refs
- fields by ref
- SKU candidates
- custom asset fields
- imported modules

**AI usage:** confirm what the source appears to define before SKiDL execution.

---

### `skidl_export_report.json`

**Purpose:** execution status of SKiDL and generated XML/netlist outputs.

**Typical fields:**

- executed source path
- working directory
- generated files
- stdout/stderr summary
- export status

**AI usage:** determine whether failure occurred before or after SKiDL execution.

---

### `netlist_report.json` / `netlist_report.md`

**Purpose:** structured parsed XML/netlist summary.

**Typical fields:**

- component count
- net count
- node count
- XML parse status
- parse warnings

**AI usage:** validate that SKiDL produced a usable connectivity graph.

---

### `component_report.json` / `component_report.md`

**Purpose:** one entry per component.

**Typical fields:**

- `ref`
- `value`
- `library`
- `footprint`
- `symbol_source`
- `footprint_source`
- `SKU`
- `SKU_PROVIDER`
- `NO_SKU_REASON`
- custom asset paths
- `pin_count`
- `pad_count`
- `warnings`

**AI usage:** inspect sourcing metadata, custom assets, and part-by-part mismatches.

[!NOTE]
No-SKU parts are not electrical failures. They are sourcing/import metadata gaps unless a workflow requires a catalog import.

---

### `connection_report.json` / `connection_report.md`

**Purpose:** all nets and their connected nodes.

**Typical fields:**

- net name
- node count
- nodes (`ref`, `pin`, `value`)
- critical-net flags
- single-node net flags

**AI usage:** debug connectivity without opening KiCad.

---

### `issue_report.json` / `issue_report.md`

**Purpose:** normalized issue feed across all stages.

**Typical issue object:**

```json
{
  "severity": "error",
  "stage": "erc",
  "code": "PIN_NOT_CONNECTED",
  "message": "U7 pin GPIO12 is not connected.",
  "file": "n_defender_clean.kicad_sch",
  "ref": "U7",
  "pin": "GPIO12",
  "pad": null,
  "net": null,
  "coordinate": null,
  "likely_cause": "SKiDL source did not connect this pin or mark it NC.",
  "suggested_fix": "Connect U7['GPIO12'] to the intended net or mark it as NoConnect if intentionally unused.",
  "raw": "..."
}
```

**AI usage:** primary actionable issue feed for fix loops.

---

### `validation_report.json` / `validation_report.md`

**Purpose:** overall artifact and pipeline correctness summary.

**Typical fields:**

- generated file existence
- component/symbol/footprint counts
- asset localization status
- absolute path status
- ERC status
- DRC status
- export classification:
  - `export_successful`
  - `export_successful_with_issues`
  - `export_failed`

**AI usage:** determine whether a run is usable, risky, or invalid.

---

### `erc_report.json` / `erc_report.md`

**Purpose:** normalized KiCad ERC output.

**Typical fields:**

- total violations
- breakdown by type
- affected refs/pins/nets
- normalized issues

**AI usage:** schematic repair loop.

---

### `drc_report.json` / `drc_report.md`

**Purpose:** normalized KiCad DRC output.

**Typical fields:**

- total violations
- breakdown by type
- unconnected count
- coordinates
- affected footprints/pads/nets

**AI usage:** distinguish design-state PCB issues from generation failures.

---

### `unconnected_report.json` / `unconnected_report.md`

**Purpose:** PCB unrouted/unconnected grouping.

**Typical fields:**

- total unconnected
- grouped by net
- grouped by ref
- critical nets first

**AI usage:** plan manual routing order without pretending the board is autorouted.

---

### `routing_todo_report.json` / `routing_todo_report.md`

**Purpose:** prioritized routing strategy.

**Typical fields:**

- grouped by subsystem
- grouped by net class
- critical net routing suggestions

**AI usage:** routing handoff and planning.

---

### `board_connectivity_report.json` / `board_connectivity_report.md`

**Purpose:** prove whether PCB pad nets were assigned correctly.

**Typical fields:**

- `matched_pad_nets`
- `missing_pad_net_count`
- `wrong_pad_net_count`
- pads without net
- per-ref connectivity detail

**AI usage:** distinguish a generator bug from a normal unrouted board.

---

### `pin_pad_match_report.json` / `pin_pad_match_report.md`

**Purpose:** compare symbol pins, XML/SKiDL pins, and footprint pads.

**Typical fields:**

- symbol pin count
- footprint pad count
- matched mappings
- missing pads
- missing pins
- candidate mappings
- rewrite suggestions

**AI usage:** correct symbol/footprint mismatches before chasing PCB issues.

---

### `asset_report.json` / `asset_report.md`

**Purpose:** symbol, footprint, and 3D model usage and localization.

**Typical fields:**

- all symbols used
- all footprints used
- all models used
- missing assets
- absolute path issues
- `${KIPRJMOD}` rewrite status

**AI usage:** validate assets and custom part handling.

## ✅ Checklist

- Read `final_result.json` first
- Use `issue_report.json` for actionable fixes
- Use `pin_pad_match_report.json` before changing pin labels
- Use `board_connectivity_report.json` before blaming unrouted boards on net assignment
- Use JSON for automation, Markdown for human review

## ⚠️ Common mistakes

| Mistake | Why it hurts | Better approach |
|---|---|---|
| Reading only Markdown in automation | Harder to parse reliably | Prefer JSON |
| Treating no-SKU parts as electrical failures | Confuses sourcing with connectivity | Check `NO_SKU_REASON` and sourcing policy |
| Treating unrouted boards as generator failures | Normal on first-pass boards | Read `board_connectivity_report` first |
| Ignoring `final_result.json` | Misses top-level status | Read it before any other report |

## 🔗 Related docs

- [CLI Reference](./CLI_REFERENCE.md)
- [AI Agent Workflow](./AI_AGENT_WORKFLOW.md)
- [SKiDL Format Guide](./SKIDL_FORMAT_GUIDE.md)
- [Custom Parts](./CUSTOM_PARTS.md)
