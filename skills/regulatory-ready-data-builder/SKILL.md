---
name: regulatory-ready-data-builder
description: Build chatbot-ready and AI-agent-ready data artifacts from regulation-heavy Markdown corpora. Use when Codex needs to transform rules, notices, attachments, formulas, and tables into deterministic ready-data outputs such as catalogs, aliases, summaries, structured sections, formula cards, and relation graphs for downstream RAG systems or agent workflows.
---

# Goal

Turn Markdown regulations into reusable ready-data artifacts instead of coupling every consumer to raw Markdown parsing.

# Workflow

1. Read the Markdown corpus and front matter metadata.
2. Build a document catalog with stable `doc_id`, `title`, `category`, and `path`.
3. Generate deterministic aliases for titles, rule numbers, attachment numbers, and common shorthand.
4. Build document summaries from headings and intro paragraphs.
5. Split documents into structured sections and label likely content types such as `article`, `formula`, `table`, `obligation`, and `threshold`.
6. Extract formula cards with nearby article and heading context.
7. Build a lightweight relations graph from explicit references such as `规则第X号` and `附件X`.
8. Write the results as versionable JSON/JSONL artifacts.

# Rules

- Prefer deterministic extraction over online summarization during build steps.
- Keep identifiers stable across rebuilds when source paths do not change.
- Preserve direct links back to the Markdown path in every artifact.
- Emit a build manifest with artifact counts and timestamps.
- Treat the ready-data outputs as the contract for downstream chatbot and agent consumers.

# Output expectations

- `doc_catalog.jsonl`
- `title_aliases.jsonl`
- `doc_summaries.jsonl`
- `sections_structured.jsonl`
- `formula_cards.jsonl`
- `relations_graph.json`
- `ready_data_manifest.json`
