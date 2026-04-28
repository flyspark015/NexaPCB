# 🧠 Part Request System
> Study a part before writing SKiDL so you do not guess symbol pins, footprint pads, or model availability.

## 🧭 Overview

The part-request system exists to prevent mistakes such as:
- wrong SKiDL pin labels
- symbol pin name vs pad number mismatch
- wrong footprint choice
- missing 3D model
- custom symbol / footprint mismatch
- incorrect assumptions about supplier imports

> [!IMPORTANT]
> Before wiring a complex part, ask NexaPCB what pins and pads actually exist.

## 🚀 Command table

| Command | Purpose |
|---|---|
| `part lookup` | Import / study a part by confirmed supplier SKU |
| `part inspect` | Inspect local symbol / footprint / model files |
| `part compare` | Compare symbol pins against footprint pads |
| `part request` | AI-friendly wrapper for lookup/inspect |
| `part report` | Read a study folder |
| `part pins` | Print symbol pins only |
| `part pads` | Print footprint pads only |
| `part skidl-snippet` | Generate a safe starter snippet |
| `part model-check` | Check model linkage |

## 📦 Lookup by SKU

```bash
.venv/bin/python -m nexapcb.cli part lookup --sku C25804 --output /tmp/part_c25804
```

Use this when you have a **confirmed** supplier/catalog SKU and want:
- imported symbol
- imported footprint
- imported 3D model if available
- a study bundle before wiring SKiDL

Current implemented importer flow:
- ✅ LCSC / JLCPCB / EasyEDA `Cxxxxx` catalog numbers
- ⚠️ other provider references are conceptually supported as catalog references, but importer support may remain provider-specific

## 🔎 Inspect local assets

```bash
.venv/bin/python -m nexapcb.cli part inspect \
  --symbol /path/to/my_symbol.kicad_sym \
  --symbol-name MY_PART \
  --footprint /path/to/MY_PART.kicad_mod \
  --model /path/to/MY_PART.step \
  --output /tmp/part_study
```

## 🔬 Compare symbol vs footprint

```bash
.venv/bin/python -m nexapcb.cli part compare \
  --symbol /path/to/my_symbol.kicad_sym \
  --symbol-name MY_PART \
  --footprint /path/to/MY_PART.kicad_mod \
  --output /tmp/part_compare
```

This command is the fastest way to catch:
- missing pads
- extra pads
- uncertain mappings
- incompatible symbol/footprint pairs

## 🤖 AI-friendly request entry point

```bash
.venv/bin/python -m nexapcb.cli part request --sku C25804 --output /tmp/part_req
```

or:

```bash
.venv/bin/python -m nexapcb.cli part request \
  --symbol /path/to/my_symbol.kicad_sym \
  --symbol-name MY_PART \
  --footprint /path/to/MY_PART.kicad_mod \
  --model /path/to/MY_PART.step \
  --output /tmp/part_req
```

## 📊 Report reading order

1. `part_summary_report.json`
2. `symbol_pin_report.json`
3. `footprint_pad_report.json`
4. `pin_pad_compare_report.json`
5. `skidl_usage_report.json`

## ✅ Safe SKiDL workflow

Step 1:

```bash
.venv/bin/python -m nexapcb.cli part lookup --sku C82899 --output part_cache/esp32_c82899
```

Step 2:

```bash
.venv/bin/python -m nexapcb.cli part report --input part_cache/esp32_c82899 --format json
```

Step 3:

```python
U1["3V3"] += SYS_3V3
U1["GND"] += GND
U1["EN"] += ESP_EN
```

> [!WARNING]
> Do not assume pin labels. Use only the labels the symbol actually exposes.

## ❌ Wrong pin-label example

Bad:

```python
U1["VIDEO"] += NET_VIDEO
```

Why bad:
- you do not know whether `VIDEO` exists in the symbol
- the symbol may expose `VID_IN`, `VIN`, or only numeric pins

Better:
- run `part pins`
- run `part compare`
- then wire only confirmed labels

## ✅ Checklist

- [ ] confirm SKU if using lookup
- [ ] inspect symbol pins
- [ ] inspect footprint pads
- [ ] compare symbol vs footprint
- [ ] read the generated SKiDL snippet
- [ ] wire only confirmed symbol pins

## 🔗 Related docs

- [SKIDL_FORMAT_GUIDE.md](SKIDL_FORMAT_GUIDE.md)
- [CUSTOM_PARTS.md](CUSTOM_PARTS.md)
- [REPORTS.md](REPORTS.md)
