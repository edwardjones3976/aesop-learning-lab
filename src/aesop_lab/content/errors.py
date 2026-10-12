"""Content validation errors. Codes are stable; messages are for the author."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Issue:
    path: str
    code: str
    message: str


class ContentValidationError(ValueError):
    """A rejected pack. `issues` lists every problem found, not only the first."""

    def __init__(self, issues: tuple[Issue, ...]) -> None:
        self.issues = issues
        lines = [f"{issue.path or '<pack>'}: [{issue.code}] {issue.message}" for issue in issues]
        super().__init__("content pack is invalid:\n" + "\n".join(lines))
