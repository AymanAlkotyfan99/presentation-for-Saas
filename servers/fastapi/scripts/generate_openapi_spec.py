#!/usr/bin/env python3
"""Generate or verify the checked-in OpenAPI contract used by the MCP server."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


SERVER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_ROOT))

from api.main import app  # noqa: E402


SPEC_PATH = SERVER_ROOT / "openai_spec.json"


def rendered_spec() -> str:
    return json.dumps(
        app.openapi(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if the checked-in contract differs from the current app.",
    )
    args = parser.parse_args()

    generated = rendered_spec()
    if args.check:
        if not SPEC_PATH.is_file() or SPEC_PATH.read_text(encoding="utf-8") != generated:
            print(
                "openai_spec.json is stale; run scripts/generate_openapi_spec.py",
                file=sys.stderr,
            )
            return 1
        print("Checked-in OpenAPI contract is current.")
        return 0

    SPEC_PATH.write_text(generated, encoding="utf-8", newline="\n")
    print(f"Generated {SPEC_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
