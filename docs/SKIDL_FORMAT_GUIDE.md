# 🧩 SKiDL Format Guide
> How to write NexaPCB-friendly SKiDL source for reliable export, reports, and AI-assisted repair loops.

## 🧭 Overview

This guide covers:
- one-file SKiDL projects
- modular multi-file projects
- stable refs and named nets
- SKU metadata
- custom asset metadata
- safe pin access rules
- export-call requirements

> [!IMPORTANT]
> Never use a supplier SKU as the electrical `value` of a part.

## 🚀 Golden template

```python
from skidl import *

SYS_3V3 = Net("SYS_3V3")
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

R1[1] += SYS_3V3
R1[2] += C1[1]
C1[2] += GND

ERC()
generate_netlist(file_="my_board.net")
generate_xml(file_="my_board.xml")
```

## 🧱 One-file project

Use one-file SKiDL when:
- the design is small
- you are prototyping quickly
- there are few reusable subsystems

### Requirements
- `from skidl import *`
- explicit named nets
- stable refs
- explicit footprints
- `ERC()`
- `generate_netlist(...)`
- `generate_xml(...)`

## 🏗 Modular project

```text
skidl_project/
├── main.py
├── parts.py
├── power.py
├── mcu.py
├── connectors.py
└── passives.py
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

> [!TIP]
> NexaPCB supports modular projects as long as the entry file is run with the correct working directory and import path through `nexapcb export` or `nexapcb check imports`.

## 🧩 Stable ref checklist

- ✅ use explicit refs like `U1`, `R1`, `C1`, `J1`
- ✅ keep refs stable across iterations when possible
- ❌ do not rely on random/generated refs unless unavoidable

## 🔌 Named net checklist

- ✅ explicitly name important rails and buses
- ✅ prefer `Net("SYS_3V3")` over anonymous nets for core signals
- ✅ use consistent net names across files

Example:

```python
SYS_3V3 = Net("SYS_3V3")
I2C_SCL = Net("I2C_SCL")
I2C_SDA = Net("I2C_SDA")
GND = Net("GND")
```

## 📦 Footprints

Always assign footprints explicitly:

```python
U1.footprint = "RF_Module:ESP32-S3-WROOM-1"
R1.footprint = "Resistor_SMD:R_0603_1608Metric"
```

## 📇 SKU metadata

In NexaPCB, “SKU” means the supplier/catalog reference used to locate importable symbols, footprints, and 3D models.

### Recommended normalized fields

```python
part.fields["MPN"] = "STM32F405RGT6TR"
part.fields["SKU"] = "Cxxxxx"
part.fields["SKU_PROVIDER"] = "LCSC"
part.fields["DATASHEET"] = "https://..."
part.fields["MANUFACTURER"] = "STMicroelectronics"
```

### Supported alias fields

- `LCSC`
- `JLCPCB`
- `JLC`
- `EASYEDA`
- `SEMINEST`
- `SKU`

### Current importer scope

- ✅ LCSC / JLCPCB / EasyEDA `Cxxxxx` flow
- ⚠️ other provider fields are conceptual/forward-looking unless importer support exists

### If SKU is not confirmed

```python
part.fields["NO_SKU_REASON"] = "SKU not confirmed"
```

> [!WARNING]
> Do not guess SKUs. If the exact catalog reference is unknown, leave it blank and record the reason.

## 🧷 Custom asset fields

```python
U1.fields["CUSTOM_SYMBOL"] = "/abs/path/my_symbols.kicad_sym"
U1.fields["CUSTOM_SYMBOL_NAME"] = "MY_PART"
U1.fields["CUSTOM_FOOTPRINT"] = "/abs/path/MY_PART.kicad_mod"
U1.fields["CUSTOM_MODEL"] = "/abs/path/MY_PART.step"
```

Optional verified pin-map:

```python
Q1.fields["NEXAPCB_PINMAP"] = "B=1,C=2,E=3"
```

## 🧠 Pin access rules

Safe forms:

```python
U1["GPIO0"]
U1["3V3"]
U1[1]
```

Before wiring a complex part:

```bash
nexapcb part lookup --sku C82899 --output part_cache/esp32_c82899
nexapcb part report --input part_cache/esp32_c82899 --format json
```

Use only the labels the symbol actually exposes.

## ⚡ Export-call requirements

These calls must exist in the entry file:

```python
ERC()
generate_netlist(file_="my_board.net")
generate_xml(file_="my_board.xml")
```

### Filename rule

- `.net` and `.xml` should use the same stem
- matching the intended project name is recommended

## 🔌 No-connect and power guidance

### No-connect
- ✅ explicitly mark intentionally unused pins in source or through supported metadata
- ❌ do not leave unused placeholder pins ambiguous

### Power
- ✅ define real source nets for regulators and supplies
- ✅ review `power_pin_not_driven` reports as design feedback
- ❌ do not hide power issues instead of understanding them

## 🛠 Examples

### RC filter
- smallest working example
- good for syntax/export/report smoke tests

### ESP32 LED/button
- good for MCU + GPIO + passive support structure

### Modular power + MCU split
- good for multi-file import and subsystem separation

## ⚠️ Common mistakes

| Mistake | Why it is wrong | Better approach |
|---|---|---|
| `value="C25804"` | SKU is not the electrical value | keep `value="10k"` and put SKU in metadata |
| guessed pin labels | may not exist in the symbol | inspect part pins first |
| semantic connector names on numeric footprint | pad mismatch risk | compare symbol vs footprint or use verified pin map |
| missing `generate_xml()` | later stages cannot parse nets/components | always call both export functions |
| broken custom asset paths | localization/import fails | verify with `asset scan` or `part inspect` |

## ✅ Pre-export checklist

- [ ] stable refs used
- [ ] named nets used for important signals
- [ ] footprints assigned explicitly
- [ ] SKU metadata added only when confirmed
- [ ] complex parts inspected before wiring
- [ ] `ERC()`, `generate_netlist()`, `generate_xml()` present

## 🔗 Related docs

- [CLI_REFERENCE.md](CLI_REFERENCE.md)
- [CUSTOM_PARTS.md](CUSTOM_PARTS.md)
- [PART_REQUEST_SYSTEM.md](PART_REQUEST_SYSTEM.md)
- [AI_AGENT_WORKFLOW.md](AI_AGENT_WORKFLOW.md)
