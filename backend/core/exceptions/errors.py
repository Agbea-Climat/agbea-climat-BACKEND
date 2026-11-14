"""Erreurs métier. Les services lèvent ces exceptions, sans dépendre de HTTP.

Format renvoyé au client : {"error": {"code": "...", "message": "...", "details"?: ...}}
Codes en snake_case (voir CLAUDE.md, règle 3).
"""
from typing import Any, Optional


class ApiError(Exception):
    status_code = 400

    def __init__(self, code: str, message: str, details: Optional[Any] = None,
                 status_code: Optional[int] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
        if status_code is not None:
            self.status_code = status_code

    def to_dict(self) -> dict:
        d = {"code": self.code, "message": self.message}
        if self.details is not None:
            d["details"] = self.details
        return d


class BadRequest(ApiError):
    status_code = 400


class NotFound(ApiError):
    status_code = 404


class NotImplementedYet(ApiError):
    status_code = 501
