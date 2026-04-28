

# ⚡ NexaPCB
> **SKiDL → KiCad automation with JLC/LCSC assets, custom parts, validation, Textual TUI, and MCP-ready control.**
NexaPCB converts **Python-based SKiDL circuit descriptions** into **portable KiCad projects** with imported symbols, PCB footprints, 3D models, validation reports, and `${KIPRJMOD}`-based project-local paths.
---
## 🚀 What NexaPCB Does
NexaPCB helps developers write circuits as code and generate a KiCad project automatically.
It can:
- 🧠 Parse SKiDL Python source files
- 🔍 Extract LCSC/JLCPCB SKUs from component metadata
- 📦 Import real symbols, footprints, and 3D models using `JLC2KiCadLib`
- 📁 Copy all assets into the project folder
- 🔗 Rewrite 3D model paths to `${KIPRJMOD}`
- 🧩 Generate KiCad `.kicad_pro`, `.kicad_sch`, and `.kicad_pcb`
- 🔁 Replace generic schematic symbols with imported JLC symbols
- 🛠 Support custom user-provided symbols, footprints, and 3D models
- ✅ Validate generated projects with strict checks
- 🖥 Provide a modern Textual terminal GUI
- 🤖 Provide MCP-ready JSON automation controls
---
## 🎯 Core Goal
The goal is **not** to generate random placeholder KiCad files.
The goal is to generate a **real, portable KiCad project** that can be moved to another computer and still opens without missing:
- schematic symbols
- PCB footprints
- 3D models
- project-local library links
- validation reports
---
## 🧱 Core Rules
### ✅ 1. Zero-Path Rule
Final KiCad files must **not** contain machine-specific absolute paths.
❌ Forbidden:
```text
/Users/...
/home/...
/tmp/...
/Applications/...
C:\...

✅ Required:

${KIPRJMOD}/symbols/...
${KIPRJMOD}/footprints/...
${KIPRJMOD}/3d_models/...

⸻

✅ 2. No-Guess Rule

If NexaPCB cannot safely match a symbol, footprint, pin, pad, or 3D model, it should fail and report clearly.

It should not silently guess.

⸻

✅ 3. Manual Layout Rule

NexaPCB does not try to autoroute or beautifully arrange the board.

The user manually handles:

* schematic visual cleanup
* PCB placement
* PCB routing
* final DRC/ERC review inside KiCad

NexaPCB handles:

* component existence
* references
* values
* symbols
* footprints
* 3D model links
* net connectivity
* validation reports

⸻

📂 Project Folder Structure

nexapcb/
├── nexapcb/
│   ├── __init__.py
│   ├── config.py
│   ├── ast_parser.py
│   ├── skidl_exporter.py
│   ├── xml_netlist_parser.py
│   ├── jlc_importer.py
│   ├── asset_localizer.py
│   ├── custom_asset_localizer.py
│   ├── fuzzy_matcher.py
│   ├── kicad_project_writer.py
│   ├── schematic_symbol_rewriter.py
│   ├── validator.py
│   ├── cli.py
│   ├── tui_app.py
│   ├── mcp_json_server.py
│   └── utils/
│       ├── fs.py
│       └── process.py
├── examples/
│   └── esp32_led_button_test.py
├── docs/
│   └── SKIDL_FORMAT_GUIDE.md
├── tui/
├── mcp_server/
├── workspace/
├── README.md
├── requirements.txt
├── pyproject.toml
├── LICENSE
└── .gitignore

⸻

📦 Generated KiCad Project Structure

Each generated KiCad project should look like this:

workspace/my_project/
├── my_project.kicad_pro
├── my_project.kicad_sch
├── my_project.kicad_pcb
├── netlist/
│   ├── my_project.net
│   └── my_project.xml
├── symbols/
│   ├── C82899_jlc_symbols.kicad_sym
│   ├── C25804_jlc_symbols.kicad_sym
│   └── custom/
├── footprints/
│   ├── imported_jlc_footprints.pretty/
│   └── custom.pretty/
├── 3d_models/
│   ├── ESP32-WROOM-32.step
│   ├── R0603.step
│   └── custom/
├── reports/
│   ├── ast_parse_report.json
│   ├── jlc_import_report.json
│   ├── localization_report.json
│   ├── custom_asset_report.json
│   ├── schematic_symbol_rewrite_report.json
│   ├── validation_report.json
│   └── validation_report.md
└── logs/

⸻

⚙️ Installation

1. Clone the repo

git clone https://github.com/YOUR_USERNAME/nexapcb.git
cd nexapcb

2. Create virtual environment

python3 -m venv .venv

3. Install dependencies

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
.venv/bin/python -m pip install JLC2KiCadLib

4. Verify installation

.venv/bin/python -c "import skidl; print('SKiDL OK')"
.venv/bin/python -c "import nexapcb; print('NexaPCB OK')"

⸻

🧪 Quick Test

Run the ESP32 LED/Button example:

.venv/bin/python -m nexapcb.cli \
  --source examples/esp32_led_button_test.py \
  --project-name esp32_led_button_test

Expected final result:

✅ status: jlc_mapped_kicad_project_generated
✅ ok: true

Open in KiCad:

workspace/esp32_led_button_test/esp32_led_button_test.kicad_pro

⸻

🧾 SKiDL Source Format

A NexaPCB SKiDL file is a normal Python file.

Minimum required structure:

from skidl import *
V3V3 = Net("+3V3")
GND = Net("GND")
R1 = Part("Device", "R", ref="R1", value="10k")
R1.fields["LCSC"] = "C25804"
C1 = Part("Device", "C", ref="C1", value="100nF")
C1.fields["LCSC"] = "C1525"
R1[1] += V3V3
R1[2] += C1[1]
C1[2] += GND
ERC()
generate_netlist(file_="example.net")
generate_xml(file_="example.xml")

Detailed rules are here:

docs/SKIDL_FORMAT_GUIDE.md

⸻

🔢 LCSC / JLCPCB SKU Metadata

Use this format:

R1.fields["LCSC"] = "C25804"
C1.fields["LCSC"] = "C1525"
U1.fields["LCSC"] = "C82899"

Accepted SKU format:

C + digits

Examples:

C25804
C1525
C82899

⸻

🧩 Custom Part Support

Use custom parts when:

* the component is not available through JLC2KiCadLib
* you already have your own .kicad_sym
* you already have your own .kicad_mod
* you already have your own .step, .stp, or .wrl model

Custom SKiDL metadata

U2 = Part("CustomLib", "MY_PART", ref="U2", value="My Custom Part")
U2.fields["CUSTOM_SYMBOL"] = "/path/to/my_symbols.kicad_sym"
U2.fields["CUSTOM_SYMBOL_NAME"] = "MY_PART"
U2.fields["CUSTOM_FOOTPRINT"] = "/path/to/MY_PART.kicad_mod"
U2.fields["CUSTOM_MODEL"] = "/path/to/MY_PART.step"

NexaPCB copies those into:

symbols/custom/
footprints/custom.pretty/
3d_models/custom/

Final paths become portable:

${KIPRJMOD}/symbols/custom/my_symbols.kicad_sym
custom:MY_PART
${KIPRJMOD}/3d_models/custom/MY_PART.step

⸻

🧰 CLI Usage

Full pipeline

.venv/bin/python -m nexapcb.cli \
  --source examples/esp32_led_button_test.py \
  --project-name esp32_led_button_test

With custom output folder

.venv/bin/python -m nexapcb.cli \
  --source examples/esp32_led_button_test.py \
  --project-name esp32_led_button_test \
  --project-root workspace/esp32_led_button_test

Validate only

.venv/bin/python -m nexapcb.cli \
  --project-name esp32_led_button_test \
  --project-root workspace/esp32_led_button_test \
  --validate-only

⸻

🖥 Textual Terminal GUI

Run:

.venv/bin/python -m nexapcb.tui_app

The GUI provides:

* ⚙️ project controls
* 📄 source file input
* 🏷 project name input
* 🚀 full pipeline button
* 🔍 stage-by-stage buttons
* 📡 live logs
* 📊 validation table
* 📁 project file tree
* ✅ status cards

Keyboard shortcuts:

f = run full pipeline
v = validate
r = refresh
c = clear log
q = quit

⸻

🤖 MCP-Ready JSON Control

Run project summary:

echo '{"tool":"project_summary","project_name":"esp32_led_button_test"}' \
| .venv/bin/python -m nexapcb.mcp_json_server

Run full pipeline:

echo '{"tool":"full_pipeline","source":"examples/esp32_led_button_test.py","project_name":"esp32_led_button_test"}' \
| .venv/bin/python -m nexapcb.mcp_json_server

Supported tools:

status
file_tree
list_reports
read_report
read_file
ast_parse
skidl_export
jlc_import
localize_assets
localize_custom_assets
generate_kicad
rewrite_symbols
validate
project_summary
full_pipeline

⸻

✅ Validation

Validation checks:

* required KiCad files exist
* XML component count is not zero
* schematic symbol count matches XML component count
* PCB footprint count matches XML component count
* SKU parts use JLC schematic symbols
* SKU parts use imported JLC footprints
* custom parts use custom footprint paths
* 3D model links are portable
* no absolute paths remain
* no legacy KiCad arc syntax remains
* no invalid old width syntax remains
* no missing fp_poly fill remains

Successful status:

jlc_mapped_kicad_project_generated

⸻

📊 Reports

NexaPCB writes reports into:

workspace/<project_name>/reports/

Important reports:

Report	Purpose
ast_parse_report.json	Parsed refs, SKUs, custom metadata
jlc_import_report.json	JLC2KiCadLib import result
localization_report.json	Localized JLC asset paths
custom_asset_report.json	Custom asset localization result
schematic_symbol_rewrite_report.json	Schematic JLC symbol replacement result
validation_report.json	Machine-readable validation result
validation_report.md	Human-readable validation report

⸻

❌ Common Errors and Meaning

MISSING_FILE

A required output file is missing.

Example:

MISSING_FILE:kicad_sch

Fix:

Run KiCad generation stage.

⸻

XML_COMPONENT_COUNT_ZERO

The SKiDL XML file has no components.

Fix:

Check that parts are created before generate_xml().

⸻

XML_NOT_FOUND

The expected XML file does not exist.

Common cause:

Project name is esp32, but SKiDL generated esp32_led_button_test.xml.

Fix:

NexaPCB should create canonical project-name copies:
netlist/esp32.xml
netlist/esp32.net

⸻

SKU_PART_NOT_USING_JLC_SYMBOL

A SKU part still uses a generic schematic symbol.

Fix:

Run schematic symbol rewrite stage.
Check localization_report.json has symbol_files.

⸻

SKU_PART_NOT_USING_IMPORTED_FOOTPRINT

A SKU part does not use imported JLC footprint.

Fix:

Check jlc_import_report.json and localization_report.json.

⸻

ABSOLUTE_PATH_FOUND

Generated files contain /Users/..., /home/..., /tmp/..., or C:\....

Fix:

Asset paths must be rewritten to ${KIPRJMOD}.

⸻

LEGACY_ARC_ANGLE_SYNTAX_FOUND

Imported footprint contains old KiCad arc syntax.

Fix:

Convert old (angle ...) syntax to modern KiCad arc format.

⸻

LEGACY_NON_STROKE_WIDTH_SYNTAX_FOUND

Imported footprint contains old (width ...) drawing syntax.

Fix:

Convert to modern (stroke (width ...) (type solid)).

⸻

FP_POLY_MISSING_FILL

An fp_poly block has no fill declaration.

Fix:

Add (fill solid) or (fill none).

⸻

JLC_IMPORT_FAILED

JLC2KiCadLib failed to import a part.

Possible causes:

* wrong SKU
* network issue
* JLC2KiCadLib not installed
* part unavailable in JLC database

⸻

🧠 Mistakes This Project Avoids

We built these protections because earlier tests hit real problems:

Mistake	Protection
SKiDL generated XML with different filename	Canonical project-name XML/NET copy
Schematic used generic symbols for SKU parts	Schematic symbol rewriter
PCB had old KiCad syntax	Footprint syntax cleaner
3D model paths used absolute paths	${KIPRJMOD} rewriting
JLC2KiCadLib command not found	Python/CLI detection
Wrong Python interpreter used	SKiDL interpreter detection
Generic fallback hidden silently	Validator catches it
Custom files not copied	Custom asset localizer

⸻

🛣 Roadmap

* Finish clean one-command orchestrator
* Add official MCP SDK server
* Add Textual custom asset manifest UI
* Add KiCad CLI ERC/DRC integration
* Add advanced pin/pad fuzzy matching report
* Add multi-unit symbol support
* Add more examples: STM32, ESP32-S3, USB-C, power supply
* Add package installer
* Add GitHub Actions CI

⸻

📜 License

MIT License.

⸻

⚠️ Status

NexaPCB is currently in early development.

Use it for automation and validation experiments, but always manually inspect final KiCad output before manufacturing.

---
## File 2 — SKiDL Format Guide
### Full path
```text
/Users/surajbhati/nexapcb/docs/SKIDL_FORMAT_GUIDE.md

