from __future__ import annotations

import sys
from pathlib import Path


AI_AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AI_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AI_AGENT_DIR))

from scripts import ready_data_tools as tools


RULE2_DOC_ID = "rules/保险公司偿付能力监管规则第2号：最低资本.md"


def test_clean_formula_variables_filters_latex_control_words():
    variables = tools.clean_formula_variables(
        r"""
        $$
        \text{Stress}_t = \text{Stress}_{20} \times (40 - t) / (40 - 20)
        $$
        $$
        \operatorname {Spread} _ {t} = \operatorname {Spread}_{20} \times (40 - t)
        $$
        """
    )

    assert "Stress_t" in variables
    assert "Spread_t" in variables
    assert "times" not in variables
    assert "operatorname" not in variables
    assert "begin" not in variables


def test_search_sections_can_scope_to_rule_doc():
    hits = tools.search_sections("最低资本由哪些部分组成？", doc_ids=[RULE2_DOC_ID], limit=3)

    assert hits
    assert hits[0]["doc_id"] == RULE2_DOC_ID
    assert "最低资本" in hits[0]["text"]


def test_search_formulas_returns_clean_variables_in_formula_order():
    hits = tools.search_formulas("规则第2号最低资本公式", doc_ids=[RULE2_DOC_ID], limit=1)

    assert hits
    assert hits[0]["formula_id"].endswith("#formula-1")
    assert "MC" in hits[0]["variables"]
    assert "LA" in hits[0]["variables"]
    assert "times" not in hits[0]["variables"]


def test_explain_formula_uses_matching_section_evidence():
    explanation = tools.explain_formula(formula_id=f"{RULE2_DOC_ID}#formula-1")

    assert explanation["ok"] is True
    assert explanation["doc_id"] == RULE2_DOC_ID
    assert "MC" in explanation["variables"]
    assert explanation["applicability_evidence"]
