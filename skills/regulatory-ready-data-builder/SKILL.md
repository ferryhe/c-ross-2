---
name: regulatory-ready-data-builder
description: Build or refresh this repo's chatbot-ready and AI-agent-ready data artifacts from regulation-heavy Markdown. Use when Codex needs to regenerate `Knowledge_Base_MarkDown/ready_data/`, update deterministic summaries, rebuild structured sections, extract formula cards, or refresh lightweight relation hints after the Markdown corpus changes.
---

# Goal

Turn raw regulation Markdown into stable `ready_data` artifacts so downstream chatbot and AI agent flows do not have to rediscover document structure from scratch.

# Workflow

1. Read the Markdown corpus and front matter metadata from `Knowledge_Base_MarkDown/`.
2. Build stable `doc_id`, `path`, `title`, `category`, and alias records before generating any higher-level artifact.
3. Generate `doc_catalog.jsonl` and `title_aliases.jsonl`.
4. Generate `doc_summaries.jsonl` from headings and informative intro paragraphs.
5. Generate `sections_structured.jsonl` with section kind, content type, article number, and mention lists.
6. Generate `formula_cards.jsonl` from formula-bearing sections.
7. Generate `relations_graph.json` and propagate lightweight `related_doc_ids` into summaries.
8. Write `ready_data_manifest.json`, then inspect counts and a few sample rows before considering the build complete.

# Rules

- Prefer deterministic extraction over online summarization during build steps.
- Keep identifiers stable across rebuilds when source paths do not change.
- Preserve direct links back to the Markdown path in every artifact.
- Emit a build manifest with artifact counts and timestamps.
- Treat the ready-data outputs as the contract for downstream chatbot and agent consumers.
- Prefer informative intro paragraphs over OCR boilerplate, image placeholders, or date-only lines when setting `summary_short`.
- Treat `relations_graph.json` and `related_doc_ids` as navigation hints; do not overstate them as authoritative legal semantics.
- Avoid self-links and obviously noisy relation edges.
- Validate the builder with tests and spot-check a few artifacts after regeneration.

# Output expectations

- `doc_catalog.jsonl`
- `title_aliases.jsonl`
- `doc_summaries.jsonl`
- `sections_structured.jsonl`
- `formula_cards.jsonl`
- `relations_graph.json`
- `ready_data_manifest.json`
