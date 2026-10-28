"""
Regenerate the synthetic healthcare data used in Module 4 and Lab 2 (deterministic: no randomness).

    uv run python data/synthetic/healthcare/generate.py

Every person, number and address here is invented. SSNs use the 9xx area (never issued by the SSA),
phone numbers use the 555-01xx fictional range, emails use example.com/example.org, and NPIs are
Luhn-valid but generated. Do not replace any of it with real data.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def npi_check_digit(first9: str) -> str:
    """NPI = 9 digits + Luhn check digit computed over '80840' + the 9 digits (CMS rule)."""
    digits = [int(d) for d in "80840" + first9]
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 0:
            d *= 2
            d = d - 9 if d > 9 else d
        total += d
    return str((10 - total % 10) % 10)


def npi(first9: str) -> str:
    return first9 + npi_check_digit(first9)


PATIENTS = [
    # id, first, last, dob, sex, street, city, zip, phone, email, ssn, mrn, member, plan
    ("P-001", "Maria", "Delgado", "1961-03-14", "F", "42 Harbor St", "Quincy", "02169", "617-555-0143", "maria.delgado@example.com", "912-45-6789", "4829173", "NEH482913057", "Commercial PPO"),
    ("P-002", "James", "Okafor", "1958-11-02", "M", "19 Linden Ave", "Braintree", "02184", "781-555-0177", "j.okafor@example.org", "934-12-0071", "5537204", "NEH553720481", "Medicare Advantage"),
    ("P-003", "Priya", "Raman", "1987-06-25", "F", "7 Ocean View Rd", "Hull", "02045", "781-555-0119", "priya.raman@example.com", "901-88-2345", "6110458", "NEH611045822", "Commercial HMO"),
    ("P-004", "Robert", "Kowalski", "1949-01-30", "M", "233 Washington St", "Weymouth", "02188", "781-555-0102", "rkowalski49@example.net", "923-50-1188", "3305921", "NEH330592166", "Medicare Advantage"),
    ("P-005", "Aisha", "Bennett", "1995-09-09", "F", "88 Granite Ave", "Milton", "02186", "617-555-0168", "aisha.b@example.com", "915-27-4402", "7728830", "NEH772883019", "Medicaid Managed Care"),
    ("P-006", "Thomas", "Nguyen", "1972-04-17", "M", "5 Pleasant St", "Cohasset", "02025", "781-555-0134", "tnguyen@example.org", "947-63-0950", "2219647", "NEH221964730", "Commercial PPO"),
    ("P-007", "Elena", "Petrova", "1966-12-21", "F", "310 Hancock St", "Quincy", "02171", "617-555-0191", "elena.petrova@example.com", "908-14-7733", "8841206", "NEH884120695", "Commercial PPO"),
    ("P-008", "Marcus", "Hill", "2001-08-03", "M", "61 Summer St", "Hingham", "02043", "781-555-0125", "marcus.hill01@example.com", "926-39-5104", "9013375", "NEH901337542", "Commercial HMO"),
]

PROVIDERS = [
    ("PR-01", "Alan", "Brooks", "Orthopedics", "124531959"),
    ("PR-02", "Grace", "Lin", "Endocrinology", "167293802"),
    ("PR-03", "Samuel", "Adeyemi", "Rheumatology", "193857261"),
    ("PR-04", "Hannah", "Weiss", "Neurology", "142086537"),
    ("PR-05", "Diego", "Morales", "Cardiology", "158720493"),
]

# (request id, patient, provider, CPT/HCPCS, description, ICD-10, diagnosis, notes template)
REQUESTS = [
    ("PA-2001", "P-001", "PR-01", "72148", "MRI lumbar spine without contrast", "M54.16", "Lumbar radiculopathy",
     "{name} (DOB {dob_us}, MRN {mrn}) reports 9 weeks of low back pain radiating to the left leg despite 6 weeks of "
     "physical therapy and NSAIDs. Positive straight-leg raise. Requesting MRI to evaluate for disc herniation. "
     "Contact patient at {phone}."),
    ("PA-2002", "P-002", "PR-02", "E2103", "Continuous glucose monitor", "E11.65", "Type 2 diabetes with hyperglycemia",
     "Mr. {last} is on basal-bolus insulin (4 injections/day) with A1c 9.2%. Two documented hypoglycemic episodes last "
     "month. Member ID {member}. Ordering provider Dr. {prov_name}, NPI {npi}."),
    ("PA-2003", "P-003", "PR-03", "J0135", "Adalimumab injection", "M05.79", "Rheumatoid arthritis, multiple sites",
     "{first} {last} has active RA (DAS28 5.1) after 3 months of methotrexate 20 mg weekly. TB screening negative. "
     "Patient email {email} for portal updates. Medical record # {mrn}."),
    ("PA-2004", "P-004", "PR-04", "70553", "MRI brain with and without contrast", "R51.9", "Headache, unspecified",
     "New-onset headaches for 3 weeks in a 77-year-old with no prior history. Neurological exam shows mild left "
     "pronator drift. Patient lives at {street}, {city} MA {zip}. SSN on file {ssn}."),
    ("PA-2005", "P-005", "PR-05", "93306", "Transthoracic echocardiogram", "R01.1", "Cardiac murmur",
     "Grade 2/6 systolic murmur found at an annual physical. No prior echo. Ms. {last} (MRN {mrn}) is "
     "asymptomatic; requesting baseline echo. Call back {phone}."),
    ("PA-2006", "P-006", "PR-01", "29881", "Knee arthroscopy with meniscectomy", "S83.241A", "Medial meniscus tear, right knee",
     "Right knee locking and effusion for 4 months after a fall on {injury_date}. MRI confirms a bucket-handle tear. "
     "Failed 8 weeks of PT. Subscriber ID {member}."),
    ("PA-2007", "P-007", "PR-02", "J1950", "Leuprolide injection", "E28.2", "Polycystic ovarian syndrome",
     "{name}, born {dob_long}, referred for hormonal therapy after failed oral contraceptive trial. Reach her at "
     "{email} or {phone}."),
    ("PA-2008", "P-008", "PR-04", "95810", "Polysomnography, attended", "G47.33", "Obstructive sleep apnea",
     "Epworth Sleepiness Score 15, loud snoring, witnessed apneas. BMI 34. {first} {last} works night shifts; "
     "MRN: {mrn}. Requesting in-lab study."),
]

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def main() -> None:
    patients = [
        {"patient_id": p[0], "first_name": p[1], "last_name": p[2], "dob": p[3], "sex": p[4],
         "address": {"street": p[5], "city": p[6], "state": "MA", "zip": p[7]},
         "phone": p[8], "email": p[9], "ssn": p[10], "mrn": p[11], "member_id": p[12], "plan": p[13]}
        for p in PATIENTS
    ]
    providers = [{"provider_id": p[0], "first_name": p[1], "last_name": p[2], "specialty": p[3], "npi": npi(p[4])}
                 for p in PROVIDERS]
    by_p = {p["patient_id"]: p for p in patients}
    by_pr = {p["provider_id"]: p for p in providers}
    requests, annotations = [], {}
    for rid, pid, prid, code, desc, icd, dx, template in REQUESTS:
        p, pr = by_p[pid], by_pr[prid]
        y, m, d = p["dob"].split("-")
        values = {
            "name": f"{p['first_name']} {p['last_name']}", "first": p["first_name"], "last": p["last_name"],
            "dob_us": f"{m}/{d}/{y}", "dob_long": f"{MONTHS[int(m) - 1]} {int(d)}, {y}", "mrn": p["mrn"],
            "member": p["member_id"], "phone": p["phone"], "email": p["email"], "ssn": p["ssn"],
            "street": p["address"]["street"], "city": p["address"]["city"], "zip": p["address"]["zip"],
            "prov_name": f"{pr['first_name']} {pr['last_name']}", "npi": pr["npi"], "injury_date": "06/02/2026",
        }
        notes = template.format(**values)
        requests.append({"request_id": rid, "patient_id": pid, "provider_id": prid, "service_code": code,
                         "service": desc, "icd10": icd, "diagnosis": dx, "submitted": "2026-10-05",
                         "status": "pending_review", "clinical_notes": notes})
        # Ground truth for recall: every identifier that appears in the notes, with its type.
        kinds = {"name": "PERSON", "first": "PERSON", "last": "PERSON", "prov_name": "PERSON", "dob_us": "DATE_TIME",
                 "dob_long": "DATE_TIME", "injury_date": "DATE_TIME", "mrn": "MRN", "member": "MEMBER_ID",
                 "phone": "PHONE_NUMBER", "email": "EMAIL_ADDRESS", "ssn": "US_SSN", "street": "STREET_ADDRESS",
                 "zip": "US_ZIP", "city": "LOCATION", "npi": "NPI"}
        spans = []
        for key, kind in kinds.items():
            if "{" + key + "}" in template:
                spans.append({"type": kind, "value": values[key]})
        annotations[rid] = spans
    (HERE / "patients.json").write_text(json.dumps(patients, indent=2) + "\n", encoding="utf-8")
    (HERE / "providers.json").write_text(json.dumps(providers, indent=2) + "\n", encoding="utf-8")
    (HERE / "prior_auth_requests.json").write_text(json.dumps(requests, indent=2) + "\n", encoding="utf-8")
    (HERE / "phi_annotations.json").write_text(json.dumps(annotations, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(patients)} patients, {len(providers)} providers, {len(requests)} requests")


if __name__ == "__main__":
    main()
