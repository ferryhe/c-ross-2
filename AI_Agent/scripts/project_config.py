from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


KNOWLEDGE_BASE_NAME = "偿付能力监管知识库"
DEFAULT_OUTPUT_LANGUAGE = "zh"
REFERENCE_ENV_PATH = Path(r"C:\Projects\IAA_AI_Knowledge_Base\AI_Agent\.env")


def load_project_env(project_root: Path) -> None:
    local_env = project_root / ".env"
    if local_env.exists():
        load_dotenv(dotenv_path=local_env, override=False)
    if REFERENCE_ENV_PATH.exists():
        load_dotenv(dotenv_path=REFERENCE_ENV_PATH, override=False)
