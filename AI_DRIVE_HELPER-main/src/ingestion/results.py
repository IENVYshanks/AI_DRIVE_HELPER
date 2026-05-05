from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FileProcessResult:
    drive_file: dict
    error_message: str | None = None

    @property
    def failed(self) -> bool:
        return self.error_message is not None
