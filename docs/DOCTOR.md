# 🩺 NexaPCB Doctor
> Verify local environment readiness before debugging an export.

## 🧭 Overview

`nexapcb doctor` checks whether the local system is ready to run NexaPCB successfully.

It is intended for:

- fresh machine setup
- CI/environment debugging
- preflight checks before large exports
- AI agents validating local capability

## 🚀 Quick usage

```bash
.venv/bin/python -m nexapcb.cli doctor
.venv/bin/python -m nexapcb.cli doctor --format json
.venv/bin/python -m nexapcb.cli doctor --output /tmp/nexapcb_doctor
```

## 🧩 What doctor checks

| Check | Why it matters |
|---|---|
| Python version | Confirms runtime compatibility |
| Platform | Helps explain path/tooling behavior |
| SKiDL availability/version | Required for source execution |
| KiCad CLI availability/version | Required for ERC/DRC automation |
| JLC2KiCadLib availability | Required for SKU-based asset import |
| Output-folder writability | Required for report and artifact generation |
| Optional source-path existence | Helps catch bad path assumptions early |

## 📊 Outputs

Doctor writes:

- `doctor_report.json`
- `doctor_report.md`

Typical JSON fields:

- Python version
- platform
- SKiDL status
- KiCad CLI path/version
- JLC importer availability
- output writeability
- overall readiness status

## ✅ Checklist

- Run doctor on fresh setup
- Run doctor before debugging unexplained export failures
- Prefer `--format json` in automation

## ⚠️ Common mistakes

| Mistake | Why it is wrong | Better approach |
|---|---|---|
| Assuming KiCad CLI exists | ERC/DRC commands may fail later | Run `doctor` first |
| Assuming JLC importer exists | SKU import may fail later | Check doctor/importer status first |
| Debugging source issues before checking environment | Wastes time | Verify doctor output first |

## 🔗 Related docs

- [CLI Reference](./CLI_REFERENCE.md)
- [Errors](./ERRORS.md)
- [QA Test Plan](./QA_TEST_PLAN.md)
