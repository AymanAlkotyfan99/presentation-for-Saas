from api.middlewares import SessionAuthMiddleware
from modules.workspaces.domain.models import Permission


def test_all_app_data_asset_prefixes_require_auth():
    middleware = SessionAuthMiddleware(app=None)

    assert middleware._requires_auth("/app_data/images/photo.png") is True
    assert middleware._requires_auth("/app_data/fonts/embedded/font.ttf") is True
    assert (
        middleware._requires_auth("/app_data/pptx-to-html/session/fonts/font.ttf")
        is True
    )
    assert (
        middleware._requires_auth("/app_data/templates/default/thumbnail.png")
        is True
    )
    assert (
        middleware._requires_auth("/app_data/pptx-to-html/session/images/image.png")
        is True
    )


def test_other_app_data_prefixes_still_require_auth():
    middleware = SessionAuthMiddleware(app=None)

    assert middleware._requires_auth("/app_data/uploads/source.pptx") is True
    assert middleware._requires_auth("/app_data/exports/deck.pdf") is True


def test_retired_public_setup_path_requires_auth_middleware():
    middleware = SessionAuthMiddleware(app=None)

    assert middleware._requires_auth("/api/v1/auth/setup") is True
    assert "/api/v1/auth/setup" not in middleware._PUBLIC_AUTH_PATHS


def test_workspace_permissions_are_centralized_by_resource_and_method():
    required = SessionAuthMiddleware._required_workspace_permission
    assert required("/api/v1/ppt/presentation/deck", "GET") == Permission.PRESENTATIONS_READ
    assert required("/api/v1/ppt/presentation/deck", "PATCH") == Permission.PRESENTATIONS_WRITE
    assert required("/api/v1/ppt/images/asset", "GET") == Permission.ASSETS_READ
    assert required("/api/v1/ppt/images/generate", "GET") == Permission.ASSETS_WRITE
    assert required("/api/v1/ppt/template/item", "DELETE") == Permission.TEMPLATES_WRITE
    assert required("/api/v1/async-tasks/status/task", "GET") == Permission.JOBS_READ
    assert required("/api/v1/jobs", "GET") == Permission.JOBS_READ
    assert required("/api/v1/jobs/id/cancel", "POST") == Permission.JOBS_WRITE
    assert required("/api/v1/assets", "GET") == Permission.ASSETS_READ
    assert required("/api/v1/assets/id", "DELETE") == Permission.ASSETS_WRITE
    assert (
        required("/api/v1/assets/id/download-capability", "POST")
        == Permission.ASSETS_READ
    )
    assert required("/app_data/images/workspaces/id/file.png", "GET") == Permission.ASSETS_READ
    assert required("/api/v1/workspaces/current", "GET") is None
