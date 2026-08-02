#!/usr/bin/env python3
"""Fail when production-shaped credentials are present in repository files.

The scanner deliberately reports only detector names and locations. It never
prints the matched value, which keeps CI logs safe while maintainers investigate.
It uses only the Python standard library so the same command works locally and in
CI without installing or downloading a security tool.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Iterable, NamedTuple


class Detector(NamedTuple):
    name: str
    pattern: re.Pattern[str]


DETECTORS = (
    Detector(
        "private-key",
        re.compile(
            r"-----BEGIN (?:(?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY|"
            r"PGP PRIVATE KEY BLOCK)-----"
        ),
    ),
    Detector(
        "jwt",
        re.compile(
            r"(?<![A-Za-z0-9_-])(?P<secret>eyJ[A-Za-z0-9_-]{10,}\."
            r"[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})(?![A-Za-z0-9_-])"
        ),
    ),
    Detector(
        "openai-or-anthropic-key",
        re.compile(
            r"(?<![A-Za-z0-9])(?P<secret>sk-(?:(?:proj|svcacct|ant)-)?"
            r"[A-Za-z0-9_-]{20,})(?![A-Za-z0-9])"
        ),
    ),
    Detector(
        "presenton-access-token",
        re.compile(
            r"(?<![A-Za-z0-9])(?P<secret>sk-presenton-[A-Za-z0-9_-]{12,})"
            r"(?![A-Za-z0-9])"
        ),
    ),
    Detector(
        "github-token",
        re.compile(
            r"(?<![A-Za-z0-9])(?P<secret>gh[pousr]_[A-Za-z0-9]{30,})"
            r"(?![A-Za-z0-9])"
        ),
    ),
    Detector(
        "google-api-key",
        re.compile(
            r"(?<![A-Za-z0-9])(?P<secret>AIza[0-9A-Za-z_-]{30,})"
            r"(?![A-Za-z0-9])"
        ),
    ),
    Detector(
        "aws-access-key",
        re.compile(
            r"(?<![A-Z0-9])(?P<secret>(?:AKIA|ASIA)[A-Z0-9]{16})"
            r"(?![A-Z0-9])"
        ),
    ),
    Detector(
        "stripe-live-key",
        re.compile(
            r"(?<![A-Za-z0-9])(?P<secret>(?:sk|rk)_live_[A-Za-z0-9]{16,})"
            r"(?![A-Za-z0-9])"
        ),
    ),
    Detector(
        "slack-token",
        re.compile(
            r"(?<![A-Za-z0-9])(?P<secret>xox[baprs]-[A-Za-z0-9-]{20,})"
            r"(?![A-Za-z0-9])"
        ),
    ),
    Detector(
        "bearer-token",
        re.compile(
            r"\bBearer\s+(?P<secret>[A-Za-z0-9._~+/=-]{24,})",
            re.IGNORECASE,
        ),
    ),
    Detector(
        "credential-in-url",
        re.compile(
            r"\b[a-z][a-z0-9+.-]*://[^\s/:@]+:"
            r"(?P<secret>[^\s/@]{12,})@",
            re.IGNORECASE,
        ),
    ),
    Detector(
        "assigned-secret",
        re.compile(
            r"\b(?:api[_-]?key|client[_-]?secret|password|private[_-]?key|"
            r"session[_-]?(?:cookie|token)|webhook[_-]?secret|access[_-]?token)"
            r"\s*[=:]\s*[\"'](?P<secret>[A-Za-z0-9._~+/=-]{24,})[\"']",
            re.IGNORECASE,
        ),
    ),
)

SAFE_MARKERS = (
    "configured",
    "dummy",
    "example",
    "fake",
    "invalid",
    "placeholder",
    "redacted",
    "replace",
    "test",
    "your",
)
SAFE_PHRASES = ("clearly-fake", "not-a-real")

MAX_TEXT_FILE_BYTES = 25 * 1024 * 1024
FORBIDDEN_ARTIFACT_MARKERS = (
    "/.playwright-cli/",
    "/playwright-report/",
    "/test-results/",
    "/blob-report/",
)
FORBIDDEN_ARTIFACT_SUFFIXES = (".trace.zip", ".har", ".webm")


def _repository_paths(root: Path) -> list[str]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [
        path
        for path in result.stdout.decode("utf-8", "surrogateescape").split("\0")
        if path
    ]


def _is_explicitly_fake(value: str) -> bool:
    normalized = value.casefold()
    tokens = set(filter(None, re.split(r"[^a-z0-9]+", normalized)))
    return bool(tokens.intersection(SAFE_MARKERS)) or any(
        phrase in normalized for phrase in SAFE_PHRASES
    )


def _redact(value: str) -> str:
    redacted = value
    for detector in DETECTORS:
        redacted = detector.pattern.sub("[REDACTED]", redacted)
    return redacted


def _findings(path: str, text: str) -> Iterable[tuple[int, str]]:
    for line_number, line in enumerate(text.splitlines(), start=1):
        for detector in DETECTORS:
            for match in detector.pattern.finditer(line):
                secret = match.groupdict().get("secret") or match.group(0)
                if _is_explicitly_fake(secret):
                    continue
                yield line_number, detector.name


def _is_forbidden_artifact(relative_path: str) -> bool:
    normalized_path = f"/{relative_path.replace(os.sep, '/')}"
    return any(
        marker in normalized_path for marker in FORBIDDEN_ARTIFACT_MARKERS
    ) or normalized_path.casefold().endswith(FORBIDDEN_ARTIFACT_SUFFIXES)


def scan(root: Path) -> tuple[list[tuple[str, int, str]], int, int]:
    findings: list[tuple[str, int, str]] = []
    checked = 0
    skipped_large = 0

    for relative_path in _repository_paths(root):
        path = root / Path(relative_path)
        if not path.is_file():
            # A tracked file may be intentionally deleted in the current patch.
            continue
        if _is_forbidden_artifact(relative_path):
            findings.append((relative_path, 1, "generated-artifact"))
            continue
        if path.stat().st_size > MAX_TEXT_FILE_BYTES:
            skipped_large += 1
            continue

        data = path.read_bytes()
        if b"\0" in data:
            continue
        checked += 1
        text = data.decode("utf-8", errors="replace")
        findings.extend(
            (relative_path.replace(os.sep, "/"), line_number, detector)
            for line_number, detector in _findings(relative_path, text)
        )

    return findings, checked, skipped_large


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Scan tracked and non-ignored working-tree files for "
            "production-shaped secrets."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Git repository root (defaults to this script's repository).",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    try:
        findings, checked, skipped_large = scan(root)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"Secret scan could not run: {type(error).__name__}", file=sys.stderr)
        return 2

    if findings:
        print(
            "Secret scan failed. Matched values are redacted; inspect these locations:",
            file=sys.stderr,
        )
        for path, line_number, detector in findings:
            print(
                f"- {_redact(path)}:{line_number}: {detector} [REDACTED]",
                file=sys.stderr,
            )
        return 1

    print(
        f"Secret scan passed: {checked} repository text files checked"
        f"; {skipped_large} oversized files skipped."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
