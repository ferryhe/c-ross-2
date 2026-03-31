from __future__ import annotations

import sys
from pathlib import Path


AI_AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AI_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AI_AGENT_DIR))

from scripts.rich_markdown import build_rich_markdown_html


def test_rich_markdown_pins_marked_version_and_sanitizes_html():
    html = build_rich_markdown_html('<img src="javascript:alert(1)" onerror="alert(2)">')

    assert "marked@12.0.2/marked.min.js" in html
    assert "sanitizeHtmlTree" in html
    assert 'name.startsWith("on")' in html
    assert 'value.startsWith("javascript:")' in html
