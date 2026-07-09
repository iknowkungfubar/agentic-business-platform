"""DriftReport model — EU AI Act post-market monitoring for model bias and hallucination tracking.

Stores daily evaluation results from the independent Judge LLM, including
bias scores, hallucination rates, and deterministic proof for regulatory audits.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.database import Base


class DriftReport(Base):
    __tablename__ = "drift_reports"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, nullable=False, index=True)
    model_name = Column(String(255), default="")
    # Bias score: 0.0 (no bias detected) to 1.0 (systemic bias)
    bias_score = Column(Float, default=0.0)
    # Hallucination rate: 0.0 to 1.0
    hallucination_rate = Column(Float, default=0.0)
    # JSON payload — stores the deterministic proof for regulatory audit
    deterministic_proof_json = Column(Text, default="{}")
    # Sample size used for this evaluation
    sample_size = Column(Integer, default=0)
    # Whether this triggered a critical alert
    triggered_alert = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
