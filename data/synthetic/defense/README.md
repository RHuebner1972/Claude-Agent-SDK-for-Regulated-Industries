# Synthetic defense-manufacturing dataset (Module 7 and Lab 5)

Northgate Precision Components and the FALCON and HARBORLIGHT programs are fictional. The "technical details" are invented and
are NOT real CUI or ITAR technical data; they are marked as if they were so the boundary controls have something to protect.

| File | Contents |
|---|---|
| `ecrs.json` | 6 engineering change requests (ECRs): 4 FALCON (marked CUI, ITAR), 2 HARBORLIGHT (commercial) |
| `programs.json` | The two programs and where their data may live |
| `change_procedure.md` | ENG-SOP-021, the rules the boundary controls enforce |

Every FALCON ECR's notes carry a canary string (`CANARY-CUI-...`). Leak tests search every log and every orchestrator
context for canaries, CUI banner markings, drawing numbers and tolerance values.
