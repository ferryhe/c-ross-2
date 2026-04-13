---
name: regulatory-markdown-answering
description: Answer questions over this repo's regulation-ready Markdown data layer. Use when an AI agent needs to answer questions about rules, notices, attachments, formulas, thresholds, implementation notices, or reporting obligations by reading `Knowledge_Base_MarkDown/ready_data/` first, narrowing scope by title or number, then grounding the final answer in structured sections or raw Markdown instead of freeform chatbot guessing.
---

# Goal

Produce verifiable answers from this repo's `ready_data` artifacts with the smallest correct scope and the least unsupported inference.

# Workflow

1. Classify the question as `catalog`, `locate`, `summary`, `formula`, `comparison`, `version`, `compliance`, or `analysis`.
2. For counts or directory questions, answer from `doc_catalog.jsonl` or `manifest.json` directly instead of retrieval.
3. If the question contains a rule number, attachment number, or exact notice title, resolve the target document from `doc_catalog.jsonl` and `title_aliases.jsonl` first, then keep the initial scope to that `doc_id`.
4. If the question asks for overview, scope, or major content, read `doc_summaries.jsonl` first and use `summary_structured`, `focus_points`, and headings to build the outline.
5. If the question asks for a requirement, article, threshold, table, formula, or variable, use `sections_structured.jsonl` as the primary evidence layer.
6. If the question asks for a formula, use `formula_cards.jsonl` to locate the formula and use the matching structured section to explain variable meaning, applicability, and nearby rule text.
7. Expand to notices, attachments, or related rules only when the question asks about implementation, transition, optimization, adjustments, or when the chosen section explicitly points to them.
8. Fall back to raw Markdown only when the `ready_data` artifacts are insufficient or obviously noisy.

# Preferred Commands

Use the unified CLI from the repo root when answering as an agent:

```powershell
python .\cross2.py plan --question "规则第2号主要内容是什么"
python .\cross2.py evidence --question "控制风险最低资本按照哪一项规则计量？"
python .\cross2.py search sections --query "最低资本由哪些部分组成？" --doc-id "rules/保险公司偿付能力监管规则第2号：最低资本.md"
python .\cross2.py search formulas --query "规则第2号最低资本公式" --doc-id "rules/保险公司偿付能力监管规则第2号：最低资本.md"
python .\cross2.py explain formula --formula-id "rules/保险公司偿付能力监管规则第2号：最低资本.md#formula-1"
python .\cross2.py trace relations --doc-id "rules/保险公司偿付能力监管规则第2号：最低资本.md"
python .\cross2.py answer --question "最低资本由哪些部分组成？" --mode verified
```

# Artifact Roles

- `doc_catalog.jsonl`: document identity, numbering, aliases, headings, and direct catalog answers
- `title_aliases.jsonl`: shorthand, rule number, attachment number, and notice-title lookup
- `doc_summaries.jsonl`: overview and scope narrowing
- `sections_structured.jsonl`: article-level, requirement-level, threshold-level, table-level, and formula-adjacent evidence
- `formula_cards.jsonl`: formula lookup only; do not rely on it alone for semantic explanation
- `relations_graph.json` and `related_doc_ids`: expansion hints, not authoritative regulatory conclusions

# Mandatory Answer Rules

- Start with a direct conclusion.
- Keep exact-number questions scoped to the matching document before exploring related material.
- Treat `related_doc_ids` and relation edges as navigation hints; confirm the substantive claim in section text or raw Markdown before using it.
- Explain formulas with variable meaning and applicability; do not only restate LaTeX.
- Filter LaTeX control words from variable explanations; keep real variables such as `MC`, `LA`, `Stress_t`, and `Spread_t`.
- Prefer section evidence over summary text when the question asks "由哪些部分组成", "按照哪项规则计量", "第几条怎么规定", or similar article-level questions.
- If `summary_short` is noisy because of OCR notes, image placeholders, or publish-date boilerplate, use `summary_structured`, headings, and section text instead.
- Separate regulatory text from your own inference, and say when evidence is incomplete.
