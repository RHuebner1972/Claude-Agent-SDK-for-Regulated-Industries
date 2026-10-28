# Synthetic AML dataset (Module 6 and Lab 4)

Bayside Community Bank is fictional. Customers, accounts, transactions and staff are made up. Nothing here is a real person or a real SAR.

| File | Contents |
|---|---|
| `alerts.json` | 10 transaction-monitoring alerts (ALR-5001 to ALR-5010) with customer profile and transactions |
| `staff.json` | The analyst who uses the assistant and the people who approve, with roles |
| `disposition_procedure.md` | AML-SOP-012, the procedure the approval gates enforce |

**Expected dispositions (instructor notes):** 5001 structuring, recommend SAR. 5002 payroll, close (false positive). 5003 rapid movement to crypto, recommend SAR and block outgoing wires. 5004 documented supplier, close (not suspicious). 5005 possible elder exploitation, recommend SAR and block outgoing wires. 5006 consistent cash business, close. 5007 needs information, case note only. 5008 consistent cash business, close; its relationship manager t.nguyen is also an approver and must be blocked by the conflict rule. 5009 tiny P2P payments, close. 5010 travel notice, close.
