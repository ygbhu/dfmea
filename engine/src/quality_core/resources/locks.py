from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType

from quality_core.cli.errors import QualityCliError

DEFAULT_LOCK_TIMEOUT_SECONDS = 5.0


def project_lock_path(project_root: Path) -> Path:
    return project_root / ".quality" / "locks" / "project.lock"


@dataclass(slots=True)
class ProjectWriteLock:
    project_root: Path
    timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS
    poll_seconds: float = 0.05
    _fd: int | None = None

    @property
    def path(self) -> Path:
        return project_lock_path(self.project_root)

    def acquire(self) -> ProjectWriteLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + max(self.timeout_seconds, 0)
        while True:
            try:
                self._fd = os.open(
                    self.path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
                os.write(self._fd, _lock_payload().encode("utf-8"))
                return self
            except FileExistsError as exc:
                if time.monotonic() >= deadline:
                    raise QualityCliError(
                        code="FILE_LOCKED",
                        message=f"Project write lock is held at '{self.path}'.",
                        path=str(self.path),
                        suggestion="Wait for the other write command to finish and retry.",
                    ) from exc
                time.sleep(self.poll_seconds)

    def release(self) -> None:
        if self._fd is None:
            return
        os.close(self._fd)
        self._fd = None
        self.path.unlink(missing_ok=True)

    def __enter__(self) -> ProjectWriteLock:
        return self.acquire()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.release()


def _lock_payload() -> str:
    acquired_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return f"pid: {os.getpid()}\nacquiredAt: {acquired_at}\n"
