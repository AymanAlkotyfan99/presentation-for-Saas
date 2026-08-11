"""Inventory or migrate authorized legacy ImageAsset paths.

Default behavior is dry-run. Original files are never deleted by this tool.
"""

from __future__ import annotations

import argparse
import asyncio
import json

from sqlmodel import select

from models.sql.image_asset import ImageAsset
from modules.assets.migrations.legacy import inventory_legacy_assets, migrate_legacy_image
from services.database import async_session_maker


async def run(apply: bool) -> None:
    async with async_session_maker() as session:
        if not apply:
            rows = await inventory_legacy_assets(session)
            print(json.dumps([row.__dict__ for row in rows], indent=2))
            return
        summaries = []
        for row in (await session.scalars(select(ImageAsset).order_by(ImageAsset.created_at))).all():
            summaries.append(await migrate_legacy_image(session, row, dry_run=False))
        await session.commit()
        print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Create managed asset copies; originals remain untouched")
    args = parser.parse_args()
    asyncio.run(run(args.apply))
