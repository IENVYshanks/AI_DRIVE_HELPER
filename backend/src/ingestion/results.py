from __future__ import annotations

"""Small value objects passed between file processing and retry coordination."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FileProcessResult:
    """Outcome for one Drive file; an error marks it for retry/final failure."""
    drive_file: dict
    error_message: str | None = None

    @property
    def failed(self) -> bool:
        """Return whether processing produced an error message."""
        return self.error_message is not None
