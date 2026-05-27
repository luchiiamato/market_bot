from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class InvestorProfile:
    user_id: int
    username: str
    display_name: str
    local_currency: str
    investor_profile: str
    preferred_horizon: str
    preferred_instrument_types: str
    risk_tolerance: str
    benchmark_preference: str
    created_at: datetime
    updated_at: datetime


@dataclass
class AuthenticatedUser:
    user_id: int
    username: str


@dataclass
class UserSession:
    access_token: str
    expires_at: datetime
    profile: InvestorProfile
