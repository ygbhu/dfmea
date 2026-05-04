from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from quality_core.cli.errors import QualityCliError


@dataclass(frozen=True, slots=True)
class GitCompleted:
    args: tuple[str, ...]
    stdout: str
    stderr: str


def find_git_root(start: Path) -> Path:
    completed = git(
        "rev-parse",
        "--show-toplevel",
        cwd=start,
        error_code="RESTORE_PRECONDITION_FAILED",
        suggestion="Run the command inside a Git workspace.",
    )
    return Path(completed.stdout.strip()).resolve()


def git(
    *args: str,
    cwd: Path,
    error_code: str = "GIT_CONFLICT",
    suggestion: str = "Inspect Git state and retry the command.",
    allow_failure: bool = False,
) -> GitCompleted:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    result = GitCompleted(args=tuple(args), stdout=completed.stdout, stderr=completed.stderr)
    if completed.returncode != 0 and not allow_failure:
        message = completed.stderr.strip() or completed.stdout.strip() or "Git command failed."
        raise QualityCliError(
            code=error_code,
            message=message,
            target={"gitArgs": list(args)},
            suggestion=suggestion,
        )
    return result


def git_bytes(
    *args: str,
    cwd: Path,
    error_code: str = "GIT_CONFLICT",
    suggestion: str = "Inspect Git state and retry the command.",
) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        message = (
            completed.stderr.decode("utf-8", errors="replace").strip()
            or completed.stdout.decode("utf-8", errors="replace").strip()
            or "Git command failed."
        )
        raise QualityCliError(
            code=error_code,
            message=message,
            target={"gitArgs": list(args)},
            suggestion=suggestion,
        )
    return completed.stdout


def ensure_no_unresolved_conflicts(repo_root: Path) -> None:
    output = git(
        "diff",
        "--name-only",
        "--diff-filter=U",
        cwd=repo_root,
        error_code="GIT_CONFLICT",
    ).stdout
    conflicts = [line for line in output.splitlines() if line.strip()]
    if conflicts:
        raise QualityCliError(
            code="GIT_CONFLICT",
            message="Git has unresolved conflicts in this workspace.",
            target={"paths": conflicts},
            suggestion="Resolve conflicts and rerun the command.",
        )


def current_branch(repo_root: Path) -> str | None:
    completed = git(
        "branch",
        "--show-current",
        cwd=repo_root,
        error_code="GIT_CONFLICT",
        allow_failure=True,
    )
    branch = completed.stdout.strip()
    return branch or None


def current_head(repo_root: Path) -> str | None:
    completed = git(
        "rev-parse",
        "--verify",
        "HEAD",
        cwd=repo_root,
        error_code="GIT_CONFLICT",
        allow_failure=True,
    )
    head = completed.stdout.strip()
    return head or None
