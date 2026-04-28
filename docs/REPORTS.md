# Reports

NexaPCB is report-first. The output project is important, but the reports are what users and AI agents read to decide the next fix.

All reports live under:

```text
output/reports/
```

## Core reports

### `summary_report`
- purpose: high-level project summary
- key fields:
  - project name
  - component count
  - footprint count
  - net count
  - status

### `check_report`
- purpose: source readiness before export
- key fields:
  - source existence
  - syntax status
  - import status
  - SKiDL export-call presence
  - custom asset references

### `ast_parse_report`
- purpose: source-level discovery of refs, fields, SKUs, custom metadata

### `skidl_export_report`
- purpose: source execution and generated output summary

### `netlist_report`
- purpose: parsed XML/netlist summary
- key fields:
  - components
  - nets
  - nodes

### `component_report`
- purpose: one row/object per component
- key fields:
  - ref
  - value
  - footprint
  - symbol source
  - footprint source
  - LCSC
  - custom asset metadata
  - warnings

### `connection_report`
- purpose: net-to-node connectivity
- key fields:
  - net name
  - nodes
  - node count
  - likely single-node / unconnected nets

### `issue_report`
- purpose: normalized issues across stages
- key fields:
  - severity
  - stage
  - code
  - message
  - file
  - ref
  - pin
  - pad
  - net
  - coordinate
  - likely_cause
  - suggested_fix
  - raw

### `validation_report`
- purpose: final artifact and pipeline correctness summary
- key fields:
  - file existence
  - component/symbol/footprint counts
  - path checks
  - ERC/DRC status
  - export success classification

### `erc_report`
- purpose: normalized KiCad ERC report

### `drc_report`
- purpose: normalized KiCad DRC report

### `unconnected_report`
- purpose: board-level unrouted/unconnected grouping

### `routing_todo_report`
- purpose: routing priorities by subsystem/net class

### `board_connectivity_report`
- purpose: distinguish missing pad-net assignment from normal unrouted state

### `pin_pad_match_report`
- purpose: compare symbol pins, XML/SKiDL pins, and footprint pads

### `asset_report`
- purpose: symbol/footprint/model availability and localization

### `final_result`
- purpose: first file an AI agent should read
- key fields:
  - status
  - generated files
  - report paths
  - issue counts
  - erc_count
  - drc_count
  - unconnected_count
  - pin_pad_mismatch_count
  - next recommended action

## How AI should use reports

Suggested read order:
1. `final_result.json`
2. `validation_report.json`
3. `issue_report.json`
4. `pin_pad_match_report.json`
5. `erc_report.json`
6. `drc_report.json`
7. `unconnected_report.json`
8. focused queries:
   - `nexapcb ref show`
   - `nexapcb net show`
   - `nexapcb issue by-code`

## Markdown vs JSON

- JSON is for automation
- Markdown is for human scanning and code review

AI agents should prefer JSON whenever available.
