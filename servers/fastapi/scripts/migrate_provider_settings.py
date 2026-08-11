"""Inventory or import legacy provider settings without exposing credentials."""

from __future__ import annotations

import argparse
import asyncio
from uuid import UUID

from modules.providers.application.legacy_migration import migrate_legacy_provider_settings
from services.database import async_session_maker, dispose_engines


async def run(workspace_id: UUID, actor_id: UUID | None, apply: bool) -> None:
    try:
        async with async_session_maker() as session:
            rows = await migrate_legacy_provider_settings(
                session, workspace_id=workspace_id, actor_id=actor_id, apply=apply,
            )
        mode = "APPLY" if apply else "DRY-RUN"
        print(f"{mode}: {len(rows)} provider configuration mapping(s)")
        for row in rows:
            print(f"- {row.adapter_id}: model={row.model}, credential_present={row.has_secret}, status={row.status}")
    finally:
        await dispose_engines()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-id", type=UUID, required=True)
    parser.add_argument("--actor-id", type=UUID)
    parser.add_argument("--apply", action="store_true", help="Apply after reviewing the default dry run")
    args = parser.parse_args()
    asyncio.run(run(args.workspace_id, args.actor_id, args.apply))
