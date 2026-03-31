from __future__ import annotations

import sys
from pathlib import Path


AI_AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AI_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AI_AGENT_DIR))

from scripts.rich_markdown import build_rich_markdown_html, estimate_component_height


def test_build_rich_markdown_html_includes_math_and_table_support():
    html = build_rich_markdown_html("| a | b |\n|---|---|\n| 1 | 2 |\n\n$$x^2$$\n")

    assert "marked.min.js" in html
    assert "katex.min.js" in html
    assert "renderMathInElement" in html
    assert "streamlit:setFrameHeight" in html
    assert "| a | b |" in html


def test_build_rich_markdown_html_escapes_script_closing_tags():
    html = build_rich_markdown_html("</script>\n$E=mc^2$")

    assert "</script>" not in html.split("const markdownSource = ", 1)[1].split(";", 1)[0]
    assert "<\\/script>" in html


def test_estimate_component_height_scales_with_content():
    short_height = estimate_component_height("short")
    long_height = estimate_component_height("\n".join(["line"] * 40))

    assert long_height > short_height
    assert short_height >= 160
