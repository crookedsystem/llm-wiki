from __future__ import annotations

import shlex
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


class CommandRunner:
    def __init__(self, *, dry_run: bool) -> None:
        self.dry_run = dry_run

    def command_exists(self, command: str) -> bool:
        return self.dry_run or shutil.which(command) is not None

    def run(
        self,
        args: Sequence[str],
        *,
        check: bool = True,
        capture: bool = False,
    ) -> CommandResult:
        if self.dry_run:
            print(f"[dry-run] {_quote_command(args)}")
            return CommandResult(returncode=0, stdout="", stderr="")

        completed = subprocess.run(
            list(args),
            check=False,
            capture_output=capture,
            text=True,
        )
        if check and completed.returncode != 0:
            raise subprocess.CalledProcessError(
                completed.returncode,
                list(args),
                output=completed.stdout,
                stderr=completed.stderr,
            )
        return CommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )


def _quote_command(args: Sequence[str]) -> str:
    return " ".join(shlex.quote(arg) for arg in args)


def copy_directory(source: Path, destination: Path, *, dry_run: bool) -> None:
    if not source.is_dir():
        raise FileNotFoundError(f"Skill source not found: {source}")
    if dry_run:
        print(f"[dry-run] copy {source} -> {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True)
