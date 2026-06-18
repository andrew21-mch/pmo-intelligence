from fastapi import APIRouter
from pydantic import BaseModel

from app.services.system_status import get_integrations_status

router = APIRouter(prefix="/system", tags=["system"])


class IntegrationStatus(BaseModel):
    id: str
    name: str
    status: str
    message: str
    details: dict


class IntegrationsStatusResponse(BaseModel):
    checked_at: str
    overall: str
    llm_provider: str
    llm_model: str
    integrations: list[IntegrationStatus]


@router.get("/integrations", response_model=IntegrationsStatusResponse)
async def integrations_status() -> IntegrationsStatusResponse:
    result = await get_integrations_status()
    return IntegrationsStatusResponse(**result)
