"""Assembles the system prompt handed to any Agent (main REPL agent or a sub-agent) from
the persona/policy markdown files. Deliberately no templating engine — just reading files
and joining them with clear "---" separators, so the files stay plain, editable prose.
"""

from __future__ import annotations

from pathlib import Path

_PERSONA_DIR = Path(__file__).resolve().parent
DEFAULT_POLICY_PATH = _PERSONA_DIR / "policy.md"
DEFAULT_PERSONA_PATH = _PERSONA_DIR / "miku.md"

_SEPARATOR = "\n\n---\n\n"


def load_system_prompt(
    persona_path: Path | str | None = None,
    policy_path: Path | str | None = None,
    extra_context: str | None = None,
) -> str:
    """Builds the full system prompt: policy.md (operating scope) first, establishing what
    Miku will and won't refuse before her identity/tone even come up, then miku.md
    (identity/expertise/teaching style/tone), then optionally `extra_context` appended last
    (e.g. a sub-agent role's scope suffix, or caller-assembled runtime context like cwd/git
    branch — this function accepts it as a pre-built string, it does not compute it).

    Paths default to the two files living alongside this loader, resolved relative to this
    file's own directory rather than the process's current working directory — Hermes is
    launched from inside whatever project the user is working on, so cwd is never a safe
    place to look for persona files.

    Missing files are skipped rather than raised, so a user who deletes/renames one of these
    files gets a degraded-but-working prompt instead of a crash.
    """
    policy_file = Path(policy_path) if policy_path is not None else DEFAULT_POLICY_PATH
    persona_file = Path(persona_path) if persona_path is not None else DEFAULT_PERSONA_PATH

    sections: list[str] = []

    if policy_file.is_file():
        policy_text = policy_file.read_text(encoding="utf-8").strip()
        if policy_text:
            sections.append(policy_text)

    if persona_file.is_file():
        persona_text = persona_file.read_text(encoding="utf-8").strip()
        if persona_text:
            sections.append(persona_text)

    if extra_context and extra_context.strip():
        sections.append(extra_context.strip())

    return _SEPARATOR.join(sections)
