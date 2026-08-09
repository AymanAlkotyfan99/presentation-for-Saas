import asyncio
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.responses import JSONResponse

from api.middlewares import SessionAuthMiddleware
from api.operation_security import reset_operation_control_backend
from api.v1.ppt.endpoints.presentation_document import PRESENTATION_DOCUMENT_ROUTER
from models.sql.image_asset import ImageAsset
from models.sql.presentation import PresentationModel, PresentationVersion
from models.sql.presentation_document import PresentationDocumentModel
from models.sql.slide import SlideModel
from services.database import get_async_session
from utils.api_errors import StableAPIError


def _client(tmp_path, presentation_id):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'canonical-api.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def prepare():
        async with engine.begin() as connection:
            await connection.run_sync(PresentationModel.__table__.create)
            await connection.run_sync(SlideModel.__table__.create)
            await connection.run_sync(ImageAsset.__table__.create)
            await connection.run_sync(PresentationDocumentModel.__table__.create)
        async with sessions() as session:
            session.add(PresentationModel(
                id=presentation_id,
                owner_id=None,
                version=PresentationVersion.V2_STANDARD,
                content="Canonical API test",
                n_slides=1,
                language="en",
                title="Canonical API test",
            ))
            session.add(SlideModel(
                id=uuid4(),
                owner_id=None,
                presentation=presentation_id,
                layout_group="basic",
                layout="title",
                index=0,
                content={"title": "Safe structured content"},
                ui=None,
            ))
            await session.commit()

    asyncio.run(prepare())

    async def override_session():
        async with sessions() as session:
            yield session

    app = FastAPI()
    app.include_router(PRESENTATION_DOCUMENT_ROUTER, prefix="/api/v1/ppt")
    app.dependency_overrides[get_async_session] = override_session

    @app.exception_handler(StableAPIError)
    async def stable_error(_request: Request, exc: StableAPIError):
        return JSONResponse(status_code=exc.status_code, content=exc.response_body(), headers=exc.headers)

    return TestClient(app), engine, sessions


def test_canonical_api_preview_flags_revision_and_asset_ownership(monkeypatch, tmp_path):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("SECURITY_CONTROL_BACKEND", "memory")
    presentation_id = uuid4()
    monkeypatch.setenv("CANONICAL_INTERNAL_COHORT", f"presentation:{presentation_id}")
    monkeypatch.setenv("CANONICAL_DOCUMENT_READS_ENABLED", "false")
    monkeypatch.setenv("CANONICAL_DOCUMENT_WRITES_ENABLED", "false")
    client, engine, sessions = _client(tmp_path, presentation_id)

    preview = client.post(f"/api/v1/ppt/presentations/{presentation_id}/document/migration-preview")
    assert preview.status_code == 200
    assert preview.json()["schemaVersion"] == "1.0.0"

    async def row_count():
        async with sessions() as session:
            return await session.get(PresentationDocumentModel, presentation_id)

    assert asyncio.run(row_count()) is None
    disabled = client.get(f"/api/v1/ppt/presentations/{presentation_id}/document")
    assert disabled.status_code == 404
    assert disabled.json()["code"] == "CANONICAL_READ_DISABLED"

    monkeypatch.setenv("CANONICAL_DOCUMENT_READS_ENABLED", "true")
    fallback = client.get(f"/api/v1/ppt/presentations/{presentation_id}/document")
    assert fallback.status_code == 200
    assert fallback.json()["source"] == "legacy-fallback"
    assert fallback.json()["revision"] == 0

    monkeypatch.setenv("CANONICAL_DOCUMENT_WRITES_ENABLED", "true")
    converted = client.post(f"/api/v1/ppt/presentations/{presentation_id}/document/convert")
    assert converted.status_code == 200
    assert converted.json()["revision"] == 1
    assert converted.headers["etag"] == '"1"'

    payload = converted.json()["document"]
    payload["title"] = "Revision two"
    updated = client.put(
        f"/api/v1/ppt/presentations/{presentation_id}/document",
        headers={"If-Match": '"1"'},
        json=payload,
    )
    assert updated.status_code == 200
    assert updated.json()["revision"] == 2

    stale = client.put(
        f"/api/v1/ppt/presentations/{presentation_id}/document",
        headers={"If-Match": '"1"'},
        json=payload,
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "CANONICAL_REVISION_CONFLICT"
    assert stale.json()["params"]["currentRevision"] == 2

    invalid = dict(payload)
    invalid["title"] = "<script>unsafe</script>"
    rejected = client.put(
        f"/api/v1/ppt/presentations/{presentation_id}/document",
        headers={"If-Match": '"2"'},
        json=invalid,
    )
    assert rejected.status_code == 422
    persisted = client.get(f"/api/v1/ppt/presentations/{presentation_id}/document")
    assert persisted.json()["revision"] == 2
    assert persisted.json()["document"]["title"] == "Revision two"

    foreign_asset_id = uuid4()
    async def add_foreign_asset():
        async with sessions() as session:
            session.add(ImageAsset(id=foreign_asset_id, owner_id=uuid4(), is_uploaded=True, path="C:/private/foreign.png"))
            await session.commit()
    asyncio.run(add_foreign_asset())
    asset_payload = persisted.json()["document"]
    asset_payload["assets"] = [{
        "assetId": str(foreign_asset_id), "kind": "image", "mimeType": "image/png",
        "sourceType": "uploaded", "role": "content",
    }]
    denied = client.put(
        f"/api/v1/ppt/presentations/{presentation_id}/document",
        headers={"If-Match": '"2"'},
        json=asset_payload,
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "CANONICAL_ASSET_ACCESS_DENIED"

    client.close()
    asyncio.run(reset_operation_control_backend())
    asyncio.run(engine.dispose())


def test_canonical_routes_are_session_protected():
    middleware = object.__new__(SessionAuthMiddleware)
    assert middleware._requires_auth("/api/v1/ppt/presentations/00000000-0000-4000-8000-000000000001/document") is True
