"""Prompt template management API — CRUD for LLMOps prompt registry.

Enables ORG_ADMIN users to dynamically tune system prompts without
code deployments. Supports versioned templates with named input
variables for injection at inference time.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.database import get_db
from app.models import PromptTemplate
from app.models.user import UserRole
from app.routers import RequireRole

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/prompts", tags=["prompts"])


class CreatePromptRequest(BaseModel):
    name: str
    template_text: str
    input_variables: list[str] = []


def render_template(template: PromptTemplate, variables: dict[str, str]) -> str:
    """Render a prompt template with the given variables.

    Uses Python string formatting. Variables not in input_variables
    are ignored; missing required variables are left as-is.
    """
    safe_vars = {k: v for k, v in variables.items() if k in json.loads(template.input_variables or "[]")}
    try:
        return template.template_text.format(**safe_vars)
    except KeyError:
        return template.template_text


@router.get("")
async def list_prompts(
    active_only: Annotated[bool, Query(description="Only return active templates")] = False,
    user: dict = Depends(RequireRole(UserRole.ORG_ADMIN, UserRole.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    """List all prompt templates for the organization."""
    query = db.query(PromptTemplate).filter(PromptTemplate.organization_id == user.get("org_id"))
    if active_only:
        query = query.filter(PromptTemplate.is_active.is_(True))
    templates = query.order_by(PromptTemplate.name).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "template_text": t.template_text[:200],
            "input_variables": json.loads(t.input_variables or "[]"),
            "is_active": bool(t.is_active),
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in templates
    ]


@router.post("")
async def create_prompt(
    req: CreatePromptRequest,
    user: Annotated[dict, Depends(RequireRole(UserRole.ORG_ADMIN, UserRole.SUPERADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Create a new prompt template."""
    template = PromptTemplate(
        organization_id=user.get("org_id"),
        name=req.name,
        template_text=req.template_text,
        input_variables=json.dumps(req.input_variables),
        created_by=user.get("user_id"),
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return {
        "id": template.id,
        "name": template.name,
        "input_variables": req.input_variables,
        "is_active": True,
    }


@router.put("/{template_id}")
async def update_prompt(
    template_id: int,
    req: CreatePromptRequest,
    user: Annotated[dict, Depends(RequireRole(UserRole.ORG_ADMIN, UserRole.SUPERADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Update an existing prompt template."""
    template = (
        db.query(PromptTemplate)
        .filter(
            PromptTemplate.id == template_id,
            PromptTemplate.organization_id == user.get("org_id"),
        )
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    template.name = req.name
    template.template_text = req.template_text
    template.input_variables = json.dumps(req.input_variables)
    db.commit()
    return {"status": "updated", "id": template_id}


@router.delete("/{template_id}")
async def delete_prompt(
    template_id: int,
    user: Annotated[dict, Depends(RequireRole(UserRole.ORG_ADMIN, UserRole.SUPERADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    """Delete a prompt template (soft: sets is_active to False)."""
    template = (
        db.query(PromptTemplate)
        .filter(
            PromptTemplate.id == template_id,
            PromptTemplate.organization_id == user.get("org_id"),
        )
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Prompt template not found")
    template.is_active = False
    db.commit()
    return {"status": "deactivated", "id": template_id}
