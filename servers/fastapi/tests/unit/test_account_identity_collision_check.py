from __future__ import annotations

import json
import os
from uuid import UUID
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def _create_shadow_fixture(database_url: str, *, ambiguous: bool) -> None:
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE "user" (
                        id CHAR(32) PRIMARY KEY,
                        username VARCHAR(128),
                        email_original VARCHAR(320),
                        email_normalized VARCHAR(320)
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE account_pending_registrations (
                        id CHAR(32) PRIMARY KEY,
                        email_original VARCHAR(320),
                        email_normalized VARCHAR(320)
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE invitations (
                        id CHAR(32) PRIMARY KEY,
                        invited_identity VARCHAR(320) NOT NULL,
                        normalized_identity VARCHAR(320),
                        identity_kind VARCHAR(16)
                    )
                    """
                )
            )
            if ambiguous:
                connection.execute(
                    text(
                        """
                        INSERT INTO "user"
                            (id, username, email_original, email_normalized)
                        VALUES
                            ('000000000000400080000000000011', 'Straße', NULL, NULL),
                            ('000000000000400080000000000012', 'STRASSE', NULL, NULL),
                            ('000000000000400080000000000013', 'Owner@EXAMPLE.COM', NULL, NULL)
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO account_pending_registrations
                            (id, email_original, email_normalized)
                        VALUES
                            ('000000000000400080000000000021', 'owner@example.com', NULL),
                            ('000000000000400080000000000022', 'person@bücher.example', NULL),
                            ('000000000000400080000000000023', 'PERSON@xn--bcher-kva.example', NULL)
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO invitations
                            (id, invited_identity, normalized_identity, identity_kind)
                        VALUES
                            ('000000000000400080000000000031', 'Owner@example.com', NULL, 'EMAIL')
                        """
                    )
                )
            else:
                connection.execute(
                    text(
                        """
                        INSERT INTO "user"
                            (id, username, email_original, email_normalized)
                        VALUES
                            ('000000000000400080000000000041', 'alpha', NULL, NULL),
                            ('000000000000400080000000000042', 'beta', NULL, NULL)
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO account_pending_registrations
                            (id, email_original, email_normalized)
                        VALUES
                            ('000000000000400080000000000043', 'owner@example.com', NULL)
                        """
                    )
                )
    finally:
        engine.dispose()


def _row_snapshot(database_url: str) -> dict[str, list[tuple]]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            return {
                table: list(
                    connection.execute(text(f'SELECT * FROM "{table}" ORDER BY id'))
                )
                for table in (
                    "user",
                    "account_pending_registrations",
                    "invitations",
                )
            }
    finally:
        engine.dispose()


def test_collision_preflight_reports_only_safe_ids_counts_and_categories(
    tmp_path, capsys
) -> None:
    from scripts.check_account_identity_collisions import main

    database_url = f"sqlite:///{(tmp_path / 'ambiguous.db').as_posix()}"
    _create_shadow_fixture(database_url, ambiguous=True)
    before = _row_snapshot(database_url)

    assert main(["--database-url", database_url, "--format", "json"]) == 2
    first_output = capsys.readouterr().out
    assert main(["--database-url", database_url, "--format", "json"]) == 2
    second_output = capsys.readouterr().out

    assert first_output == second_output
    report = json.loads(first_output)
    assert report["status"] == "ambiguous"
    assert report["total_collisions"] == 3
    assert {item["category"] for item in report["categories"]} == {
        "EMAIL_EMAIL",
        "EMAIL_USERNAME_ALIAS",
        "USERNAME_USERNAME",
    }
    assert all(item["count"] >= 2 for item in report["categories"])
    assert all(
        UUID(subject_id).version is not None
        for item in report["categories"]
        for subject_id in item["subject_ids"]
    )
    lowered = first_output.casefold()
    for secret_identity in (
        "straße",
        "strasse",
        "owner@example.com",
        "bücher.example",
        "xn--bcher-kva.example",
    ):
        assert secret_identity.casefold() not in lowered
    assert _row_snapshot(database_url) == before


def test_collision_preflight_clean_database_is_read_only(tmp_path, capsys) -> None:
    from scripts.check_account_identity_collisions import main

    database_url = f"sqlite:///{(tmp_path / 'clean.db').as_posix()}"
    _create_shadow_fixture(database_url, ambiguous=False)
    before = _row_snapshot(database_url)

    assert main(["--database-url", database_url, "--format", "json"]) == 0

    assert json.loads(capsys.readouterr().out) == {
        "categories": [],
        "status": "clean",
        "total_collisions": 0,
    }
    assert _row_snapshot(database_url) == before


def test_collision_preflight_failure_does_not_echo_connection_or_identity_data(
    capsys,
) -> None:
    from scripts.check_account_identity_collisions import main

    unsafe_url = "not-a-driver://example.invalid/data?identity=private-marker"
    assert main(["--database-url", unsafe_url, "--format", "json"]) == 3

    output = capsys.readouterr().out
    assert json.loads(output)["status"] == "error"
    assert "private-marker" not in output
    assert "example.invalid" not in output


def test_collision_preflight_runs_read_only_on_disposable_postgresql() -> None:
    from scripts.check_account_identity_collisions import build_report

    database_url = os.getenv("MIGRATION_TEST_DATABASE_URL", "")
    if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        pytest.skip(
            "MIGRATION_TEST_DATABASE_URL does not identify disposable PostgreSQL"
        )
    schema = f"account_collision_{uuid4().hex}"
    schema_url = make_url(database_url).update_query_dict(
        {"options": f"-csearch_path={schema}"}
    ).render_as_string(hide_password=False)
    admin_engine = create_engine(database_url)
    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        _create_shadow_fixture(schema_url, ambiguous=True)
        before = _row_snapshot(schema_url)

        report = build_report(schema_url)

        assert report["status"] == "ambiguous"
        assert report["total_collisions"] == 3
        assert _row_snapshot(schema_url) == before
    finally:
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin_engine.dispose()
