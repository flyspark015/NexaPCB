# Part Request System

The part request system exists to prevent wiring mistakes before SKiDL code is written.

Typical problems it helps avoid:
- wrong SKiDL pin labels
- symbol pin name vs pad number mismatch
- wrong footprint choice
- missing 3D model
- custom symbol/footprint mismatch
- incorrect assumptions about LCSC/JLC imports

## Core commands

- `nexapcb part lookup`
- `nexapcb part inspect`
- `nexapcb part compare`
- `nexapcb part request`
- `nexapcb part report`
- `nexapcb part pins`
- `nexapcb part pads`
- `nexapcb part skidl-snippet`
- `nexapcb part model-check`

## Lookup by SKU

```bash
nexapcb part lookup --sku C25804 --output /tmp/part_c25804
```

Use this when you have a confirmed LCSC/JLCPCB SKU and want:
- imported symbol
- imported footprint
- imported 3D model if available
- a study bundle before wiring SKiDL

## Inspect local assets

```bash
nexapcb part inspect \
  --symbol /path/to/my_symbol.kicad_sym \
  --symbol-name MY_PART \
  --footprint /path/to/MY_PART.kicad_mod \
  --model /path/to/MY_PART.step \
  --output /tmp/part_study
```

## Compare symbol vs footprint

```bash
nexapcb part compare \
  --symbol /path/to/my_symbol.kicad_sym \
  --symbol-name MY_PART \
  --footprint /path/to/MY_PART.kicad_mod \
  --output /tmp/part_compare
```

## Request abstraction

`part request` is the AI-friendly entry point:

```bash
nexapcb part request --sku C25804 --output /tmp/part_req
```

or:

```bash
nexapcb part request \
  --symbol /path/to/my_symbol.kicad_sym \
  --symbol-name MY_PART \
  --footprint /path/to/MY_PART.kicad_mod \
  --model /path/to/MY_PART.step \
  --output /tmp/part_req
```

## Reports generated

- `part_summary_report.json/.md`
- `symbol_pin_report.json/.md`
- `footprint_pad_report.json/.md`
- `pin_pad_compare_report.json/.md`
- `model_report.json/.md`
- `skidl_usage_report.json/.md`

## How AI should use this

1. inspect or lookup the part first
2. read `symbol_pin_report.json`
3. read `footprint_pad_report.json`
4. read `pin_pad_compare_report.json`
5. use `skidl_usage_report.json` to start the SKiDL declaration
6. only then wire nets in the project

## Avoiding pin-label mismatch

Do not guess labels like:
- `U1["GPIO0"]`
- `Q1["B"]`
- `J1["VIDEO"]`

Inspect the symbol first, then compare against footprint pads. If the symbol uses semantic labels but the footprint uses numeric pads, use a verified pin map or numeric access only after confirming the mapping.
