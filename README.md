# NexaPCB

NexaPCB is a CLI-only SKiDL-to-KiCad export and reporting tool for hardware automation loops.

It is built for:
- normal users who want first-pass KiCad output from SKiDL
- PCB developers who need structured validation and issue reports
- AI coding agents that need machine-readable repair feedback
- scripts/CI jobs that need stable command/JSON behavior

## What NexaPCB does

- validates one-file and modular multi-file SKiDL projects
- executes SKiDL exports with the correct working directory and import path
- generates KiCad project files:
  - `.kicad_pro`
  - `.kicad_sch`
  - `.kicad_pcb`
- localizes custom symbols, footprints, and 3D models into project-local folders
- supports LCSC/JLCPCB SKU metadata when explicitly provided
- generates detailed JSON and Markdown reports for:
  - checks
  - connectivity
  - pin/pad mapping
  - asset localization
  - ERC/DRC
  - board connectivity
  - routing TODOs
- provides pre-design part study commands so a user or AI can inspect a part before wiring it in SKiDL

## What NexaPCB does not do

- it is **not** an autorouter
- it does **not** make a board manufacturing-ready automatically
- it does **not** replace datasheet review
- it does **not** guarantee a routed or production-clean PCB for complex projects
- it reports design and generation problems; it does not silently “fix” them

> ⚠️ Do not guess part SKUs or pin labels.
>
> For complex parts, always:
> 1. confirm the SKU from a supplier/catalog,
> 2. inspect the symbol pins,
> 3. compare the footprint pads,
> 4. then write SKiDL wiring.
>
> NexaPCB reports issues, but clean input produces much better KiCad output.

## Alpha status

NexaPCB is GitHub-ready as an alpha CLI/reporting tool.

That means:
- the CLI works
- reports are generated
- fixtures run
- negative tests produce actionable failures

It does **not** mean:
- every generated board is production-ready
- every stress-test design is fully routed or finalized

## Installation

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
```

Optional:

```bash
.venv/bin/python -m pip install JLC2KiCadLib
```

If KiCad CLI is installed, NexaPCB will automatically use it when it can find:
- `/Volumes/ToyBook/KiCad/KiCad.app/Contents/MacOS/kicad-cli`
- `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`

You can also pass:

```bash
--kicad-cli /path/to/kicad-cli
```

## Quick start

### 1. Check local readiness

```bash
.venv/bin/python -m nexapcb.cli doctor --format json
```

### 2. Run a simple example

```bash
.venv/bin/python -m nexapcb.cli check all \
  --source tests/fixtures/rc_filter/main.py \
  --output /tmp/nexapcb_rc_filter \
  --format json

.venv/bin/python -m nexapcb.cli export \
  --source tests/fixtures/rc_filter/main.py \
  --project-name rc_filter \
  --output /tmp/nexapcb_rc_filter \
  --allow-issues
```

### 3. Read the result bundle first

```bash
.venv/bin/python -m nexapcb.cli report final \
  --output /tmp/nexapcb_rc_filter \
  --format json
```

The first file an AI agent should read is:

```text
output/reports/final_result.json
```

## CLI overview

Top-level commands:

- `nexapcb doctor`
- `nexapcb version`
- `nexapcb explain`
- `nexapcb init`
- `nexapcb check`
- `nexapcb stage`
- `nexapcb export`
- `nexapcb report`
- `nexapcb inspect`
- `nexapcb erc`
- `nexapcb drc`
- `nexapcb part`
- `nexapcb asset`
- `nexapcb net`
- `nexapcb ref`
- `nexapcb issue`
- `nexapcb examples`
- `nexapcb help`

See:
- [docs/CLI_REFERENCE.md](docs/CLI_REFERENCE.md)

## One-file SKiDL example

```python
from skidl import *

VCC = Net("VCC")
OUT = Net("OUT")
GND = Net("GND")

