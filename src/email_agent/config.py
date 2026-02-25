from __future__ import annotations

from pathlib import Path
from typing import Iterable

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

SYSTEM_PROMPT_PATHS: tuple[Path, ...] = (
    Path("~/.email-agent/EMAILS.md").expanduser(),
    Path("./EMAILS.md"),
    Path("./prompts/EMAILS.md"),
)


def load_environment() -> None:
    if load_dotenv is not None:
        load_dotenv()


def load_system_prompt(paths: Iterable[Path] = SYSTEM_PROMPT_PATHS) -> str | None:
    for path in paths:
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            print(f"Failed to read system prompt from {path}: {exc}")
            continue
        if content:
            return content
    return None
