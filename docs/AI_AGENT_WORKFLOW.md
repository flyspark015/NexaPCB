# AI Agent Workflow

NexaPCB is designed for iterative AI repair loops. It reports problems; it does not silently complete a complex board for you.

## Canonical loop

1. AI writes or updates modular SKiDL.
2. Run:

```bash
nexapcb check all --source path/to/main.py --output /tmp/out --format json
```

3. Read:
- `check_report.json`
- `issue_report.json`

4. Fix SKiDL or custom assets.

5. Run:

```bash
nexapcb export --source path/to/main.py --project-name my_board --output /tmp/out --allow-issues
```

6. Read first:
- `reports/final_result.json`

7. Then read focused reports:
- `validation_report.json`
- `erc_report.json`
- `drc_report.json`
- `pin_pad_match_report.json`
- `issue_report.json`
- `board_connectivity_report.json`

8. Use focused commands:

```bash
nexapcb issue by-code --output /tmp/out --code PIN_PAD_MISMATCH --format json
nexapcb ref show --output /tmp/out --ref U7 --format json
nexapcb net show --output /tmp/out --net SYS_3V3 --format json
nexapcb part inspect --symbol file.kicad_sym --symbol-name MY_PART --footprint file.kicad_mod --output /tmp/part_study
```

9. Fix the source.
10. Repeat until acceptable.
11. Human opens KiCad for final engineering review.

## JSON-first behavior

AI agents should prefer:
- `--format json`
- `report all --format json`
- `final_result.json`

Do not scrape Markdown unless you specifically need human-readable summaries.

## Design issue vs tool bug

Treat these as design issues:
- unrouted board
- intentional NC pins
- power pin not driven in the design
- pad connected but no track routed

Treat these as tool bugs:
- missing reports
- wrong/missing refs in reports
- wrong pin/pad analysis
- missing generated files
- incorrect exit code
- broken modular imports
- stale or misleading report contents

## Part study before wiring

Before wiring a part in SKiDL:

```bash
nexapcb part lookup --sku C25804 --output /tmp/part_lookup
```

or:

```bash
nexapcb part inspect --symbol part.kicad_sym --symbol-name MY_PART --footprint part.kicad_mod --output /tmp/part_study
```

Then read:
- `symbol_pin_report.json`
- `footprint_pad_report.json`
- `pin_pad_compare_report.json`
- `skidl_usage_report.json`

This prevents avoidable pin-label and footprint mistakes before board export.
