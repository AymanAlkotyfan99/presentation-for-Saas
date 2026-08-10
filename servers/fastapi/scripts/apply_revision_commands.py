"""JSON-lines bridge used by cross-runtime revision replay contract tests."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.presentations.domain import canonical_checksum, canonical_json
from modules.presentations.revision_commands import apply_commands


def main() -> None:
    request = json.load(sys.stdin)
    result = apply_commands(request["document"], request["commands"])
    sys.stdout.write(json.dumps({
        "document": result,
        "canonicalJson": canonical_json(result),
        "checksum": canonical_checksum(result),
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
