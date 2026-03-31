#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip
python -m pip install -r AI_Agent/requirements.txt

if [ ! -f AI_Agent/.env ] && [ -f AI_Agent/.env.example ]; then
  cp AI_Agent/.env.example AI_Agent/.env
fi

echo "Codespaces setup complete."
