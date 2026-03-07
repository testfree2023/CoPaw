# -*- coding: utf-8 -*-
"""Persona API Router for CoPaw."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from enum import Enum

from ...agents.persona import PersonaManager, PersonaScope, PersonaSpec

router = APIRouter(prefix="/personas", tags=["personas"])

# Global persona manager instance
_persona_manager: Optional[PersonaManager] = None


def set_persona_manager(manager: PersonaManager):
    """Set the persona manager instance."""
    global _persona_manager
    _persona_manager = manager


def get_persona_manager() -> PersonaManager:
    """Get the persona manager instance."""
    if _persona_manager is None:
        raise HTTPException(status_code=500, detail="Persona manager not initialized")
    return _persona_manager


class PersonaScopeEnum(str, Enum):
    """Persona scope enum for API."""
    GLOBAL = "global"
    CHANNEL = "channel"
    USER = "user"
    USER_CHANNEL = "user_channel"


class PersonaCreate(BaseModel):
    """Persona creation model."""
    name: str
    description: Optional[str] = None
    system_prompt_addon: str
    scope: PersonaScopeEnum = PersonaScopeEnum.GLOBAL
    channel: Optional[str] = None
    user_ids: Optional[str] = None  # Space-separated user IDs


class PersonaUpdate(BaseModel):
    """Persona update model."""
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt_addon: Optional[str] = None
    enabled: Optional[bool] = None
    scope: Optional[str] = None
    channel: Optional[str] = None
    user_ids: Optional[str] = None


@router.get("")
async def list_personas():
    """List all personas."""
    manager = get_persona_manager()
    personas = await manager.list_personas()
    return {"personas": [p.model_dump() for p in personas]}


@router.post("")
async def create_persona(persona: PersonaCreate):
    """Create a new persona."""
    manager = get_persona_manager()
    new_persona = await manager.create_persona(
        name=persona.name,
        description=persona.description,
        system_prompt_addon=persona.system_prompt_addon,
        scope=PersonaScope(persona.scope.value),
        channel=persona.channel,
        user_ids=persona.user_ids,
    )
    return {"persona": new_persona.model_dump()}


@router.get("/{persona_id}")
async def get_persona(persona_id: str):
    """Get a specific persona."""
    manager = get_persona_manager()
    persona = await manager.get_persona(persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    return {"persona": persona.model_dump()}


@router.put("/{persona_id}")
async def update_persona(persona_id: str, persona: PersonaUpdate):
    """Update a persona."""
    manager = get_persona_manager()
    updates = persona.model_dump(exclude_unset=True)
    updated_persona = await manager.update_persona(persona_id, **updates)
    if updated_persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    return {"persona": updated_persona.model_dump()}


@router.delete("/{persona_id}")
async def delete_persona(persona_id: str):
    """Delete a persona."""
    manager = get_persona_manager()
    success = await manager.remove_persona(persona_id)
    if not success:
        raise HTTPException(status_code=404, detail="Persona not found")
    return {"success": True}


@router.post("/{persona_id}/toggle")
async def toggle_persona(persona_id: str):
    """Toggle persona enabled status."""
    manager = get_persona_manager()
    persona = await manager.get_persona(persona_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Persona not found")
    updated_persona = await manager.update_persona(persona_id, enabled=not persona.enabled)
    return {"persona": updated_persona.model_dump()}