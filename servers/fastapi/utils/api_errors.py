"""Stable API error contracts with backwards-compatible human detail text."""

from collections.abc import Mapping
from typing import Any

from fastapi import HTTPException


class StableAPIError(HTTPException):
    def __init__(
        self,
        status_code: int,
        code: str,
        detail: str,
        *,
        params: Mapping[str, str | int | float | bool] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=dict(headers or {}))
        self.code = code
        self.params = dict(params or {})

    def response_body(self) -> dict[str, Any]:
        return {"detail": self.detail, "code": self.code, "params": self.params}
