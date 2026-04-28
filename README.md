# ⚡ NexaPCB
> CLI-first **SKiDL → KiCad** automation with structured reports for humans, scripts, and AI agents.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![KiCad](https://img.shields.io/badge/KiCad-CLI%20supported-005bbb)
![SKiDL](https://img.shields.io/badge/SKiDL-source%20of%20truth-2b8a3e)
![CLI](https://img.shields.io/badge/Interface-CLI%20only-6f42c1)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Alpha-orange)

NexaPCB converts **one-file** and **modular multi-file** SKiDL projects into KiCad projects and generates structured reports for:
- source validation
- symbol / footprint / 3D asset handling
- pin / pad compatibility
- ERC / DRC / connectivity
- AI-assisted repair loops

> [!WARNING]
> NexaPCB is **not** an autorouter and does **not** make a board manufacturing-ready automatically.
> It reports design and generation issues so a human or AI agent can fix them deliberately.

## 🧭 What NexaPCB is / is not

| ✅ NexaPCB is | ❌ NexaPCB is not |
|---|---|
| SKiDL-to-KiCad exporter | Autorouter |
| Report generator | Replacement for engineering review |
| AI feedback-loop tool | Guarantee of manufacturing readiness |
| CLI automation toolbox | “One-click finished PCB” tool |
| Part-study / pin-pad inspection helper | Datasheet replacement |

## 🚀 Fast start

### 1. Install

```bash
git clone https://github.com/flyspark015/NexaPCB.git
cd NexaPCB
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
```

Optional SKU importer dependency:

```bash
.venv/bin/python -m pip install JLC2KiCadLib
```

### 2. Check the local environment

```bash
.venv/bin/python -m nexapcb.cli doctor --format json
```

### 3. Run a first example

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

.venv/bin/python -m nexapcb.cli report final \
  --output /tmp/nexapcb_rc_filter \
  --format json
```

> [!TIP]
> The first file an AI agent should read is:
>
> `output/reports/final_result.json`

## 🔄 Core workflow

```text
SKiDL source
   ↓
nexapcb check
   ↓
nexapcb export
   ↓
KiCad project + reports
   ↓
AI/user fixes SKiDL
   ↺ repeat
```

## 🧰 Command overview

| Command | Purpose | Typical user |
|---|---|---|
| `nexapcb doctor` | Check local tool readiness | user / CI / AI |
| `nexapcb check` | Validate source before export | user / AI |
| `nexapcb export` | Run the full SKiDL → KiCad pipeline | user / AI / script |
| `nexapcb report` | Read normalized reports | user / AI |
| `nexapcb inspect` | Query source/output quickly | AI / developer |
| `nexapcb part inspect` | Inspect symbol / footprint / model before wiring | AI / user |
| `nexapcb issue list` | Query structured issues | AI / developer |
| `nexapcb net show` | Inspect a net directly | AI / developer |
| `nexapcb ref show` | Inspect a component directly | AI / developer |

See:
- [docs/CLI_REFERENCE.md](docs/CLI_REFERENCE.md)

## 🧩 One-file SKiDL example

```python
from skidl import *

VCC = Net("VCC")
OUT = Net("OUT")
GND = Net("GND")

R1 = Part("Device", "R", ref="R1", value="10k")
R1.footprint = "Resistor_SMD:R_0603_1608Metric"
R1.fields["MPN"] = "0603 10k resistor"
R1.fields["SKU"] = "C25804"
R1.fields["SKU_PROVIDER"] = "LCSC"

C1 = Part("Device", "C", ref="C1", value="100nF")
C1.footprint = "Capacitor_SMD:C_0603_1608Metric"
C1.fields["SKU"] = "C1525"
C1.fields["SKU_PROVIDER"] = "LCSC"

R1[1] += VCC
R1[2] += OUT
C1[1] += OUT
C1[2] += GND

ERC()
generate_netlist(file_="rc_filter.net")
generate_xml(file_="rc_filter.xml")
```

## 🧱 Modular multi-file SKiDL example

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

Export it with:

```bash
.venv/bin/python -m nexapcb.cli export \
  --project-root /path/to/project \
  --entry skidl_project/main.py \
  --project-name my_board \
  --output /tmp/my_board_out
```

## 📦 SKU-Based Symbol / Footprint / 3D Import

NexaPCB can use a supplier/catalog reference to import or locate:
- schematic symbols
- PCB footprints
- 3D models when available

“SKU” in NexaPCB means the catalog reference used to identify a part for importing symbols, footprints, and 3D models. In many JLC/LCSC/EasyEDA flows this is the `Cxxxxx` number. If future SemiNest SKU support is available, the same concept applies.

### Supported conceptually

- LCSC SKU
- JLCPCB SKU
- EasyEDA / JLCEDA part number
- SemiNest SKU / `seminest.in` part reference
- future provider-specific catalog references

### Currently implemented importer flow

- ✅ LCSC / JLCPCB / EasyEDA-style `Cxxxxx` catalog numbers
- ⚠️ Other provider fields are documented for future/provider-specific integrations

### Recommended normalized style

```python
R1 = Part("Device", "R", ref="R1", value="10k")
R1.footprint = "Resistor_SMD:R_0603_1608Metric"
R1.fields["MPN"] = "0603 10k resistor"
R1.fields["SKU"] = "C25804"
R1.fields["SKU_PROVIDER"] = "LCSC"
```

### Backward-compatible aliases

```python
R1.fields["LCSC"] = "C25804"
R1.fields["JLCPCB"] = "C25804"
R1.fields["EASYEDA"] = "C25804"
R1.fields["SEMINEST"] = "SNxxxxx"
```

> [!IMPORTANT]
> Do **not** use the SKU as the electrical value.

Correct:

```python
R1 = Part("Device", "R", ref="R1", value="10k")
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

## 🔎 SKU confirmation rule

Before adding a SKU to SKiDL, confirm it from the supplier site or trusted catalog source.

### AI / automation rules

- ✅ search the supplier/catalog before adding SKU metadata
- ✅ confirm the SKU matches the exact MPN, value, and package
- ❌ do not guess SKUs
- ✅ if SKU is unknown, leave it blank and record:

```python
part.fields["NO_SKU_REASON"] = "SKU not confirmed"
```

Confirmed example:

```python
R1.fields["SKU"] = "C25804"
R1.fields["SKU_PROVIDER"] = "LCSC"
```

Unconfirmed example:

```python
U7.fields["NO_SKU_REASON"] = "Exact LCSC/JLCPCB SKU not confirmed"
```

## 🧠 Study parts before wiring

Before wiring a complex IC, module, connector, or custom sensor, inspect the actual symbol pins and footprint pads.

### Command card

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

Step 1:

```bash
nexapcb part lookup --sku C82899 --output part_cache/esp32_c82899
```

Step 2:

```bash
nexapcb part report --input part_cache/esp32_c82899 --format json
```

Step 3:

```python
U1["3V3"] += SYS_3V3
U1["GND"] += GND
U1["EN"] += ESP_EN
```

> [!WARNING]
> Do not assume pin labels. Use what the symbol actually exposes.

## 🧷 Custom part example

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

Localize them:

```bash
.venv/bin/python -m nexapcb.cli asset localize \
  --source /path/to/main.py \
  --output /tmp/my_board_out \
  --custom-assets /path/to/custom_assets.json
```

Expected final paths:
- `${KIPRJMOD}/symbols/custom/...`
- `${KIPRJMOD}/footprints/custom.pretty/...`
- `${KIPRJMOD}/3d_models/custom/...`

## 📊 Reports that matter most

| Report | Why it matters |
|---|---|
| `final_result.json` | first file an AI agent should read |
| `issue_report.json` | normalized actionable issues |
| `pin_pad_match_report.json` | symbol/footprint compatibility |
| `component_report.json` | ref/value/footprint/SKU/custom asset summary |
| `connection_report.json` | net-level connectivity |
| `erc_report.json` | schematic violations |
| `drc_report.json` | PCB violations |
| `board_connectivity_report.json` | pad-net assignment vs unrouted state |

See:
- [docs/REPORTS.md](docs/REPORTS.md)

## 🤖 AI agent workflow

### Recommended loop

- [ ] choose component MPN/value first
- [ ] confirm SKU from supplier/catalog if available
- [ ] inspect or compare complex parts before wiring
- [ ] write / update SKiDL
- [ ] run `nexapcb check`
- [ ] run `nexapcb export --allow-issues`
- [ ] read `final_result.json`
- [ ] read `issue_report.json`, `pin_pad_match_report.json`, `component_report.json`, `connection_report.json`
- [ ] fix SKiDL or assets
- [ ] repeat
- [ ] human opens KiCad for final review

See:
- [docs/AI_AGENT_WORKFLOW.md](docs/AI_AGENT_WORKFLOW.md)

## 🧪 QA

Full QA script:

```bash
tests/run_full_qa.sh
```

QA summary files:
- `/tmp/nexapcb_qa/qa_summary.json`
- `/tmp/nexapcb_qa/qa_summary.md`

See:
- [docs/QA_TEST_PLAN.md](docs/QA_TEST_PLAN.md)
- [docs/EXAMPLES.md](docs/EXAMPLES.md)

## ⚠️ Common errors

Common failure categories:
- `SOURCE_FILE_NOT_FOUND`
- `PYTHON_SYNTAX_ERROR`
- `SKIDL_EXPORT_FAILED`
- `PIN_PAD_MISMATCH`
- `CUSTOM_SYMBOL_NOT_FOUND`
- `SKU_IMPORT_FAILED`
- `KICAD_CLI_NOT_FOUND`

Use:

```bash
nexapcb explain --list
nexapcb explain PIN_PAD_MISMATCH
```

## 🔗 Related docs

- [docs/CLI_REFERENCE.md](docs/CLI_REFERENCE.md)
- [docs/SKIDL_FORMAT_GUIDE.md](docs/SKIDL_FORMAT_GUIDE.md)
- [docs/CUSTOM_PARTS.md](docs/CUSTOM_PARTS.md)
- [docs/PART_REQUEST_SYSTEM.md](docs/PART_REQUEST_SYSTEM.md)
- [docs/REPORTS.md](docs/REPORTS.md)
- [docs/ERRORS.md](docs/ERRORS.md)
- [docs/AI_AGENT_WORKFLOW.md](docs/AI_AGENT_WORKFLOW.md)
- [docs/QA_TEST_PLAN.md](docs/QA_TEST_PLAN.md)
- [docs/EXAMPLES.md](docs/EXAMPLES.md)
