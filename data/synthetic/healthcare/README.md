# Synthetic healthcare data (Module 4, Lab 2)

| File | Contents |
|---|---|
| `patients.json` | 8 invented patients: name, DOB, address, phone, email, SSN (9xx area, never issued), MRN, member ID, plan |
| `providers.json` | 5 invented ordering providers with Luhn-valid but generated NPIs |
| `prior_auth_requests.json` | PA-2001..PA-2008: service, CPT/HCPCS, ICD-10, and free-text clinical notes that deliberately contain identifiers |
| `phi_annotations.json` | Ground truth: every identifier in each request's notes, with its type. Used to measure detection recall |
| `prior_auth_criteria.md` | The (synthetic) payer's medical-necessity criteria |
| `generate.py` | Regenerates the JSON files deterministically |

Everything is fictional. Never replace it with real patient data, even "just to test".
