from fastapi import APIRouter

from utils.architecture_flags import provider_registry_enabled, workspaces_enabled


RUNTIME_CAPABILITIES_ROUTER = APIRouter(prefix="/api/v1/runtime", tags=["Runtime"])


@RUNTIME_CAPABILITIES_ROUTER.get("/capabilities")
async def runtime_capabilities() -> dict[str, bool]:
    """Expose authenticated rollout capabilities from the authoritative flags."""
    return {
        "workspaces": workspaces_enabled(),
        "providerRegistry": provider_registry_enabled(),
    }
