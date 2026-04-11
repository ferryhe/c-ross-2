from __future__ import annotations

import sys
from pathlib import Path


AI_AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AI_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AI_AGENT_DIR))

from scripts import ask as ask_module
from scripts import build_index as build_index_module


def test_prompt_and_empty_response_use_same_fallback_phrase():
    prompt = ask_module.format_user_prompt("Question?", "[1] doc.md\nAnswer")

    assert ask_module.INSUFFICIENT_INFO_RESPONSE in ask_module.get_system_prompt("en")
    assert ask_module.INSUFFICIENT_INFO_RESPONSE in prompt
    assert ask_module.answer_from_hits(client=object(), question="Question?", hits=[]) == ask_module.INSUFFICIENT_INFO_RESPONSE


def test_fallback_encoders_round_trip_whitespace():
    text = "Solvency II\nMinimum capital"

    assert ask_module._FallbackEncoder().decode(ask_module._FallbackEncoder().encode(text)) == text
    assert build_index_module._FallbackEncoder().decode(build_index_module._FallbackEncoder().encode(text)) == text
