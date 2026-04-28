# 🤖 AI Agent Workflow
> A practical repair loop for using NexaPCB as an AI-assisted SKiDL → KiCad export and reporting system.

[!WARNING]
NexaPCB is **not an autorouter** and does **not** make a board manufacturing-ready automatically. It reports issues so the AI or user can fix the source and assets intentionally.

## 🧭 Overview

NexaPCB is designed for iterative repair loops:

```text
Write or update SKiDL
   ↓
nexapcb check
   ↓
Fix source / assets
   ↓
nexapcb export --allow-issues
   ↓
Read final_result + reports
   ↓
Fix source / assets / mappings
   ↺ repeat
```

## ✅ Agent Rules

- Do **not** guess supplier SKUs.
- Do **not** guess symbol pin labels.
- Do **not** confuse a design issue with a tool bug.
- Do **not** treat an unrouted board as proof that the exporter failed.
- Use JSON outputs first; Markdown is secondary.
- Study complex parts before wiring them.

## 🔁 Canonical AI Loop

1. Select the **component MPN/value** first.
2. Confirm the **supplier/catalog SKU** if available.
3. Add SKU metadata only if confirmed.
4. Inspect complex parts before wiring:
   - `nexapcb part lookup`
   - `nexapcb part inspect`
   - `nexapcb part compare`
5. Use only confirmed symbol pin labels.
6. Write or update modular SKiDL.
7. Run:

```bash
.venv/bin/python -m nexapcb.cli check all --source workspace/my_board/skidl_project/main.py --output /tmp/my_board_check --format json
```

8. Read:
   - `check_report.json`
   - `issue_report.json`

9. Fix source, imports, or asset metadata.

10. Run:

```bash
.venv/bin/python -m nexapcb.cli export --source workspace/my_board/skidl_project/main.py --project-name my_board --output /tmp/my_board_out --allow-issues
```

11. Read **first**:
   - `reports/final_result.json`

12. Then read focused reports:
   - `validation_report.json`
   - `issue_report.json`
   - `pin_pad_match_report.json`
   - `component_report.json`
   - `connection_report.json`
   - `erc_report.json`
   - `drc_report.json`

13. Use focused commands when needed:

```bash
.venv/bin/python -m nexapcb.cli ref issues --output /tmp/my_board_out --ref U7 --format json
.venv/bin/python -m nexapcb.cli net show --output /tmp/my_board_out --net SYS_3V3 --format json
.venv/bin/python -m nexapcb.cli issue by-code --output /tmp/my_board_out --code PIN_PAD_MISMATCH --format json
.venv/bin/python -m nexapcb.cli part inspect --symbol path/to/part.kicad_sym --symbol-name MY_PART --footprint path/to/part.kicad_mod --output /tmp/part_study
```

14. Fix the source.
15. Repeat until the result is acceptable.
16. Human opens KiCad for final engineering review.

## 🔎 Study Parts Before Wiring

Before wiring a complex IC, module, or connector:

```bash
.venv/bin/python -m nexapcb.cli part lookup --sku C25804 --output /tmp/part_lookup
```

or:

```bash
.venv/bin/python -m nexapcb.cli part inspect --symbol path/to/part.kicad_sym --symbol-name MY_PART --footprint path/to/part.kicad_mod --output /tmp/part_study
```

Then read:

- `symbol_pin_report.json`
- `footprint_pad_report.json`
- `pin_pad_compare_report.json`
- `skidl_usage_report.json`

This prevents:

- wrong SKiDL pin labels
- wrong footprint selection
- symbol/footprint pad mismatches
- guessed pad names

## 📦 SKU Confirmation Rule

Before adding a supplier/catalog reference:

1. search the supplier catalog
2. confirm exact MPN/value/package
3. add SKU only when confirmed

Correct:

```python
R1.fields["SKU"] = "C25804"
R1.fields["SKU_PROVIDER"] = "LCSC"
```

If unconfirmed:

```python
U7.fields["NO_SKU_REASON"] = "Exact LCSC/JLCPCB SKU not confirmed"
```

[!IMPORTANT]
If browsing/catalog lookup is not available, the AI must **not invent a SKU**.

## 🧠 Use JSON First

For automation, prefer:

- `--format json`
- `report all --format json`
- `final_result.json`

JSON is the canonical machine interface.

Markdown is for:

- GitHub readability
- human review
- code review discussion

## ⚖️ Design Issue vs Tool Bug

| Treat as a design issue | Treat as a tool bug |
|---|---|
| Unrouted board | Missing report file |
| Intentional NC pin | Wrong or missing ref in report |
| Power pin not driven in the design | Wrong pin/pad mismatch analysis |
| Pad has net but no track | Missing generated KiCad files |
| Board needs manual routing | Broken modular imports |

[!TIP]
If `board_connectivity_report.json` shows pad nets are assigned correctly, an unrouted board is a design-state issue, not necessarily a generator failure.

## 🛠 Prompt Template For AI Agents

Use this pattern when driving NexaPCB:

```text
1. Update modular SKiDL source.
2. Confirm SKU only if exact supplier/catalog match is known.
3. Inspect complex parts before wiring.
4. Run nexapcb check all --format json.
5. Read issue_report.json and fix source-level problems.
6. Run nexapcb export --allow-issues.
7. Read final_result.json first.
8. Read pin_pad_match_report.json, component_report.json, connection_report.json, and issue_report.json.
9. Fix source and repeat.
10. Do not treat unrouted PCB state as a tool bug unless reports show missing net assignment or generation failure.
```

## ✅ Checklist

- Confirm MPN/value before SKU
- Confirm SKU before adding it
- Inspect part pins/pads before wiring
- Use JSON reports first
- Read `final_result.json` before deep-diving
- Separate design issues from tool bugs

## ⚠️ Common mistakes

| Mistake | Why it is wrong | Better approach |
|---|---|---|
| Guessing a supplier SKU | Causes wrong imported assets | Add `NO_SKU_REASON` until confirmed |
| Guessing a symbol pin label | Causes pin mismatches and ERC noise | Run `nexapcb part pins` first |
| Treating every DRC issue as exporter failure | First-pass boards are often unrouted | Check `board_connectivity_report.json` |
| Reading only Markdown in automation | Hard to parse reliably | Use `--format json` |

## 🔗 Related docs

- [Reports](./REPORTS.md)
- [Errors](./ERRORS.md)
- [Part Request System](./PART_REQUEST_SYSTEM.md)
- [SKiDL Format Guide](./SKIDL_FORMAT_GUIDE.md)
