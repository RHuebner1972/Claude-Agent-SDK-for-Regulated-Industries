# M04-L04: Detection with Presidio, patterns and custom recognizers (MRN, NPI, account numbers)

Module: M04 Pillar 2, Data Protection · Type: Code-along

`final/detect_demo.py` compares three detection stages on the eight annotated prior-auth notes:

| Stage | What it adds | Recall |
|---|---|---|
| 1 | Presidio defaults (spaCy `en_core_web_sm` + built-in patterns) | 75.0% |
| 2 | Custom recognizers (MRN with context, Luhn-checked NPI, member ID, street, ZIP, phone, city gazetteer) + post-filters | 92.9% |
| 3 | Known values from the structured record | 100.0% |

Code walked through on screen: `src/sentinel/privacy/recognizers.py` and `detect.py`.

```bash
uv run python lessons/M04-L04_detection-with-presidio-patterns-and/final/detect_demo.py
```
