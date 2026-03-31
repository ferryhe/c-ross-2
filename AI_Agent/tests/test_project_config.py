from __future__ import annotations

import sys
from pathlib import Path

AI_AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AI_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AI_AGENT_DIR))

from scripts import project_config


def test_codespaces_secret_overrides_placeholder_env(tmp_path, monkeypatch):
    project_root = tmp_path / "AI_Agent"
    project_root.mkdir()
    local_env = project_root / ".env"
    local_env.write_text("OPENAI_API_KEY=sk-your-key\n", encoding="utf-8")

    codespaces_env = tmp_path / ".env-secrets"
    codespaces_env.write_text("OPENAI_API_KEY=sk-real-secret\n", encoding="utf-8")

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(project_config, "CODESPACES_SECRET_ENV_PATH", codespaces_env, raising=False)
    monkeypatch.setattr(project_config, "REFERENCE_ENV_PATH", tmp_path / "missing.env", raising=False)

    project_config.load_project_env(project_root)

    assert project_config.has_real_openai_api_key()

