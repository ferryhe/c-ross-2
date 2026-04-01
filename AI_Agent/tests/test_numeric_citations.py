from __future__ import annotations

import sys
from pathlib import Path


AI_AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AI_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AI_AGENT_DIR))

from scripts.rich_markdown import linkify_numeric_citations


def test_linkify_numeric_citations_converts_bare_indices_to_links():
    linked = linkify_numeric_citations(
        "答案见 [1]，补充见 [2]。",
        {
            1: "https://github.com/ferryhe/c-ross-2/blob/main/Knowledge_Base_MarkDown/rules/a.md",
            2: "https://github.com/ferryhe/c-ross-2/blob/main/Knowledge_Base_MarkDown/rules/b.md",
        },
    )

    assert linked == (
        "答案见 [[1]](https://github.com/ferryhe/c-ross-2/blob/main/Knowledge_Base_MarkDown/rules/a.md)，"
        "补充见 [[2]](https://github.com/ferryhe/c-ross-2/blob/main/Knowledge_Base_MarkDown/rules/b.md)。"
    )


def test_linkify_numeric_citations_skips_existing_markdown_links():
    linked = linkify_numeric_citations(
        "已经有链接 [1](https://example.com) 和普通引用 [2]",
        {2: "https://github.com/ferryhe/c-ross-2/blob/main/Knowledge_Base_MarkDown/rules/b.md"},
    )

    assert "[1](https://example.com)" in linked
    assert "[[2]](https://github.com/ferryhe/c-ross-2/blob/main/Knowledge_Base_MarkDown/rules/b.md)" in linked
