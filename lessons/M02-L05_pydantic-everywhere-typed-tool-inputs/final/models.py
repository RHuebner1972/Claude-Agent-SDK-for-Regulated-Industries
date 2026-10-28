"""
M02-L05: Pydantic domain models. Types and business rules, enforced in code.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ENTRY_ID = r"^JE-\d{4}$"
ACCOUNT = r"^\d{4}$"


class EntryLookup(BaseModel):
    """Input to the get_journal_entry tool."""
    model_config = ConfigDict(extra="forbid")
    entry_id: str = Field(pattern=ENTRY_ID, description="Journal entry ID, e.g. JE-1003")


class JournalLine(BaseModel):
    account: str = Field(pattern=ACCOUNT)
    debit: Decimal = Field(ge=0)
    credit: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def one_side_only(self) -> "JournalLine":
        if (self.debit > 0) == (self.credit > 0):
            raise ValueError("each line must have exactly one of debit or credit")
        return self


class JournalEntry(BaseModel):
    entry_id: str = Field(pattern=ENTRY_ID)
    date: str
    preparer: str
    description: str
    vendor_id: str | None = None
    lines: list[JournalLine] = Field(min_length=2)
    amount: Decimal = Field(gt=0)
    currency: Literal["USD"]
    status: Literal["pending_review", "approved", "rejected", "escalated"]

    @model_validator(mode="after")
    def balanced(self) -> "JournalEntry":
        debits = sum(line.debit for line in self.lines)
        credits = sum(line.credit for line in self.lines)
        if debits != credits:
            raise ValueError(f"entry is unbalanced: debits {debits} != credits {credits}")
        return self


class ReviewDecision(BaseModel):
    """What the reviewer agent must return. Used as a structured-output schema in L06."""
    model_config = ConfigDict(extra="forbid")
    entry_id: str = Field(pattern=ENTRY_ID)
    decision: Literal["approve", "reject", "escalate"]
    required_approver: Literal["none", "controller", "cfo"]
    policy_rules_applied: list[int] = Field(min_length=1, description="Numbers of the policy rules relied on")
    reasons: list[str] = Field(min_length=1, max_length=5)

    @field_validator("reasons")
    @classmethod
    def no_empty_reasons(cls, v: list[str]) -> list[str]:
        if any(not r.strip() for r in v):
            raise ValueError("reasons must not be blank")
        return v
