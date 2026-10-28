"""Data classes: what kind of sensitive data an entity is, and which rules follow it."""
from __future__ import annotations

from typing import Literal

DataClass = Literal["PHI", "PII", "NPI", "CUI", "INTERNAL", "PUBLIC"]

DATA_CLASSES: dict[str, dict[str, str]] = {
    "PHI": {"name": "Protected health information", "rule": "HIPAA Privacy and Security Rules (45 CFR 160, 164)",
            "test": "Individually identifiable health info held by a covered entity or business associate"},
    "PII": {"name": "Personally identifiable information", "rule": "State privacy and breach laws, GDPR (personal data), FERPA for education records",
            "test": "Information that identifies, or can reasonably be linked to, a person"},
    "NPI": {"name": "Nonpublic personal information", "rule": "GLBA Privacy and Safeguards Rules (16 CFR 313, 314)",
            "test": "Personal financial information a financial institution obtains about a consumer"},
    "CUI": {"name": "Controlled unclassified information", "rule": "32 CFR 2002, NIST SP 800-171, DFARS 252.204-7012",
            "test": "Government information that requires safeguarding under law, regulation or policy"},
    "INTERNAL": {"name": "Internal business data", "rule": "Company policy", "test": "Not public, not regulated"},
    "PUBLIC": {"name": "Public", "rule": "None", "test": "Approved for release"},
}

# Detected entity type -> data class, in a healthcare context. The same entity can be a different
# class elsewhere: an account number is NPI at a bank, PHI on a hospital bill.
ENTITY_CLASS: dict[str, DataClass] = {
    "PERSON": "PHI", "DATE_TIME": "PHI", "PHONE_NUMBER": "PHI", "EMAIL_ADDRESS": "PHI", "US_SSN": "PHI",
    "MRN": "PHI", "MEMBER_ID": "PHI", "STREET_ADDRESS": "PHI", "US_ZIP": "PHI", "LOCATION": "PHI",
    "US_BANK_NUMBER": "PHI", "CREDIT_CARD": "PHI", "IP_ADDRESS": "PHI", "URL": "PHI",
    "NPI": "INTERNAL",   # a provider's NPI is public in the NPPES registry, but we still keep it out of logs
}
