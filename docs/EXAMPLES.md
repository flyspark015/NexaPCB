# 🧪 NexaPCB Examples and Fixtures
> A catalog of example projects and negative fixtures used for learning, smoke tests, and QA.

## 🧭 Overview

NexaPCB includes:

- **examples** for happy-path learning
- **fixtures** for automated regression tests
- **negative fixtures** for proving that failures are reported clearly

## 📚 Example Catalog

| Example | Difficulty | Teaches | Typical command |
|---|---|---|---|
| `rc_filter` | Beginner | One-file SKiDL, basic export, SKU smoke test | `nexapcb examples --create rc_filter --output /tmp/rc_filter_example` |
| `modular_esp32` | Intermediate | Multi-file modular SKiDL project structure | `nexapcb examples --create modular_esp32 --output /tmp/modular_esp32_example` |
| `custom_part_demo` | Intermediate | Custom symbol/footprint/model localization | `nexapcb examples --create custom_part_demo --output /tmp/custom_part_example` |

## 🚫 Negative Fixtures

| Fixture | Purpose | Expected behavior |
|---|---|---|
| `bad_unconnected_pins` | Proves issue/ERC reporting for design-state problems | Export may succeed, issues must be reported |
| `bad_pin_pad_mismatch` | Proves symbol/pad mismatch analysis | Export/report should explain mismatch clearly |
| `bad_missing_custom_asset` | Proves structured failure handling for missing custom files | Check/export should fail with actionable error |

## 🚀 Quick Usage

Create a built-in example:

```bash
.venv/bin/python -m nexapcb.cli examples
.venv/bin/python -m nexapcb.cli examples --create rc_filter --output /tmp/rc_filter_example
```

Then run:

```bash
.venv/bin/python -m nexapcb.cli check all --source /tmp/rc_filter_example/main.py --output /tmp/rc_filter_out --format json
.venv/bin/python -m nexapcb.cli export --source /tmp/rc_filter_example/main.py --project-name rc_filter --output /tmp/rc_filter_out --allow-issues
.venv/bin/python -m nexapcb.cli report all --output /tmp/rc_filter_out --format json
```

## 🧩 What Each Example Is For

### `rc_filter`

**Good for:**

- first-time install sanity check
- one-file SKiDL export flow
- report generation basics
- small LCSC/SKU smoke tests

**Use when:**

- validating the tool on the smallest possible design

---

### `modular_esp32`

**Good for:**

- testing modular imports
- verifying `--project-root` + `--entry`
- proving multi-file SKiDL support

**Use when:**

- you are building a real project split across `power.py`, `mcu.py`, `connectors.py`, etc.

---

### `custom_part_demo`

**Good for:**

- custom asset localization
- `${KIPRJMOD}` rewriting
- `part inspect` / `part compare`
- asset report validation

**Use when:**

- you need to verify custom symbols, footprints, or models before wiring a real board

## 🧠 Suggested Learning Order

1. `rc_filter`
2. `modular_esp32`
3. `custom_part_demo`
4. negative fixtures
5. stress-test projects such as N-Defender

## ✅ Checklist

- Start with a happy-path example first
- Use negative fixtures to verify failure reporting
- Use `custom_part_demo` before trusting custom asset flows
- Treat stress-test projects as report-quality tests, not as “finished boards”

## ⚠️ Common mistakes

| Mistake | Why it is wrong | Better approach |
|---|---|---|
| Starting with a complex board first | Too many variables at once | Start with `rc_filter` |
| Treating negative fixtures as bugs to fix | They exist to test reporting quality | Verify failure messages instead |
| Skipping `custom_part_demo` before using custom assets | Easy way to miss path/localization issues | Test custom assets in isolation first |

## 🔗 Related docs

- [QA Test Plan](./QA_TEST_PLAN.md)
- [AI Agent Workflow](./AI_AGENT_WORKFLOW.md)
- [Custom Parts](./CUSTOM_PARTS.md)
- [Part Request System](./PART_REQUEST_SYSTEM.md)
