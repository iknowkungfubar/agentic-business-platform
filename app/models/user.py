"""User model with RBAC role enum."""

from __future__ import annotations

import enum
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class UserRole(enum.StrEnum):
    """Enterprise RBAC roles — strict hierarchy for B2B compliance.

    SUPERADMIN: Platform-level admin, can manage organizations and all tenants.
    ORG_ADMIN: Organization-level admin, manages users, agents, API keys.
    AUDITOR: Read-only access to audit logs and compliance reports.
    USER: Standard user, can chat and use assigned features.
    """

    SUPERADMIN = "superadmin"
    ORG_ADMIN = "org_admin"
    AUDITOR = "auditor"
    USER = "user"


# Role hierarchy for privilege checks — higher number = more privileges
ROLE_HIERARCHY: dict[UserRole, int] = {
    UserRole.USER: 0,
    UserRole.AUDITOR: 10,
    UserRole.ORG_ADMIN: 50,
    UserRole.SUPERADMIN: 100,
}


def role_at_least(required: UserRole, actual: str | UserRole) -> bool:
    """Check if a role meets the minimum required level."""
    if isinstance(actual, str):
        try:
            actual_enum = UserRole(actual)
        except ValueError:
            return False
    else:
        actual_enum = actual
    return ROLE_HIERARCHY.get(actual_enum, -1) >= ROLE_HIERARCHY.get(required, 0)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), default="")
    role = Column(String(50), default=UserRole.USER.value, nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    organization = relationship("Organization", back_populates="users")
