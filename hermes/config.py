"""Config loading: XDG paths, config.yaml + .env merge, per-role model map.

Priority, highest first: real environment variables > .env file > config.yaml > built-in defaults.
Nothing here talks to Ollama or the network — this must stay fast and side-effect-free to load.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_MODELS: dict[str, dict[str, Any]] = {
    # "default" is used for general chat/security-research work — an abliterated model so
    # she doesn't refuse authorized malware-dev/CVE/pentest tasks. Swap freely in config.yaml.
    "default": {"name": "huihui_ai/qwen3-abliterated:30b", "num_ctx": 8192},
    "code": {"name": "qwen3-coder:30b", "num_ctx": 16384},
    "fast": {"name": "huihui_ai/gpt-oss-abliterated:20b", "num_ctx": 8192},
    "embed": {"name": "nomic-embed-text", "num_ctx": 2048},
}


def _xdg_path(env_var: str, home_default: str) -> Path:
    val = os.environ.get(env_var)
    base = Path(val) if val else Path.home() / home_default
    return base / "hermes"


def xdg_config_dir() -> Path:
    return _xdg_path("XDG_CONFIG_HOME", ".config")


def xdg_data_dir() -> Path:
    return _xdg_path("XDG_DATA_HOME", ".local/share")


def xdg_cache_dir() -> Path:
    return _xdg_path("XDG_CACHE_HOME", ".cache")


def _load_dotenv(path: Path) -> None:
    """Tiny .env loader (no python-dotenv dependency) — only fills vars not already set."""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


DEFAULT_PROJECT_INCLUDE = [
    "*.md", "*.txt", "*.rst",
    "*.py", "*.java", "*.kt", "*.c", "*.cpp", "*.h", "*.hpp",
    "*.rs", "*.go", "*.ts", "*.js", "*.yaml", "*.yml", "*.json",
]
DEFAULT_PROJECT_EXCLUDE = [
    "*/.git/*", "*/node_modules/*", "*/build/*", "*/out/*",
    "*/.venv/*", "*/venv/*", "*/vendor/*", "*/dist/*",
]


@dataclass
class ModelProfile:
    name: str
    num_ctx: int = 8192


@dataclass
class ProjectSource:
    """An external codebase/doc tree Miku should track alongside her own knowledge/ folder —
    e.g. your FYP repo. Daily-refreshed the same way as CVE deltas: mtime+hash diff, re-embed
    changed files, prune deleted ones. Retrieval can filter to one project by `name`."""

    name: str
    path: Path
    include: list[str] = field(default_factory=lambda: list(DEFAULT_PROJECT_INCLUDE))
    exclude: list[str] = field(default_factory=lambda: list(DEFAULT_PROJECT_EXCLUDE))


@dataclass
class HermesConfig:
    ollama_host: str
    models: dict[str, ModelProfile]
    config_dir: Path
    data_dir: Path
    cache_dir: Path
    knowledge_dir: Path
    projects: list[ProjectSource] = field(default_factory=list)
    github_token: str | None = None
    nvd_api_key: str | None = None
    malwarebazaar_auth_key: str | None = None
    search_backend: str = "ddgs"
    searxng_url: str | None = None
    shell_auto_confirm: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    def model(self, role: str = "default") -> ModelProfile:
        return self.models.get(role, self.models["default"])

    @property
    def rag_dir(self) -> Path:
        return self.data_dir / "rag"

    @property
    def state_db_path(self) -> Path:
        return self.data_dir / "state.sqlite3"

    @property
    def tool_strategy_cache_path(self) -> Path:
        return self.data_dir / "tool_strategy_cache.json"

    def section(self, name: str) -> dict[str, Any]:
        """Raw nested config (e.g. config.section('shell')) for tool-specific settings."""
        val = self.raw.get(name, {})
        return val if isinstance(val, dict) else {}


def load_config() -> HermesConfig:
    _load_dotenv(REPO_ROOT / ".env")

    config_dir = xdg_config_dir()
    data_dir = xdg_data_dir()
    cache_dir = xdg_cache_dir()
    for d in (config_dir, data_dir, cache_dir):
        d.mkdir(parents=True, exist_ok=True)

    yaml_path = config_dir / "config.yaml"
    raw: dict[str, Any] = {}
    if yaml_path.is_file():
        raw = yaml.safe_load(yaml_path.read_text()) or {}

    models_cfg = {**DEFAULT_MODELS, **(raw.get("models") or {})}
    models = {
        role: ModelProfile(name=spec["name"], num_ctx=int(spec.get("num_ctx", 8192)))
        for role, spec in models_cfg.items()
    }

    default_model_override = os.environ.get("HERMES_MODEL")
    if default_model_override:
        models["default"] = ModelProfile(
            name=default_model_override,
            num_ctx=models.get("default", ModelProfile(name="")).num_ctx,
        )

    knowledge_dir = Path(raw.get("knowledge_dir", REPO_ROOT / "knowledge")).expanduser()

    projects = [
        ProjectSource(
            name=p["name"],
            path=Path(p["path"]).expanduser(),
            include=p.get("include", list(DEFAULT_PROJECT_INCLUDE)),
            exclude=p.get("exclude", list(DEFAULT_PROJECT_EXCLUDE)),
        )
        for p in (raw.get("projects") or [])
    ]

    return HermesConfig(
        ollama_host=os.environ.get("OLLAMA_HOST", raw.get("ollama_host", "http://127.0.0.1:11434")),
        models=models,
        config_dir=config_dir,
        data_dir=data_dir,
        cache_dir=cache_dir,
        knowledge_dir=knowledge_dir,
        projects=projects,
        github_token=os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or raw.get("github_token"),
        nvd_api_key=os.environ.get("NVD_API_KEY") or raw.get("nvd_api_key"),
        malwarebazaar_auth_key=os.environ.get("MALWAREBAZAAR_AUTH_KEY") or raw.get("malwarebazaar_auth_key"),
        search_backend=os.environ.get("HERMES_SEARCH_BACKEND", raw.get("search_backend", "ddgs")),
        searxng_url=os.environ.get("SEARXNG_URL") or raw.get("searxng_url"),
        shell_auto_confirm=os.environ.get("HERMES_SHELL_AUTO_CONFIRM", "").lower() in ("1", "true", "yes")
        or bool(raw.get("shell", {}).get("auto_confirm", False)),
        raw=raw,
    )
