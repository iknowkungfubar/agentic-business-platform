"""Database models and session management for the TurinTech platform.

Supports PostgreSQL for production, SQLite for development.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./turin.db")
_engine = create_engine(DATABASE_URL, pool_pre_ping=True)
_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


class Base(DeclarativeBase):
    pass


# ── Models ─────────────────────────────────────────────────────────


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    users = relationship("User", back_populates="organization")
    agents = relationship("AgentRecord", back_populates="organization")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), default="")
    role = Column(String(50), default="viewer")  # admin, operator, viewer, auditor
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    organization = relationship("Organization", back_populates="users")


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    key_prefix = Column(String(8), nullable=False)  # First 8 chars for identification
    key_hash = Column(String(128), nullable=False)
    name = Column(String(255), default="")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


class AgentRecord(Base):
    __tablename__ = "agent_records"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    url = Column(String(512), nullable=False)
    provider = Column(String(100), default="custom")
    status = Column(String(50), default="unknown")
    tags = Column(Text, default="[]")
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    last_seen = Column(DateTime, default=lambda: datetime.now(UTC))

    organization = relationship("Organization", back_populates="agents")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC))
    agent_id = Column(String(100), nullable=False)
    user_id = Column(String(100), nullable=False)
    action_type = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=False)
    resource_id = Column(String(100), default="")
    input_hash = Column(String(64), default="")
    output_hash = Column(String(64), default="")
    policy_decision = Column(String(50), default="")
    metadata_json = Column(Text, default="{}")
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(512), nullable=False)
    content = Column(Text, nullable=False)
    file_type = Column(String(20), default="")
    file_name = Column(String(255), default="")
    file_size = Column(Integer, default=0)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), default="New conversation")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    messages = relationship("Message", back_populates="conversation", order_by="Message.id")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    model_tier = Column(String(10), default="")
    tokens_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    conversation = relationship("Conversation", back_populates="messages")


# ── Helpers ────────────────────────────────────────────────────────


def get_db():
    """Get a database session."""
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=_engine)


def get_engine():
    return _engine