R1 = Part("Device", "R", ref="R1", value="10k")
R1.footprint = "Resistor_SMD:R_0603_1608Metric"
R1.fields["LCSC"] = "C25804"

C1 = Part("Device", "C", ref="C1", value="100nF")
C1.footprint = "Capacitor_SMD:C_0603_1608Metric"
C1.fields["LCSC"] = "C1525"

R1[1] += VCC
R1[2] += OUT
C1[1] += OUT
C1[2] += GND

ERC()
generate_netlist(file_="rc_filter.net")
generate_xml(file_="rc_filter.xml")
```

## Modular multi-file SKiDL example

```text
skidl_project/
├── main.py
├── power.py
├── mcu.py
├── connectors.py
└── parts.py
```

`main.py`:

```python
from skidl import *
from power import build_power
from mcu import build_mcu

def build():
    nets = {
        "SYS_3V3": Net("SYS_3V3"),
        "GND": Net("GND"),
    }
    build_power(nets)
    build_mcu(nets)

build()
ERC()
generate_netlist(file_="my_board.net")
generate_xml(file_="my_board.xml")
```

Run it with:

```bash
.venv/bin/python -m nexapcb.cli export \
  --project-root /path/to/project \
  --entry skidl_project/main.py \
  --project-name my_board \
  --output /tmp/my_board_out
```

## Custom part example

In SKiDL:

```python
U1.fields["CUSTOM_SYMBOL"] = "/abs/path/my_symbols.kicad_sym"
U1.fields["CUSTOM_SYMBOL_NAME"] = "MY_SENSOR"
U1.fields["CUSTOM_FOOTPRINT"] = "/abs/path/MY_SENSOR.kicad_mod"
U1.fields["CUSTOM_MODEL"] = "/abs/path/MY_SENSOR.step"
```

Or manifest:

```json
{
  "U1": {
    "symbol": "/abs/path/my_symbols.kicad_sym",
    "symbol_name": "MY_SENSOR",
    "footprint": "/abs/path/MY_SENSOR.kicad_mod",
    "model": "/abs/path/MY_SENSOR.step"
  }
}
```

Use:

```bash
.venv/bin/python -m nexapcb.cli asset localize \
  --source /path/to/main.py \
  --output /tmp/my_board_out \
  --custom-assets /path/to/custom_assets.json
```

## LCSC / JLCPCB SKU example

```python
R1.fields["LCSC"] = "C25804"
```

Do not guess SKU values. Only use a confirmed match.

## 📦 Automatic Symbol / Footprint / 3D Model Import Using SKU

NexaPCB can use a supplier SKU/catalog reference to import or locate:
- schematic symbol
- PCB footprint
- 3D model, when available

“SKU” in NexaPCB means the catalog reference used to identify a part for importing symbols, footprints, and 3D models. In many JLC/LCSC/EasyEDA flows this is the `Cxxxxx` number. If future SemiNest SKU support is available, the same concept applies.

Accepted SKU/reference types conceptually include:
- LCSC SKU
- JLCPCB SKU
- EasyEDA/JLCEDA part number
- SemiNest SKU / `seminest.in` part reference
- future supported supplier SKU

Use normalized metadata when possible:

```python
R1 = Part("Device", "R", ref="R1", value="10k")
R1.footprint = "Resistor_SMD:R_0603_1608Metric"
R1.fields["MPN"] = "0603 10k resistor"
R1.fields["SKU"] = "C25804"
R1.fields["SKU_PROVIDER"] = "LCSC"
```

Backward-compatible aliases:

```python
R1.fields["LCSC"] = "C25804"
R1.fields["JLCPCB"] = "C25804"
R1.fields["EASYEDA"] = "C25804"
R1.fields["SEMINEST"] = "SNxxxxx"
```

Do **not** use the SKU as the electrical value.

Correct:

```python
R1 = Part("Device", "R", ref="R1", value="10k")
R1.footprint = "Resistor_SMD:R_0603_1608Metric"
R1.fields["MPN"] = "0603 10k resistor"
R1.fields["SKU"] = "C25804"
R1.fields["SKU_PROVIDER"] = "LCSC"
```

Wrong:

```python
R1 = Part("Device", "R", ref="R1", value="C25804")
```

Why wrong:
- `C25804` is a catalog reference, not the resistor value
- the electrical value should remain `10k`
- the SKU belongs in metadata fields

Currently implemented importer flow:
- LCSC / JLCPCB / EasyEDA style `Cxxxxx` catalog numbers

Other provider fields are documented for future/provider-specific integrations. They serve the same conceptual role as a catalog reference, but actual importer support depends on the provider.

## 🔎 SKU Confirmation Rule

Before adding a SKU to SKiDL, the user or AI should verify it from the supplier site or trusted catalog source.

For AI agents:
- search the supplier/catalog before adding SKU metadata
- confirm the SKU matches the exact MPN, value, and package
- do not guess SKUs
- if SKU is unknown, leave it blank and add:

```python
part.fields["NO_SKU_REASON"] = "SKU not confirmed"
```

Example:

```python
# SKU confirmed from supplier search.
R1.fields["SKU"] = "C25804"
R1.fields["SKU_PROVIDER"] = "LCSC"

