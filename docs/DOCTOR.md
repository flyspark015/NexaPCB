# Doctor

`nexapcb doctor` checks whether the local system is ready to run NexaPCB.

## What it checks

- Python version
- platform
- SKiDL availability and version
- KiCad CLI availability and version
- JLC2KiCadLib availability and version
- output folder writeability
- optional source path existence

## Example

```bash
nexapcb doctor --output /tmp/nexapcb_doctor
```

## Reports

Doctor writes:
- `doctor_report.json`
- `doctor_report.md`

Use this before debugging a failing export if you suspect an environment or dependency problem.
