"""Chat-completion parameter contract per model family.

`gpt-5*` and `gpt-6*` reject any non-default `temperature` (HTTP 400:
"Unsupported value: 'temperature' does not support 0.2 with this model"), so the
request must omit the parameter for those families. Other families keep the
caller's temperature. Regression guard for switching the C-Ross chat model to
`gpt-6-luna`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

AI_AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AI_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AI_AGENT_DIR))

from scripts import ask as ask_module


class _CapturingClient:
    """Minimal OpenAI client stub that records the kwargs it receives."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        outer = self

        def _create(**kwargs):
            outer.calls.append(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]
            )

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=_create))


def _call_kwargs(model: str, temperature: float = 0.2) -> dict:
    client = _CapturingClient()
    ask_module._create_chat_completion(
        client,
        [{"role": "user", "content": "hi"}],
        temperature=temperature,
        model=model,
    )
    assert len(client.calls) == 1
    return client.calls[0]


def test_temperature_locked_families_omit_temperature():
    for model in ("gpt-6-luna", "gpt-5.6-luna", "openai/gpt-6-luna"):
        kwargs = _call_kwargs(model)
        assert kwargs["model"] == model
        assert "temperature" not in kwargs, f"{model} must not send temperature"


def test_other_families_keep_caller_temperature():
    for model in ("gpt-4o-mini", "deepseek-chat"):
        kwargs = _call_kwargs(model, temperature=0.3)
        assert kwargs["temperature"] == 0.3, model
