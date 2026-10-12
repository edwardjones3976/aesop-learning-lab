"""Stable, user-displayable assessment errors."""

from __future__ import annotations


class AssessmentError(ValueError):
    """A rejected assessment request. The code is stable; the message is for people."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
