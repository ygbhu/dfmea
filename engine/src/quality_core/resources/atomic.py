from __future__ import annotations

import os
import tempfile
from pathlib import Path

from quality_core.cli.errors import QualityCliError


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_file.write(text)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_path = Path(temp_file.name)
        os.replace(temp_path, path)
    except OSError as exc:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise QualityCliError(
            code="ATOMIC_WRITE_FAILED",
            message=f"Could not atomically write '{path}'.",
            path=str(path),
            suggestion="Check filesystem permissions and retry the command.",
        ) from exc
