from __future__ import annotations

import os
import json
from pathlib import Path

from dotenv import load_dotenv


KNOWLEDGE_BASE_NAME = "偿付能力监管知识库"
DEFAULT_OUTPUT_LANGUAGE = "zh"
REFERENCE_ENV_PATH = Path(r"C:\Projects\IAA_AI_Knowledge_Base\AI_Agent\.env")
CODESPACES_SECRET_JSON_PATH = Path("/workspaces/.codespaces/shared/user-secrets-envs.json")
PLACEHOLDER_OPENAI_KEYS = {"", "sk-your-key"}


def has_real_openai_api_key() -> bool:
    return os.getenv("OPENAI_API_KEY", "").strip() not in PLACEHOLDER_OPENAI_KEYS


def _load_env_file(path: Path, *, override: bool = False) -> None:
    if path.exists():
        load_dotenv(dotenv_path=path, override=override)


def _load_codespaces_openai_key(*, override: bool = False) -> None:
    if not CODESPACES_SECRET_JSON_PATH.exists():
        return
    try:
        data = json.loads(CODESPACES_SECRET_JSON_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    value = data.get("OPENAI_API_KEY")
    if not isinstance(value, str) or not value.strip():
        return
    if override or "OPENAI_API_KEY" not in os.environ:
        os.environ["OPENAI_API_KEY"] = value.strip()


def load_project_env(project_root: Path) -> None:
    local_env = project_root / ".env"
    _load_env_file(local_env, override=False)
    _load_codespaces_openai_key(override=not has_real_openai_api_key())
    _load_env_file(REFERENCE_ENV_PATH, override=not has_real_openai_api_key())
