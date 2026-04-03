---
name: regulatory-markdown-answering
description: Grounded answering workflow for regulation-heavy Markdown knowledge bases with rules, notices, attachments, formulas, thresholds, reporting obligations, and version adjustments. Use when an AI agent needs to answer questions about regulatory documents by first locating official titles or numbers, then using summary search, evidence retrieval, related notices/attachments, and citation-backed synthesis instead of freeform chatbot behavior.
---

# Goal

Produce verifiable answers over regulatory Markdown, while minimizing unsupported inference.

# Workflow

1. Classify the question as `locate`, `summary`, `formula`, `comparison`, `version`, `compliance`, or `analysis`.
2. If the question mentions a rule number, attachment number, or official notice title, call title search first.
3. If the question asks for overview, major content, scope, or comparison, call summary search before retrieving evidence.
4. If the question asks about formulas, variables, thresholds, coefficients, tables, or curves, prioritize section-level evidence and formula/table snippets.
5. If the question asks about adjustments, implementation, transition period, optimization, or extension, expand to related notices before final synthesis.
6. Synthesize only after evidence is grounded in retrieved Markdown.

# Mandatory answer rules

- Start with a direct conclusion.
- Cite retrieved evidence for every substantive claim.
- Separate `regulatory requirement` from `known facts` when the user asks for compliance judgment.
- Explain formulas with variable meaning and applicability; do not only restate LaTeX.
- For comparison questions, split into common points, differences, and relationship.
- If evidence is incomplete, say what is missing and which Markdown file or section should be checked next.

# Tool expectations

- Use title search to resolve official document candidates.
- Use summary search to narrow the document set.
- Use evidence retrieval for article-, section-, table-, and formula-level support.
- Use related notice or attachment expansion when the answer may have been adjusted after the base rule.
