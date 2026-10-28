# M04-L06: Masking at the tool boundary vs. the log boundary

Module: M04 Pillar 2, Data Protection · Type: Code-along

`final/boundaries_demo.py` runs the same eight-request review three ways and counts the patient identifiers
that reach the model and the audit log:

| Configuration | Model saw | Audit log |
|---|---|---|
| A. No masking (M03 key redaction only) | 68 | 35 |
| B. Log boundary only (`AuditHooks(redactor=PrivacyRedactor(...))`) | 68 | 4 |
| C. Tool boundary (minimized tool) + log boundary | 0 | 0 |

```bash
uv run python lessons/M04-L06_masking-at-the-tool-boundary-vs-the-log/final/boundaries_demo.py
```
Code walked through on screen: `src/sentinel/privacy/minimize.py`, `pa_tools.py`, and the `redactor=` parameter in `src/sentinel/audit/hooks.py`.
