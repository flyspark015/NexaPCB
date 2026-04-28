# Examples and Fixtures

## Built-in examples

### `rc_filter`
- smallest working one-file example
- good for:
  - basic check/export/report testing
  - SKU import smoke test

### `modular_esp32`
- multi-file modular SKiDL project
- good for:
  - import-path testing
  - modular export pipeline testing

### `custom_part_demo`
- custom symbol/footprint/model localization example
- good for:
  - asset report testing
  - part inspect/compare flows

## Negative fixtures

### `bad_unconnected_pins`
- intentionally leaves design-state connectivity issues
- used to prove issue/erc reporting

### `bad_pin_pad_mismatch`
- intentionally creates symbol/pad mismatch conditions
- used to prove pin/pad analysis quality

### `bad_missing_custom_asset`
- intentionally references missing custom assets
- used to prove failure handling and actionable issue reports

## How to create examples

```bash
nexapcb examples
nexapcb examples --create rc_filter --output /tmp/rc_filter_example
```

## Recommended learning order

1. `rc_filter`
2. `modular_esp32`
3. `custom_part_demo`
4. negative fixtures
5. stress-test projects such as N-Defender
