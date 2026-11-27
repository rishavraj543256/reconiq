from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models import TxKind


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=2, max_length=160)
    organization_name: str = Field(min_length=2, max_length=160)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TransactionIn(BaseModel):
    kind: TxKind
    external_id: str = Field(min_length=1, max_length=120)
    reference: str = Field(default="", max_length=255)
    vendor: str = Field(default="", max_length=255)
    amount: Decimal
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    transaction_date: date


class TransactionOut(TransactionIn):
    id: str
    is_quarantined: bool
    model_config = ConfigDict(from_attributes=True)


class RuleIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    amount_tolerance: Decimal = Field(default=Decimal("0.00"), ge=0)
    date_tolerance_days: int = Field(default=3, ge=0, le=90)
    fuzzy_threshold: int = Field(default=85, ge=0, le=100)
    auto_approve_threshold: int = Field(default=95, ge=0, le=100)


class Dashboard(BaseModel):
    total_transactions: int
    matched_transactions: int
    match_percentage: float
    unmatched_transactions: int
    discrepancy_amount: Decimal
    anomalies: int
    pending_approvals: int
    recent_runs: list[dict]
