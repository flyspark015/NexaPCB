# Custom Parts

NexaPCB supports custom symbols, footprints, and 3D models without requiring a full board export first.

## Supported files

- `.kicad_sym`
- `.kicad_mod`
- `.pretty/`
- `.step`
- `.stp`
- `.wrl`

## SKiDL custom fields

```python
U1.fields["CUSTOM_SYMBOL"] = "/abs/path/my_symbols.kicad_sym"
U1.fields["CUSTOM_SYMBOL_NAME"] = "MY_SENSOR"
U1.fields["CUSTOM_FOOTPRINT"] = "/abs/path/MY_SENSOR.kicad_mod"
U1.fields["CUSTOM_MODEL"] = "/abs/path/MY_SENSOR.step"
```

## Manifest support

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
nexapcb export --source main.py --project-name my_board --output /tmp/out --custom-assets custom_assets.json
```

## How assets are copied

NexaPCB localizes custom assets into:

- `output/symbols/custom/`
- `output/footprints/custom.pretty/`
- `output/3d_models/custom/`

## `${KIPRJMOD}` rewriting

Generated KiCad artifacts should not keep absolute custom model paths. NexaPCB rewrites localized model references to `${KIPRJMOD}` paths where possible.

## Inspecting custom parts before export

```bash
nexapcb part inspect \
  --symbol /path/to/part.kicad_sym \
  --symbol-name MY_PART \
  --footprint /path/to/part.kicad_mod \
  --model /path/to/part.step \
  --output /tmp/part_study
```

## Comparing symbol pins to footprint pads

```bash
nexapcb part compare \
  --symbol /path/to/part.kicad_sym \
  --symbol-name MY_PART \
  --footprint /path/to/part.kicad_mod \
  --output /tmp/part_compare
```

## Common custom part errors

- `CUSTOM_SYMBOL_NOT_FOUND`
- `CUSTOM_FOOTPRINT_NOT_FOUND`
- `CUSTOM_MODEL_NOT_FOUND`
- `ABSOLUTE_PATH_FOUND`
- `PIN_PAD_MISMATCH`

Common causes:
- wrong file path
- wrong `CUSTOM_SYMBOL_NAME`
- symbol pins do not match footprint pads
- custom model exists but footprint model reference was not localized
