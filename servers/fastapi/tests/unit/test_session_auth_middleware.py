from api.middlewares import SessionAuthMiddleware


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
