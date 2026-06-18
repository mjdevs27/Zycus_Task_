"""Prompt versioning: load external Markdown prompts and render them safely.

Prompts live as versioned Markdown files under ``PROMPT_DIR`` (default
``./prompts``). Each file carries simple ``key: value`` frontmatter between
``---`` fences. Keeping prompts out of Python code makes versioning, review,
and changelog tracking straightforward.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.config import Settings, get_settings


class PromptError(Exception):
    """Base class for prompt loading/rendering errors."""


class PromptNotFoundError(PromptError):
    """Raised when a requested prompt file does not exist."""


class PromptRenderError(PromptError):
    """Raised when a required template placeholder has no provided value."""


_PLACEHOLDER_RE = re.compile(r"{{\s*([a-zA-Z0-9_]+)\s*}}")
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def _prompt_dir(settings: Settings | None = None) -> Path:
    return (settings or get_settings()).prompt_dir


def load_prompt(prompt_name: str, settings: Settings | None = None) -> str:
    """Load a prompt's full text by name (with or without ``.md`` suffix)."""
    directory = _prompt_dir(settings)
    filename = prompt_name if prompt_name.endswith(".md") else f"{prompt_name}.md"
    path = directory / filename
    if not path.exists():
        raise PromptNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def parse_prompt_metadata(prompt_text: str) -> dict:
    """Parse simple ``key: value`` frontmatter into a dict (no YAML dependency)."""
    match = _FRONTMATTER_RE.match(prompt_text or "")
    if not match:
        return {}
    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        metadata[key.strip()] = value.strip()
    return metadata


def render_prompt(template: str, variables: dict[str, str]) -> str:
    """Replace ``{{placeholder}}`` tokens with provided values.

    Raises:
        PromptRenderError: if the template references a placeholder that is not
            present in *variables*. Extra variables are ignored.
    """
    variables = variables or {}
    required = set(_PLACEHOLDER_RE.findall(template or ""))
    missing = sorted(name for name in required if name not in variables)
    if missing:
        raise PromptRenderError(
            f"Missing prompt variable(s): {', '.join(missing)}"
        )

    def _replace(match: re.Match) -> str:
        return str(variables[match.group(1)])

    return _PLACEHOLDER_RE.sub(_replace, template)


def get_prompt_version(prompt_name: str, settings: Settings | None = None) -> str:
    """Return the ``version`` field from a prompt's frontmatter."""
    text = load_prompt(prompt_name, settings=settings)
    metadata = parse_prompt_metadata(text)
    version = metadata.get("version")
    if not version:
        raise PromptError(
            f"Prompt '{prompt_name}' has no 'version' in its frontmatter"
        )
    return version
