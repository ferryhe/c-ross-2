from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.normalize_markdown import normalize_math_entities


def test_normalize_math_entities_decodes_only_math_segments():
    text = "t 为年度，$20 &lt; t \\leq 40$；正文里保留 &lt; 文本。"

    cleaned = normalize_math_entities(text)

    assert "$20 < t \\leq 40$" in cleaned
    assert "正文里保留 &lt; 文本" in cleaned


def test_normalize_math_entities_decodes_alignment_in_display_math():
    text = "$$\\begin{cases} 0 &amp; x &lt; 1 \\\\ 1 &amp; x &gt; 1 \\end{cases}$$"

    cleaned = normalize_math_entities(text)

    assert "&amp;" not in cleaned
    assert "&lt;" not in cleaned
    assert "&gt;" not in cleaned
    assert "\\begin{cases} 0 & x < 1 \\\\ 1 & x > 1 \\end{cases}" in cleaned


def test_normalize_math_entities_repairs_broken_cjk_subscripts():
    text = "$\\mathrm{OL}_{\\巨灾_i}$ $\\mathrm{MC}_{\\客户}$ $\\mathrm{NE}_{\\短期寿险}$"

    cleaned = normalize_math_entities(text)

    assert "\\mathrm{OL}_{\\text{巨灾}_i}" in cleaned
    assert "\\mathrm{MC}_{\\text{客户}}" in cleaned
    assert "\\mathrm{NE}_{\\text{短期寿险}}" in cleaned
