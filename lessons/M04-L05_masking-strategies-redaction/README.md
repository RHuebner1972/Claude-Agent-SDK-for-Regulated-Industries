# M04-L05: Masking strategies: redaction, tokenization, pseudonymization and reversible vaults

Module: M04 Pillar 2, Data Protection · Type: Code-along

`final/masking_demo.py` masks one note five ways (redact, partial, pseudonym, generalize, token), then shows
the token vault: values encrypted at rest, re-identification granted to a care manager for treatment and
denied to an analyst, with every attempt in a hash-chained audit log.

```bash
uv run python lessons/M04-L05_masking-strategies-redaction/final/masking_demo.py
```
Code walked through on screen: `src/sentinel/privacy/mask.py` and `vault.py`.
