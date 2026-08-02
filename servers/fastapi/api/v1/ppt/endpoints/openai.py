from typing import Annotated, List
from fastapi import APIRouter, Body, Depends, HTTPException

from api.v1.security_dependencies import require_provider_endpoint_admin
from utils.available_models import (
    ModelAvailabilityError,
    list_available_openai_compatible_models,
)
from utils.outbound_http import OutboundSecurityError, public_outbound_error

OPENAI_ROUTER = APIRouter(prefix="/openai", tags=["OpenAI"])


@OPENAI_ROUTER.post("/models/available", response_model=List[str])
async def get_available_models(
    url: Annotated[str, Body()],
    api_key: Annotated[str, Body()],
    _: None = Depends(require_provider_endpoint_admin),
):
    try:
        return await list_available_openai_compatible_models(url, api_key)
    except ModelAvailabilityError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except OutboundSecurityError as e:
        raise HTTPException(status_code=400, detail=public_outbound_error(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "MODEL_DISCOVERY_FAILED", "message": "Model discovery failed"},
        ) from e
