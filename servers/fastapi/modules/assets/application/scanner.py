"""Malware scanner boundary.

The development scanner only provides deterministic safety-flow behavior. It
is not represented as production malware protection.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import BinaryIO, Protocol

from modules.assets.domain.models import MalwareScanStatus


@dataclass(frozen=True)
class ScanResult:
    status: MalwareScanStatus
    safe_code: str


class MalwareScanner(Protocol):
    async def scan(self, stream: BinaryIO, *, maximum_bytes: int) -> ScanResult: ...


class UnavailableScanner:
    async def scan(self, stream: BinaryIO, *, maximum_bytes: int) -> ScanResult:
        return ScanResult(MalwareScanStatus.UNAVAILABLE, "SCANNER_UNAVAILABLE")


class DeterministicDevelopmentScanner:
    """Test/development-only EICAR detector, never a production claim."""

    async def scan(self, stream: BinaryIO, *, maximum_bytes: int) -> ScanResult:
        read = 0
        marker = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"
        tail = b""
        while True:
            chunk = stream.read(min(1024 * 1024, maximum_bytes - read + 1))
            if not chunk:
                break
            read += len(chunk)
            if read > maximum_bytes:
                return ScanResult(MalwareScanStatus.ERROR, "SCAN_SIZE_LIMIT")
            combined = tail + chunk
            if marker in combined:
                return ScanResult(MalwareScanStatus.INFECTED, "MALWARE_TEST_SIGNATURE")
            tail = combined[-len(marker):]
        return ScanResult(MalwareScanStatus.CLEAN, "DEVELOPMENT_SCAN_CLEAN")


def get_malware_scanner() -> MalwareScanner:
    mode = os.getenv("ASSET_SCANNER_MODE", "unavailable").strip().lower()
    if mode in {"development", "fake"}:
        if os.getenv("PRESENTON_ENV", "development").lower() == "production":
            raise RuntimeError("The deterministic development scanner is forbidden in production")
        return DeterministicDevelopmentScanner()
    return UnavailableScanner()
