from __future__ import annotations

import sys
from pathlib import Path


AI_AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AI_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AI_AGENT_DIR))

from scripts import rich_markdown
from scripts.rich_markdown import (
    build_github_blob_url,
    build_inline_rich_markdown_html,
    build_rich_markdown_html,
    estimate_component_height,
    linkify_github_blob_references,
    linkify_numeric_citations,
)


def test_build_rich_markdown_html_includes_math_and_table_support():
    html = build_rich_markdown_html("| a | b |\n|---|---|\n| 1 | 2 |\n\n$$x^2$$\n")

    assert "marked.min.js" in html
    assert "katex.min.js" in html
    assert "renderMathInElement" in html
    assert "streamlit:setFrameHeight" in html
    assert "| a | b |" in html


def test_build_rich_markdown_html_includes_responsive_frame_sizing():
    html = build_rich_markdown_html("hello", min_height=120, max_height=None)

    assert 'const minFrameHeight = 120;' in html
    assert "const maxFrameHeight = null;" in html
    assert "scheduleFrameHeightSync" in html
    assert 'window.visualViewport.addEventListener("resize"' in html
    assert "document.fonts.ready.then" in html


def test_build_inline_rich_markdown_html_uses_dom_rendering_without_iframe_height_logic():
    html = build_inline_rich_markdown_html("hello", root_id="rich-markdown-test", min_height=120, max_height=None)

    assert 'id="rich-markdown-test"' in html
    assert 'data-rich-markdown-root="rich-markdown-test"' in html
    assert "ensureScript" in html
    assert "unsafe_allow_javascript" not in html
    assert "streamlit:setFrameHeight" not in html
    assert "marked.parse" in html


def test_build_rich_markdown_html_escapes_script_closing_tags():
    html = build_rich_markdown_html("</script>\n$E=mc^2$")

    assert "</script>" not in html.split("const markdownSource = ", 1)[1].split(";", 1)[0]
    assert "<\\/script>" in html


def test_estimate_component_height_scales_with_content():
    short_height = estimate_component_height("short")
    long_height = estimate_component_height("\n".join(["line"] * 40))

    assert long_height > short_height
    assert short_height >= 160


def test_estimate_component_height_allows_unbounded_growth():
    huge_text = "\n".join(["line"] * 300)

    bounded = estimate_component_height(huge_text, max_height=1400)
    unbounded = estimate_component_height(huge_text, max_height=None)

    assert bounded == 1400
    assert unbounded > bounded


def test_linkify_github_blob_references_converts_citations(monkeypatch):
    monkeypatch.setattr(rich_markdown, "get_github_blob_base_url", lambda: "https://github.com/ferryhe/c-ross-2/blob/main")

    linked = linkify_github_blob_references("[1] Knowledge_Base_MarkDown/rules/保险公司偿付能力监管规则第2号：最低资本.md")

    assert linked.startswith("[[1] Knowledge_Base_MarkDown/rules/")
    assert "%E4%BF%9D%E9%99%A9" in linked
    assert "blob/main/Knowledge_Base_MarkDown/rules/" in linked


def test_build_github_blob_url_normalizes_repo_paths(monkeypatch):
    monkeypatch.setattr(rich_markdown, "get_github_blob_base_url", lambda: "https://github.com/ferryhe/c-ross-2/blob/main")

    url = build_github_blob_url(r".\Knowledge_Base_MarkDown\rules\foo bar.md")

    assert url == "https://github.com/ferryhe/c-ross-2/blob/main/Knowledge_Base_MarkDown/rules/foo%20bar.md"


def test_build_rich_markdown_html_protects_math_and_links():
    html = build_rich_markdown_html("[1] Knowledge_Base_MarkDown/rules/test.md\n\n$$\\mathrm{MC}{\\text{损失发生}}$$")

    assert "extractMathSegments" in html
    assert "restoreMathSegments" in html
    assert "normalizeLikelyLatexArtifacts" in html
    assert "configureLinks" in html
    assert "Knowledge_Base_MarkDown/rules/test.md" in html
