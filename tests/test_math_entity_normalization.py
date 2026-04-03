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
    assert cleaned == "```math\n\\begin{cases}\n0 & x < 1 \\\\\n1 & x > 1\n\\end{cases}\n```"


def test_normalize_math_entities_repairs_broken_cjk_subscripts():
    text = "$\\mathrm{OL}_{\\巨灾_i}$ $\\mathrm{MC}_{\\客户}$ $\\mathrm{NE}_{\\短期寿险}$"

    cleaned = normalize_math_entities(text)

    assert "\\mathrm{OL}_{\\text{巨灾}_i}" in cleaned
    assert "\\mathrm{MC}_{\\text{客户}}" in cleaned
    assert "\\mathrm{NE}_{\\text{短期寿险}}" in cleaned


def test_normalize_math_entities_rewrites_left_array_piecewise_to_cases():
    text = (
        "$$\\mathrm {k} _ {1} = \\left\\{ \\begin{array}{l l} "
        "-0.05 & x \\in (0, 95\\% ] \\\\ 0 & x \\in (95\\%, 100\\% ] "
        "\\end{array} \\right.$$"
    )

    cleaned = normalize_math_entities(text)

    assert "\\left\\{" not in cleaned
    assert "\\right." not in cleaned
    assert "\\begin{cases}" in cleaned
    assert "\\end{cases}" in cleaned
    assert cleaned.startswith("```math\n")
    assert cleaned.endswith("\n```")
    assert "\\begin{cases}\n-0.05 & x \\in (0, 95\\% ] \\\\\n0 & x \\in (95\\%, 100\\% ]\n\\end{cases}" in cleaned


def test_normalize_math_entities_rewrites_display_cases_to_math_fence():
    text = "$$\\mathrm {S F} = \\begin{cases} a & 0 < t \\leq 10 \\\\ b & t > 10 \\end{cases}$$"

    cleaned = normalize_math_entities(text)

    assert cleaned == (
        "```math\n"
        "\\mathrm {S F} = \\begin{cases}\n"
        "a & 0 < t \\leq 10 \\\\\n"
        "b & t > 10\n"
        "\\end{cases}\n"
        "```"
    )


def test_normalize_math_entities_plainifies_simple_inline_references():
    text = (
        "$\\rho$ 为 $\\mathrm{MC}_{\\text{市场}}$ 与 $\\mathrm{MC}_{\\text{信用}}$ 的相关系数，"
        "$\\rho = 0.35$。"
    )

    cleaned = normalize_math_entities(text)

    assert cleaned == "`ρ` 为 `MC_市场` 与 `MC_信用` 的相关系数，`ρ = 0.35`。"


def test_normalize_math_entities_plainifies_inline_subscripts_in_prose():
    text = (
        "（三）$\\mathrm{LA}_{\\text{上限}}$ 为损失吸收效应调整上限；"
        "$\\mathbf{MC}_{\\text{保费及准备金}_i}$ 和 $\\mathbf{MC}_{\\text{保费及准备金}_j}$ 分别为业务类型。"
    )

    cleaned = normalize_math_entities(text)

    assert cleaned == "（三）`LA_上限` 为损失吸收效应调整上限；`MC_保费及准备金_i` 和 `MC_保费及准备金_j` 分别为业务类型。"


def test_normalize_math_entities_keeps_complex_inline_math():
    text = "t 为年度，$20 < t \\leq 40$；当 $\\sum_{i=1}^{36} EP_i < 0$ 时不适用。"

    cleaned = normalize_math_entities(text)

    assert "$20 < t \\leq 40$" in cleaned
    assert "$\\sum_{i=1}^{36} EP_i < 0$" in cleaned


def test_normalize_math_entities_merges_fragmented_decimals_in_fenced_math():
    text = (
        "```math\n"
        "\\mathrm {k} _ {2} = \\begin{cases}\n"
        "0. 1 4 8 & \\mathrm {N E} _ {\\text {船货特险}} \\in (- \\infty , - 1 \\%) \\\\\n"
        "- 0. 0 2 3 & \\mathrm {N E} _ {\\text {船货特险}} \\in [ 2. 5 \\%, 5 \\%)\n"
        "\\end{cases}\n"
        "```"
    )

    cleaned = normalize_math_entities(text)

    assert "0.148" in cleaned
    assert "-0.023" in cleaned
    assert "2.5\\%" in cleaned
    assert "0. 1 4 8" not in cleaned
    assert "- 0. 0 2 3" not in cleaned