# SKU not confirmed.
U7.fields["NO_SKU_REASON"] = "Exact LCSC/JLCPCB SKU not confirmed"
```

If browsing/catalog lookup is unavailable, the AI must not invent a SKU.

Study a part before wiring it:

```bash
.venv/bin/python -m nexapcb.cli part lookup \
  --sku C25804 \
  --output /tmp/part_c25804
```

## 🧠 Study Part Pins Before Wiring SKiDL

Before wiring a complex IC, module, or connector, inspect the actual imported symbol pins and footprint pads.

Use:

```bash
nexapcb part lookup --sku Cxxxxx --output part_cache/<part_name>
nexapcb part inspect --symbol path/to/symbol.kicad_sym --symbol-name SYMBOL_NAME --footprint path/to/footprint.kicad_mod --output part_cache/<part_name>
nexapcb part compare --symbol path/to/symbol.kicad_sym --symbol-name SYMBOL_NAME --footprint path/to/footprint.kicad_mod --output part_cache/<part_name>
nexapcb part pins --symbol path/to/symbol.kicad_sym --symbol-name SYMBOL_NAME --format json
nexapcb part pads --footprint path/to/footprint.kicad_mod --format json
nexapcb part skidl-snippet --input part_cache/<part_name> --ref U1
```

This prevents:
- wrong SKiDL pin labels
- symbol/footprint mismatch
- wrong pad names
- missing pins
- unconnected pins caused by guessed labels

### Safe wiring example

Step 1: lookup by SKU

```bash
nexapcb part lookup --sku C82899 --output part_cache/esp32_c82899
```

Step 2: read safe pin labels

```bash
nexapcb part report --input part_cache/esp32_c82899 --format json
```

Step 3: use only confirmed pin labels in SKiDL

```python
U1["3V3"] += SYS_3V3
U1["GND"] += GND
U1["EN"] += ESP_EN
```

Do not assume pin labels. Use what the symbol actually exposes.

## Normalized SKU fields

Recommended metadata schema:

```python
part.fields["MPN"] = "STM32F405RGT6TR"
part.fields["SKU"] = "Cxxxxx"
part.fields["SKU_PROVIDER"] = "LCSC"
part.fields["DATASHEET"] = "https://..."
part.fields["MANUFACTURER"] = "STMicroelectronics"
```

Supported legacy or alias fields:
- `LCSC`
- `JLCPCB`
- `JLC`
- `EASYEDA`
- `SEMINEST`
- `SKU`

## Part study before wiring

Before writing SKiDL for a complex part:

```bash
.venv/bin/python -m nexapcb.cli part inspect \
  --symbol /path/to/part.kicad_sym \
  --symbol-name MY_PART \
  --footprint /path/to/part.kicad_mod \
  --model /path/to/part.step \
  --output /tmp/part_study
