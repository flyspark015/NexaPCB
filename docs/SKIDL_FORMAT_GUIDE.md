# SKiDL Format Guide

This guide defines the NexaPCB-compatible SKiDL shape.

## Required import

```python
from skidl import *
```

## One-file project structure

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

R1[1] += VCC
R1[2] += OUT
C1[1] += OUT
C1[2] += GND

ERC()
generate_netlist(file_="my_board.net")
generate_xml(file_="my_board.xml")
```

## Modular project structure

```text
skidl_project/
├── main.py
├── parts.py
├── power.py
├── mcu.py
├── connectors.py
└── passives.py
```

`main.py` should be the entry point:

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

## Stable refs

Use stable explicit refs:
- `U1`
- `R1`
- `C1`
- `J1`

Avoid random/generated refs in source when possible.

## Named nets

Always name important nets explicitly:

```python
SYS_3V3 = Net("SYS_3V3")
I2C_SCL = Net("I2C_SCL")
I2C_SDA = Net("I2C_SDA")
GND = Net("GND")
```

## Footprint assignment

Assign footprints explicitly:

```python
U1.footprint = "RF_Module:ESP32-S3-WROOM-1"
R1.footprint = "Resistor_SMD:R_0603_1608Metric"
```

## LCSC field

Only use confirmed SKU values:

```python
R1.fields["LCSC"] = "C25804"
```

Do not guess SKUs.

## Custom asset fields

Supported fields:

```python
U1.fields["CUSTOM_SYMBOL"] = "/abs/path/my_symbols.kicad_sym"
U1.fields["CUSTOM_SYMBOL_NAME"] = "MY_PART"
U1.fields["CUSTOM_FOOTPRINT"] = "/abs/path/MY_PART.kicad_mod"
U1.fields["CUSTOM_MODEL"] = "/abs/path/MY_PART.step"
```

Optional pin map field:

```python
Q1.fields["NEXAPCB_PINMAP"] = "B=1,C=2,E=3"
```

## Export calls

These calls must exist in the entry file:

```python
ERC()
generate_netlist(file_="my_board.net")
generate_xml(file_="my_board.xml")
```

## Filename rules

Recommended:
- `.net` and `.xml` should share the same stem
- file names should match the intended project name when possible

Example:
- `my_board.net`
- `my_board.xml`

## Pin access rules

Use the safest label form discovered from the symbol:

```python
U1["GPIO0"]
U1["3V3"]
U1[1]
```

If you are unsure, run:

```bash
nexapcb part pins --symbol file.kicad_sym --symbol-name MY_PART --format json
```

## No-connect guidance

Use explicit no-connect handling for intentionally unused pins in the source design instead of leaving ambiguity for the exporter. If you are using placeholder symbols, document intentionally unused pins clearly.

## Power net / power flag guidance

Do not assume ERC will infer power sources for complex placeholders.
- use explicit power source topology in SKiDL
- review ERC reports after export
- treat `power_pin_not_driven` as a report to resolve, not something to hide

## Examples

### RC filter

Use the `rc_filter` fixture for the smallest working pattern.

### ESP32 LED/button

Use the `esp32_led_button` style example for:
- MCU
- LED resistor
- button input

### Modular power + MCU split

Use `modular_esp32` for:
- multi-file imports
- split subsystem builders

## Mistakes to avoid

- missing `generate_netlist()` or `generate_xml()`
- relying on unstable/random refs
- using wrong pin labels without first inspecting the symbol
- using semantic connector pin names against numeric-only footprints without a pin-map
- guessing LCSC SKU values
- leaving custom asset paths broken
- assuming a generated board is production-ready automatically
