# 🧷 Custom Parts
> How to use custom symbols, footprints, and 3D models when catalog-based import is unavailable or insufficient.

## 🧭 Overview

Use custom assets when:
- no working SKU importer exists for the part
- the supplier/imported symbol is not suitable
- the footprint must be company-specific
- the 3D model must be preserved exactly

## 🧩 Supported asset types

| Asset | Supported forms |
|---|---|
| Symbol | `.kicad_sym` |
| Footprint | `.kicad_mod`, `.pretty/` |
| Model | `.step`, `.stp`, `.wrl` |

## 🛠 SKiDL custom fields

```python
U1.fields["CUSTOM_SYMBOL"] = "/abs/path/my_symbols.kicad_sym"
U1.fields["CUSTOM_SYMBOL_NAME"] = "MY_SENSOR"
U1.fields["CUSTOM_FOOTPRINT"] = "/abs/path/MY_SENSOR.kicad_mod"
U1.fields["CUSTOM_MODEL"] = "/abs/path/MY_SENSOR.step"
```

## 📄 Manifest format

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

Use with:

```bash
.venv/bin/python -m nexapcb.cli export \
  --source main.py \
  --project-name my_board \
  --output /tmp/out \
  --custom-assets custom_assets.json
```

## 🔄 Custom asset flow

```text
Custom symbol / footprint / model
   ↓
CUSTOM_* fields or manifest
   ↓
nexapcb asset localize
   ↓
${KIPRJMOD}-local assets in output project
```

## 📦 Localization behavior

NexaPCB copies custom assets into:
- `output/symbols/custom/`
- `output/footprints/custom.pretty/`
- `output/3d_models/custom/`

Expected final path forms:
- `${KIPRJMOD}/symbols/custom/...`
- `${KIPRJMOD}/footprints/custom.pretty/...`
- `${KIPRJMOD}/3d_models/custom/...`

> [!IMPORTANT]
> Final KiCad artifacts should not keep absolute custom asset paths.

## 🔎 Inspect before export

```bash
.venv/bin/python -m nexapcb.cli part inspect \
  --symbol /path/to/part.kicad_sym \
  --symbol-name MY_PART \
  --footprint /path/to/part.kicad_mod \
  --model /path/to/part.step \
  --output /tmp/part_study
```

## 🔬 Compare symbol pins to footprint pads

```bash
.venv/bin/python -m nexapcb.cli part compare \
  --symbol /path/to/part.kicad_sym \
  --symbol-name MY_PART \
  --footprint /path/to/part.kicad_mod \
  --output /tmp/part_compare
```

This avoids:
- wrong pin labels in source
- wrong footprint selection
- pad-number assumptions
- later pin/pad mismatch errors

## ✅ Before export checklist

- [ ] symbol file exists
- [ ] `CUSTOM_SYMBOL_NAME` is correct
- [ ] footprint file exists
- [ ] model exists if needed
- [ ] symbol pins reviewed
- [ ] footprint pads reviewed
- [ ] compare report checked

## ✅ After export checklist

- [ ] custom assets were copied into project-local folders
- [ ] `${KIPRJMOD}` paths are used
- [ ] `asset_report.json` shows no missing files
- [ ] `pin_pad_match_report.json` shows no unexpected mismatch

## ⚠️ Common mistakes

| Mistake | Result | Better approach |
|---|---|---|
| wrong `CUSTOM_SYMBOL_NAME` | symbol replacement fails | inspect symbol names first |
| absolute custom paths left in KiCad output | portability failure | run `asset localize` and recheck |
| using a custom symbol without comparing pads | pin/pad mismatch later | run `part compare` first |
| missing 3D file | model warnings | accept explicitly or supply a valid model |

## 🚨 Common custom part errors

- `CUSTOM_SYMBOL_NOT_FOUND`
- `CUSTOM_FOOTPRINT_NOT_FOUND`
- `CUSTOM_MODEL_NOT_FOUND`
- `ABSOLUTE_PATH_FOUND`
- `PIN_PAD_MISMATCH`

## 🔗 Related docs

- [PART_REQUEST_SYSTEM.md](PART_REQUEST_SYSTEM.md)
- [REPORTS.md](REPORTS.md)
- [ERRORS.md](ERRORS.md)
