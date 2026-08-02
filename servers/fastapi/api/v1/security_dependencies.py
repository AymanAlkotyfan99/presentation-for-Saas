"""Route-local security dependencies shared by provider configuration surfaces."""

from fastapi import HTTPException, Request

from utils.get_env import is_disable_auth_enabled


async def require_provider_endpoint_admin(request: Request) -> None:
    """Arbitrary provider endpoints are administrator-controlled in SaaS mode."""
    if is_disable_auth_enabled():
        return
    principal = getattr(request.state, "auth_principal", None)
    if principal is None or not bool(getattr(principal, "is_admin", False)):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "PROVIDER_ENDPOINT_ADMIN_REQUIRED",
                "message": "Administrator access is required to probe provider endpoints",
            },
        )
