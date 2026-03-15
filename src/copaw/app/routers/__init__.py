# -*- coding: utf-8 -*-
from fastapi import APIRouter

from .agent import router as agent_router
from .config import router as config_router
from .local_models import router as local_models_router
from .providers import router as providers_router
from .skills import router as skills_router
from .workspace import router as workspace_router
from .envs import router as envs_router
from .ollama_models import router as ollama_models_router
from .mcp import router as mcp_router
from .rules import router as rules_router
from .personas import router as personas_router
from .agent_instances import router as agent_instances_router
from .tasks import router as tasks_router
from .security import router as security_router
from ..crons.api import router as cron_router
from ..runner.api import router as runner_router
from .console import router as console_router


router = APIRouter()

router.include_router(agent_router)
router.include_router(config_router)
router.include_router(console_router)
router.include_router(cron_router)
router.include_router(local_models_router)
router.include_router(mcp_router)
router.include_router(ollama_models_router)
router.include_router(personas_router)
router.include_router(providers_router)
router.include_router(rules_router)
router.include_router(runner_router)
router.include_router(skills_router)
router.include_router(workspace_router)
router.include_router(envs_router)
router.include_router(agent_instances_router)
router.include_router(tasks_router)
router.include_router(security_router)

__all__ = ["router"]
