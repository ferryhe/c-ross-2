from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


KNOWLEDGE_BASE_NAME = "偿付能力监管知识库"
DEFAULT_OUTPUT_LANGUAGE = "zh"
REFERENCE_ENV_PATH = Path(r"C:\Projects\IAA_AI_Knowledge_Base\AI_Agent\.env")
CODESPACES_SECRET_ENV_PATH = Path("/workspaces/.codespaces/shared/.env-secrets")
PLACEHOLDER_OPENAI_KEYS = {"", "sk-your-key"}


def has_real_openai_api_key() -> bool:
    return os.getenv("OPENAI_API_KEY", "").strip() not in PLACEHOLDER_OPENAI_KEYS


def _load_env_file(path: Path, *, override: bool = False) -> None:
    if path.exists():
        load_dotenv(dotenv_path=path, override=override)


def load_project_env(project_root: Path) -> None:
    local_env = project_root / ".env"
    _load_env_file(local_env, override=False)
    _load_env_file(CODESPACES_SECRET_ENV_PATH, override=not has_real_openai_api_key())
    _load_env_file(REFERENCE_ENV_PATH, override=not has_real_openai_api_key())
