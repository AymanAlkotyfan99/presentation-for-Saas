"""Validate the Alembic graph and optionally smoke-test it on fresh PostgreSQL.

The database mode is intentionally destructive only to an empty, disposable
database. CI supplies a dedicated PostgreSQL service database. Local runs can
set MIGRATION_TEST_DATABASE_URL to opt into the same check.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect


ROOT = Path(__file__).resolve().parents[1]


def build_config(database_url: str | None = None) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    if database_url:
        config.set_main_option("sqlalchemy.url", database_url)
    return config


def validate_graph(config: Config) -> tuple[str, str]:
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    bases = script.get_bases()
    if len(heads) != 1:
        raise RuntimeError(f"Expected one Alembic head, found {heads}")
    if len(bases) != 1:
        raise RuntimeError(f"Expected one Alembic base, found {bases}")
    revisions = list(script.walk_revisions())
    revision_ids = {revision.revision for revision in revisions}
    for revision in revisions:
        down_revisions = revision._normalized_down_revisions
        missing = [item for item in down_revisions if item not in revision_ids]
        if missing:
            raise RuntimeError(f"Revision {revision.revision} references missing parents {missing}")
    return bases[0], heads[0]


def schema_snapshot(engine) -> dict[str, tuple[str, ...]]:
    inspector = inspect(engine)
    return {
        table: tuple(sorted(column["name"] for column in inspector.get_columns(table)))
        for table in sorted(inspector.get_table_names())
    }


def smoke_postgresql(database_url: str) -> None:
    if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise RuntimeError("Migration smoke database must use PostgreSQL")
    config = build_config(database_url)
    base, head = validate_graph(config)
    engine = create_engine(database_url)
    try:
        existing = set(inspect(engine).get_table_names())
        if existing:
            raise RuntimeError(
                "Refusing migration smoke test against a non-empty database: "
                + ", ".join(sorted(existing))
            )
        # A base-only database is the reproducible legacy fixture for the
        # linear chain. Upgrade it through every historical revision.
        command.upgrade(config, base)
        command.upgrade(config, head)
        first_snapshot = schema_snapshot(engine)
        with engine.connect() as connection:
            current = MigrationContext.configure(connection).get_current_revision()
        if current != head:
            raise RuntimeError(f"Database revision is {current!r}; expected {head!r}")
        command.upgrade(config, head)
        if schema_snapshot(engine) != first_snapshot:
            raise RuntimeError("Second upgrade-to-head changed the schema")
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.getenv("MIGRATION_TEST_DATABASE_URL"))
    args = parser.parse_args()
    base, head = validate_graph(build_config())
    print(f"Alembic graph valid: base={base} head={head}")
    if args.database_url:
        smoke_postgresql(args.database_url)
        print("PostgreSQL empty/base fixture upgrade and idempotency smoke passed")
    else:
        print("PostgreSQL smoke skipped (set MIGRATION_TEST_DATABASE_URL to enable)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