```

Useful follow-ups:

```bash
.venv/bin/python -m nexapcb.cli part pins --symbol /path/to/part.kicad_sym --symbol-name MY_PART --format json
.venv/bin/python -m nexapcb.cli part pads --footprint /path/to/part.kicad_mod --format json
.venv/bin/python -m nexapcb.cli part compare --symbol /path/to/part.kicad_sym --symbol-name MY_PART --footprint /path/to/part.kicad_mod --output /tmp/part_compare
.venv/bin/python -m nexapcb.cli part skidl-snippet --input /tmp/part_compare --format json
```

## Custom asset fallback

If no SKU-based asset import exists, use custom assets:

```python
part.fields["CUSTOM_SYMBOL"] = "/path/to/symbol.kicad_sym"
part.fields["CUSTOM_SYMBOL_NAME"] = "MY_PART"
part.fields["CUSTOM_FOOTPRINT"] = "/path/to/footprint.kicad_mod"
part.fields["CUSTOM_MODEL"] = "/path/to/model.step"
```

Then run:

```bash
nexapcb asset localize --output out/project --custom-assets custom_assets.json
```

Final KiCad paths should use:
- `${KIPRJMOD}/symbols/custom/...`
- `${KIPRJMOD}/footprints/custom.pretty/...`
- `${KIPRJMOD}/3d_models/custom/...`

## Report overview

Main reports live under:

```text
output/reports/
```

Most important first-read files:

- `final_result.json`
- `validation_report.json`
- `issue_report.json`
- `pin_pad_match_report.json`
- `erc_report.json`
- `drc_report.json`
- `board_connectivity_report.json`
- `unconnected_report.json`

See:
- [docs/REPORTS.md](docs/REPORTS.md)

## AI agent workflow

Recommended loop:

1. write/update SKiDL
2. run `nexapcb check`
3. read `check_report.json`
4. run `nexapcb export`
5. read `final_result.json`
6. run focused commands:
   - `nexapcb report final`
   - `nexapcb issue list`
   - `nexapcb net show`
   - `nexapcb ref show`
   - `nexapcb part inspect`
7. fix the SKiDL or custom assets
8. repeat
9. human opens KiCad for final engineering review

See:
- [docs/AI_AGENT_WORKFLOW.md](docs/AI_AGENT_WORKFLOW.md)

## Common errors

- `SOURCE_FILE_NOT_FOUND`
- `PYTHON_SYNTAX_ERROR`
- `SKIDL_IMPORT_FAILED`
- `XML_NOT_FOUND`
- `NETLIST_NOT_FOUND`
- `CUSTOM_SYMBOL_NOT_FOUND`
- `CUSTOM_FOOTPRINT_NOT_FOUND`
- `CUSTOM_MODEL_NOT_FOUND`
- `PIN_PAD_MISMATCH`
- `ABSOLUTE_PATH_FOUND`
- `KICAD_CLI_NOT_FOUND`

Use:

```bash
.venv/bin/python -m nexapcb.cli explain --list
.venv/bin/python -m nexapcb.cli explain PIN_PAD_MISMATCH
```

## QA

Run the full QA plan:

```bash
cd /path/to/NexaPCB
tests/run_full_qa.sh
```

This writes:

```text
/tmp/nexapcb_qa/qa_summary.json
/tmp/nexapcb_qa/qa_summary.md
```

See:
- [docs/QA_TEST_PLAN.md](docs/QA_TEST_PLAN.md)
- [docs/EXAMPLES.md](docs/EXAMPLES.md)

## Final warning

NexaPCB is an export/reporting tool.

It is **not** a promise that a generated board is:
- routed
- manufacturable
- production-clean
- approved without human review

Complex boards still require:
- datasheet review
- schematic review
- placement review
- routing review
- ERC/DRC interpretation
- human engineering judgment
