#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install -r AI_Agent/requirements.txt

if [ ! -f AI_Agent/.env ] && [ -f AI_Agent/.env.example ]; then
  cp AI_Agent/.env.example AI_Agent/.env
fi

ENV_OPENAI_KEY=""
if [ -f AI_Agent/.env ]; then
  ENV_OPENAI_KEY="$(grep '^OPENAI_API_KEY=' AI_Agent/.env | head -n 1 | cut -d '=' -f 2- | tr -d '\r' || true)"
fi
if [ -z "$ENV_OPENAI_KEY" ] || [ "$ENV_OPENAI_KEY" = "sk-your-key" ]; then
  if [ -f /workspaces/.codespaces/shared/.env-secrets ]; then
    ENV_OPENAI_KEY="$(grep '^OPENAI_API_KEY=' /workspaces/.codespaces/shared/.env-secrets | head -n 1 | cut -d '=' -f 2- | tr -d '\r' || true)"
  fi
fi

EFFECTIVE_OPENAI_KEY="${OPENAI_API_KEY:-$ENV_OPENAI_KEY}"
INDEX_FILES_READY=false
if [ -f AI_Agent/knowledge_base.faiss ] && [ -f AI_Agent/knowledge_base.meta.pkl ]; then
  INDEX_FILES_READY=true
fi

if [ "$INDEX_FILES_READY" = false ]; then
  if [ -n "$EFFECTIVE_OPENAI_KEY" ] && [ "$EFFECTIVE_OPENAI_KEY" != "sk-your-key" ]; then
    echo "Building the local vector index for Codespaces..."
    (
      cd AI_Agent
      OPENAI_API_KEY="$EFFECTIVE_OPENAI_KEY" python ./scripts/build_index.py --source ../Knowledge_Base_MarkDown
    )
  else
    echo "Skipping index build: configure a real OPENAI_API_KEY in AI_Agent/.env or Codespaces secrets."
  fi
fi

echo "Codespaces setup complete."
