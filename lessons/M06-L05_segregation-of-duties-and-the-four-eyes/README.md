# M06-L05: Segregation of duties and the four-eyes principle

Module: M06 Pillar 5, Human Oversight: Approval Workflows · Type: Code-along

`final/sod_demo.py` submits one SAR recommendation that needs two approvals, one from the BSA Officer, then tries
eight signers: the requester, the agent, a relationship manager, a senior analyst who manages the customer, the
same approver twice, and two valid approvers. Each refusal prints the SoD rule it broke.

```bash
uv run python lessons/M06-L05_segregation-of-duties-and-the-four-eyes/final/sod_demo.py
```
Code walked through on screen: `src/sentinel/approvals/sod.py`.

> All data in this repo is synthetic. Never use real PHI, PII, CUI or customer data with course code.