Code

# 🧾 NexaPCB SKiDL Format Guide
> **This guide explains exactly how to write SKiDL files for NexaPCB without making the mistakes we hit during development.**
---
## ✅ 1. Required File Type
Your circuit source must be a Python file:
```text
my_circuit.py

It must import SKiDL:

from skidl import *

Recommended also:

from pathlib import Path

⸻

✅ 2. Minimum Valid SKiDL File

from skidl import *
V3V3 = Net("+3V3")
GND = Net("GND")
R1 = Part("Device", "R", ref="R1", value="10k")
R1.fields["LCSC"] = "C25804"
C1 = Part("Device", "C", ref="C1", value="100nF")
C1.fields["LCSC"] = "C1525"
R1[1] += V3V3
R1[2] += C1[1]
C1[2] += GND
ERC()
generate_netlist(file_="example.net")
generate_xml(file_="example.xml")

⸻

🚨 3. Must-Have Rules

Rule 1 — Always generate .net

generate_netlist(file_="project_name.net")

Rule 2 — Always generate .xml

generate_xml(file_="project_name.xml")

Rule 3 — Use stable references

✅ Good:

R1 = Part(..., ref="R1")
C1 = Part(..., ref="C1")
U1 = Part(..., ref="U1")

❌ Bad:

R = Part(...)
C = Part(...)
U = Part(...)

Why bad?

The parser and validator need stable references to map SKiDL parts to KiCad schematic symbols and PCB footprints.

⸻

🏷 4. LCSC / JLCPCB SKU Format

Use this:

R1.fields["LCSC"] = "C25804"

Accepted keys:

R1.fields["LCSC"] = "C25804"
R1.fields["JLC"] = "C25804"
R1.fields["SKU"] = "C25804"
R1.fields["JLCPCB"] = "C25804"

Recommended key:

fields["LCSC"]

SKU must look like:

C + digits

Examples:

C25804
C1525
C82899

⸻

🧩 5. Example: Resistor + Capacitor

from skidl import *
V3V3 = Net("+3V3")
GND = Net("GND")
RC_NODE = Net("RC_NODE")
R1 = Part("Device", "R", ref="R1", value="10k")
R1.fields["LCSC"] = "C25804"
C1 = Part("Device", "C", ref="C1", value="100nF")
C1.fields["LCSC"] = "C1525"
R1[1] += V3V3
R1[2] += RC_NODE
C1[1] += RC_NODE
C1[2] += GND
ERC()
generate_netlist(file_="rc_test.net")
generate_xml(file_="rc_test.xml")

Expected:

R1 → imported JLC resistor symbol + R0603 footprint
C1 → imported JLC capacitor symbol + C0402 footprint

⸻

🧠 6. Example: ESP32 + LED + Button

from skidl import *
V3V3 = Net("+3V3")
GND = Net("GND")
EN = Net("EN")
BOOT = Net("BOOT_GPIO0")
LED_NET = Net("LED_GPIO2")
U1 = Part("RF_Module", "ESP32-WROOM-32", ref="U1", value="ESP32-WROOM-32")
U1.fields["LCSC"] = "C82899"
R1 = Part("Device", "R", ref="R1", value="1k_LED")
R1.fields["LCSC"] = "C25804"
R2 = Part("Device", "R", ref="R2", value="10k_EN_PULLUP")
R2.fields["LCSC"] = "C25804"
C1 = Part("Device", "C", ref="C1", value="100nF_DEC")
C1.fields["LCSC"] = "C1525"
D1 = Part("Device", "LED", ref="D1", value="STATUS_LED")
SW1 = Part("Switch", "SW_Push", ref="SW1", value="BOOT_BTN")
J1 = Part("Connector", "Conn_01x02", ref="J1", value="PWR_IN")
J1[1] += V3V3
J1[2] += GND
U1["3V3"] += V3V3
U1["GND"] += GND
U1["EN"] += EN
U1["GPIO0"] += BOOT
U1["GPIO2"] += LED_NET
R2[1] += V3V3
R2[2] += EN
C1[1] += V3V3
C1[2] += GND
SW1[1] += BOOT
SW1[2] += GND
R1[1] += LED_NET
R1[2] += D1[1]
D1[2] += GND
ERC()
generate_netlist(file_="esp32_led_button_test.net")
generate_xml(file_="esp32_led_button_test.xml")

⸻

⚠️ 7. Filename Rule

This mistake caused real failure earlier.

If your project name is:

esp32

But your SKiDL file generates:

generate_xml(file_="esp32_led_button_test.xml")

Then the writer may expect:

netlist/esp32.xml

But SKiDL produced:

netlist/esp32_led_button_test.xml

NexaPCB should fix this by creating canonical copies:

netlist/esp32.xml
netlist/esp32.net

Still, best practice is to keep names aligned:

✅ Best:

generate_netlist(file_="esp32.net")
generate_xml(file_="esp32.xml")

And run:

nexapcb --project-name esp32

⸻

🧱 8. Custom Part Format

Use custom parts when you already have your own KiCad files.

Supported files:

Symbol:    .kicad_sym
Footprint: .kicad_mod or .pretty folder
3D Model:  .step, .stp, .wrl

Custom SKiDL metadata

U2 = Part("CustomLib", "MY_PART", ref="U2", value="My Custom Part")
U2.fields["CUSTOM_SYMBOL"] = "/absolute/path/to/my_symbols.kicad_sym"
U2.fields["CUSTOM_SYMBOL_NAME"] = "MY_PART"
U2.fields["CUSTOM_FOOTPRINT"] = "/absolute/path/to/MY_PART.kicad_mod"
U2.fields["CUSTOM_MODEL"] = "/absolute/path/to/MY_PART.step"

NexaPCB copies files into:

symbols/custom/
footprints/custom.pretty/
3d_models/custom/

Final KiCad paths become:

${KIPRJMOD}/symbols/custom/my_symbols.kicad_sym
custom:MY_PART
${KIPRJMOD}/3d_models/custom/MY_PART.step

⸻

📄 9. Custom Manifest Alternative

If custom metadata is not inside SKiDL, use a JSON manifest:

{
  "U2": {
    "symbol": "/path/to/my_symbols.kicad_sym",
    "symbol_name": "MY_PART",
    "footprint": "/path/to/MY_PART.kicad_mod",
    "model": "/path/to/MY_PART.step"
  }
}

Run:

.venv/bin/python -m nexapcb.custom_asset_localizer \
  --project-root workspace/my_project \
  --manifest custom_manifest.json

⸻

🧷 10. Pin Connection Rules

Numeric pin connection

R1[1] += V3V3
R1[2] += GND

Named pin connection

U1["EN"] += EN
U1["GPIO0"] += BOOT

Multiple GND pins

If a part has multiple GND pins:

U1["GND"] += GND

or if required:

U1[2] += GND
U1[10] += GND

⸻

🧪 11. ERC Rule

Always run ERC before export:

ERC()

Then export:

generate_netlist(file_="my_project.net")
generate_xml(file_="my_project.xml")

⸻

🧼 12. Good Style

✅ Good:

V3V3 = Net("+3V3")
GND = Net("GND")
LED_NET = Net("LED_GPIO2")
BOOT = Net("BOOT_GPIO0")

❌ Bad:

n1 = Net()
n2 = Net()
x = Net()

Why?

Named nets make reports easier to debug.

⸻

🧨 13. Common Mistakes

Mistake 1 — No XML generated

❌ Bad:

generate_netlist(file_="test.net")

✅ Good:

generate_netlist(file_="test.net")
generate_xml(file_="test.xml")

⸻

Mistake 2 — No stable refs

❌ Bad:

Part("Device", "R")

✅ Good:

R1 = Part("Device", "R", ref="R1")

⸻

Mistake 3 — SKU stored in wrong place

❌ Bad:

R1.sku = "C25804"

✅ Good:

R1.fields["LCSC"] = "C25804"

⸻

Mistake 4 — Wrong SKU format

❌ Bad:

R1.fields["LCSC"] = "25804"

✅ Good:

R1.fields["LCSC"] = "C25804"

⸻

Mistake 5 — Custom asset path missing

❌ Bad:

U2.fields["CUSTOM_FOOTPRINT"] = "MY_PART.kicad_mod"

✅ Better:

U2.fields["CUSTOM_FOOTPRINT"] = "/full/path/to/MY_PART.kicad_mod"

NexaPCB will copy it and rewrite it to portable ${KIPRJMOD}.

⸻

Mistake 6 — Depending on machine-local KiCad libraries

❌ Bad:

Use symbol from /Users/suraj/Library/Application Support/kicad/...

✅ Good:

Copy symbol into project symbols/custom/
Use ${KIPRJMOD}

⸻

✅ 14. Recommended Final SKiDL Template

from skidl import *
# -----------------------------
# Nets
# -----------------------------
V3V3 = Net("+3V3")
GND = Net("GND")
# -----------------------------
# Parts
# -----------------------------
R1 = Part("Device", "R", ref="R1", value="10k")
R1.fields["LCSC"] = "C25804"
C1 = Part("Device", "C", ref="C1", value="100nF")
C1.fields["LCSC"] = "C1525"
# -----------------------------
# Connections
# -----------------------------
R1[1] += V3V3
R1[2] += C1[1]
C1[2] += GND
# -----------------------------
# Export
# -----------------------------
ERC()
generate_netlist(file_="my_project.net")
generate_xml(file_="my_project.xml")

⸻

🟢 15. Final Checklist Before Running NexaPCB

Before running NexaPCB, check:

[ ] File is .py
[ ] from skidl import * exists
[ ] All important parts have stable refs
[ ] SKU parts use fields["LCSC"]
[ ] SKU starts with C
[ ] Nets have readable names
[ ] ERC() is called
[ ] generate_netlist() is called
[ ] generate_xml() is called
[ ] Project name matches output filename where possible
[ ] Custom assets use valid full paths

⸻

✅ 16. Expected Successful Output

After NexaPCB runs correctly:

status: jlc_mapped_kicad_project_generated
ok: true
errors: []
warnings: []

Generated files:

my_project.kicad_pro
my_project.kicad_sch
my_project.kicad_pcb
reports/validation_report.json
reports/validation_report.md

Open in KiCad:

workspace/my_project/my_project.kicad_pro

⸻

⚠️ 17. Final Warning

Even if NexaPCB validation passes, always manually check in KiCad before manufacturing:

[ ] ERC
[ ] DRC
[ ] footprint orientation
[ ] pin mapping
[ ] 3D model alignment
[ ] board outline
[ ] copper clearance
[ ] net connectivity

NexaPCB automates generation, but it does not replace engineering review.

---
## File 3 — GitHub Repo Short Description
Use this for GitHub’s **Description** field:
```text
NexaPCB converts SKiDL Python circuit descriptions into portable KiCad projects with JLC/LCSC imports, local symbols, footprints, 3D models, validation, custom parts, Textual TUI, and MCP-ready automation.

⸻

File 4 — GitHub Topics

Use these GitHub topics:

skidl
kicad
pcb
eda
jlcpcb
lcsc
python
automation
textual
mcp
hardware
electronics
circuit-design

⸻

Create both files quickly

cd /Users/surajbhati/nexapcb
mkdir -p docs
# Open README for editing
nano README.md
# Open SKiDL guide for editing
nano docs/SKIDL_FORMAT_GUIDE.md

Current progress:

[███░░░░░░░] 30%
Progress changed: +10%
Current stage: GitHub-style README + SKiDL format guide prepared
Next: provide next code batch for exporter/importer/localizer/validator
