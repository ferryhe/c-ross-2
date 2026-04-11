import argparse
import os
import pickle
import re
import sys
from pathlib import Path
from typing import Iterable, List

import faiss
import numpy as np
import tiktoken
from openai import OpenAI

# Add parent directory to path for utils import
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from project_config import load_project_env
from utils import retry_with_exponential_backoff, validate_file_content

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PROJECT_ROOT.parent.resolve()

load_project_env(PROJECT_ROOT)


def _resolve_path(value: str | None, default: Path) -> Path:
    if not value:
        return default.resolve()
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate.resolve()
    return (PROJECT_ROOT / candidate).resolve()


def derive_section_index_path(index_path: Path) -> Path:
    return index_path.with_name(f"{index_path.stem}.sections{index_path.suffix}")


def derive_section_meta_path(meta_path: Path) -> Path:
    return meta_path.with_name(f"{meta_path.stem}.sections{meta_path.suffix}")


DEFAULT_SOURCE = _resolve_path(os.getenv("SOURCE_DIR"), REPO_ROOT / "Knowledge_Base_MarkDown")
DEFAULT_INDEX = _resolve_path(os.getenv("INDEX_PATH"), PROJECT_ROOT / "knowledge_base.faiss")
DEFAULT_META = _resolve_path(os.getenv("META_PATH"), PROJECT_ROOT / "knowledge_base.meta.pkl")
DEFAULT_SECTION_INDEX = _resolve_path(
    os.getenv("SECTION_INDEX_PATH"),
    derive_section_index_path(DEFAULT_INDEX),
)
DEFAULT_SECTION_META = _resolve_path(
    os.getenv("SECTION_META_PATH"),
    derive_section_meta_path(DEFAULT_META),
)
EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
DEFAULT_EMBED_MAX_TOKENS = int(os.getenv("DOC_INDEX_EMBED_MAX_TOKENS", "6000"))
DEFAULT_SECTION_MAX_TOKENS = int(os.getenv("SECTION_MAX_TOKENS", "1200"))
DEFAULT_SECTION_EMBED_MAX_TOKENS = int(os.getenv("SECTION_INDEX_EMBED_MAX_TOKENS", "1800"))
FRONT_MATTER_PATTERN = re.compile(r"\A---\s*\r?\n.*?\r?\n---\s*\r?\n?", re.DOTALL)
TITLE_PATTERN = re.compile(r'^title:\s*(.+?)\s*$', re.MULTILINE)
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
ARTICLE_PATTERN = re.compile(r"^第[一二三四五六七八九十百千万零两\d]+条")
CLAUSE_PATTERN = re.compile(r"^[（(][一二三四五六七八九十百千万零两\d]+[）)]")
TABLE_LINE_PATTERN = re.compile(r"^\s*\|.+\|\s*$")
MATH_FENCE_START_PATTERN = re.compile(r"^\s*```(?:math)?\s*$")
DISPLAY_MATH_PATTERN = re.compile(r"^\s*\$\$\s*$")

# Lazy-load tiktoken encoder to avoid network calls during import
_enc = None


class _FallbackEncoder:
    def encode(self, text: str) -> list[str]:
        return re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+|[^\s]", text)

    def decode(self, tokens: list[str]) -> str:
        return " ".join(tokens)


def get_encoder():
    """Get tiktoken encoder, loading it lazily."""
    global _enc
    if _enc is None:
        try:
            _enc = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _enc = _FallbackEncoder()
    return _enc


def iter_markdown_files(source: Path) -> Iterable[Path]:
    """Iterate over markdown files with validation."""
    if not source.exists():
        raise FileNotFoundError(f"Source directory not found: {source}")
    for path in sorted(source.rglob("*.md")):
        if path.is_file():
            if path.stat().st_size == 0:
                print(f"[warning] Skipping empty file: {path}")
                continue
            yield path.resolve()


def _document_path(md_path: Path, source: Path) -> str:
    resolved_path = md_path.resolve()
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        try:
            return resolved_path.relative_to(source.resolve()).as_posix()
        except ValueError:
            return md_path.name


def strip_front_matter(text: str) -> tuple[str | None, str]:
    normalized = text.lstrip("\ufeff")
    match = FRONT_MATTER_PATTERN.match(normalized)
    if not match:
        return None, normalized

    front_matter = match.group(0)
    title_match = TITLE_PATTERN.search(front_matter)
    title = None
    if title_match:
        title = title_match.group(1).strip().strip('"').strip("'")
    return title, normalized[match.end() :].lstrip()


def estimate_tokens(text: str) -> int:
    return len(get_encoder().encode(text))


def chunk_text(text: str, max_tokens: int = 500, overlap: int = 80) -> Iterable[str]:
    """
    Legacy token chunking helper retained as a fallback for pathological long blocks.
    """
    enc = get_encoder()
    tokens = enc.encode(text)
    if not tokens:
        return []
    step = max(1, max_tokens - overlap)
    for i in range(0, len(tokens), step):
        chunk = enc.decode(tokens[i : i + max_tokens])
        if chunk.strip():
            yield chunk


def _clean_heading_text(value: str) -> str:
    return " ".join(value.split()).strip()


def _build_preface(path: str, title: str | None, headings: list[str], kind: str | None = None) -> list[str]:
    parts = [f"Path: {path}"]
    if title:
        parts.append(f"Title: {title}")
    if headings:
        parts.append("Headings: " + " | ".join(_clean_heading_text(item) for item in headings if item))
    if kind:
        parts.append(f"Section type: {kind}")
    return parts


def build_embedding_text(path: str, text: str, title: str | None, *, max_tokens: int) -> str:
    enc = get_encoder()
    headings = []
    for _, heading in HEADING_PATTERN.findall(text):
        cleaned = _clean_heading_text(heading)
        if cleaned:
            headings.append(cleaned)

    composed = "\n".join(_build_preface(path, title, headings)) + "\n\n" + text.strip()
    tokens = enc.encode(composed)
    if len(tokens) <= max_tokens:
        return composed
    return enc.decode(tokens[:max_tokens])


def build_section_embedding_text(
    path: str,
    title: str | None,
    heading_path: list[str],
    text: str,
    *,
    section_kind: str,
    max_tokens: int,
) -> str:
    enc = get_encoder()
    composed = "\n".join(_build_preface(path, title, heading_path, section_kind)) + "\n\n" + text.strip()
    tokens = enc.encode(composed)
    if len(tokens) <= max_tokens:
        return composed
    return enc.decode(tokens[:max_tokens])


def _build_section_text(title: str | None, heading_path: list[str], body: str) -> str:
    context_lines = []
    if title:
        context_lines.append(f"Document: {title}")
    if heading_path:
        context_lines.append("Section: " + " > ".join(heading_path))
    context_lines.append(body.strip())
    return "\n\n".join(line for line in context_lines if line).strip()


def _consume_fenced_block(lines: list[str], start_index: int) -> tuple[str, int]:
    block_lines = [lines[start_index]]
    index = start_index + 1
    while index < len(lines):
        block_lines.append(lines[index])
        if lines[index].strip().startswith("```"):
            index += 1
            break
        index += 1
    return "\n".join(block_lines).strip(), index


def _consume_display_math_block(lines: list[str], start_index: int) -> tuple[str, int]:
    first_line = lines[start_index]
    if first_line.strip().count("$$") >= 2:
        return first_line.strip(), start_index + 1

    block_lines = [first_line]
    index = start_index + 1
    while index < len(lines):
        block_lines.append(lines[index])
        if "$$" in lines[index]:
            index += 1
            break
        index += 1
    return "\n".join(block_lines).strip(), index


def _extract_semantic_blocks(text: str) -> list[dict[str, str | int]]:
    blocks: list[dict[str, str | int]] = []
    paragraph_lines: list[str] = []
    lines = text.splitlines()

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        paragraph = "\n".join(paragraph_lines).strip()
        if paragraph:
            blocks.append({"kind": "paragraph", "text": paragraph})
        paragraph_lines = []

    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            index += 1
            continue

        heading_match = HEADING_PATTERN.match(line)
        if heading_match:
            flush_paragraph()
            blocks.append(
                {
                    "kind": "heading",
                    "text": _clean_heading_text(heading_match.group(2)),
                    "level": len(heading_match.group(1)),
                }
            )
            index += 1
            continue

        if stripped.startswith("```"):
            flush_paragraph()
            fenced_block, index = _consume_fenced_block(lines, index)
            blocks.append({"kind": "fence", "text": fenced_block})
            continue

        if TABLE_LINE_PATTERN.match(line):
            flush_paragraph()
            table_lines: list[str] = []
            while index < len(lines) and TABLE_LINE_PATTERN.match(lines[index]):
                table_lines.append(lines[index])
                index += 1
            blocks.append({"kind": "table", "text": "\n".join(table_lines).strip()})
            continue

        if DISPLAY_MATH_PATTERN.match(line):
            flush_paragraph()
            math_block, index = _consume_display_math_block(lines, index)
            blocks.append({"kind": "math", "text": math_block})
            continue

        paragraph_lines.append(line)
        index += 1

    flush_paragraph()
    return blocks


def _split_text_semantically(text: str, max_tokens: int) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return []
    if estimate_tokens(normalized) <= max_tokens:
        return [normalized]

    sentence_candidates = [
        sentence.strip()
        for sentence in re.split(r"(?<=[。！？；.!?;])\s+", normalized.replace("\n", " "))
        if sentence.strip()
    ]
    if len(sentence_candidates) <= 1:
        sentence_candidates = [part.strip() for part in normalized.splitlines() if part.strip()]
    if len(sentence_candidates) <= 1:
        return list(chunk_text(normalized, max_tokens=max_tokens, overlap=0))

    pieces: list[str] = []
    current: list[str] = []
    for sentence in sentence_candidates:
        if estimate_tokens(sentence) > max_tokens:
            if current:
                pieces.append(" ".join(current).strip())
                current = []
            pieces.extend(chunk_text(sentence, max_tokens=max_tokens, overlap=0))
            continue

        candidate = " ".join(current + [sentence]).strip()
        if current and estimate_tokens(candidate) > max_tokens:
            pieces.append(" ".join(current).strip())
            current = [sentence]
        else:
            current.append(sentence)

    if current:
        pieces.append(" ".join(current).strip())

    return [piece for piece in pieces if piece]


def split_structured_sections(
    path: str,
    title: str | None,
    text: str,
    *,
    max_tokens: int,
) -> list[dict]:
    blocks = _extract_semantic_blocks(text)
    sections: list[dict] = []
    heading_stack: list[str] = []
    current_blocks: list[str] = []
    current_heading_path: list[str] = []

    def flush() -> None:
        nonlocal current_blocks, current_heading_path
        if not current_blocks:
            return
        body = "\n\n".join(block for block in current_blocks if block.strip()).strip()
        if len(body) < 10:
            current_blocks = []
            return
        for piece in _split_text_semantically(body, max_tokens=max_tokens):
            section_text = _build_section_text(title, current_heading_path, piece)
            sections.append(
                {
                    "path": path,
                    "title": title,
                    "text": section_text,
                    "token_count": estimate_tokens(section_text),
                    "source_kind": "section",
                    "section_heading": " > ".join(current_heading_path) if current_heading_path else (title or path),
                    "section_kind": "semantic",
                }
            )
        current_blocks = []

    for block in blocks:
        kind = str(block.get("kind", "paragraph"))

        if kind == "heading":
            flush()
            level = int(block.get("level", 1))
            heading_text = str(block.get("text", "")).strip()
            heading_stack = heading_stack[: level - 1]
            if heading_text:
                heading_stack.append(heading_text)
            current_heading_path = heading_stack.copy()
            continue

        block_text = str(block.get("text", "")).strip()
        if not block_text:
            continue

        block_heading_path = heading_stack.copy() or current_heading_path
        candidate_blocks = current_blocks + [block_text]
        candidate_text = _build_section_text(
            title,
            current_heading_path or block_heading_path,
            "\n\n".join(candidate_blocks),
        )

        if current_blocks and estimate_tokens(candidate_text) > max_tokens:
            flush()

        if not current_blocks:
            current_heading_path = block_heading_path

        if estimate_tokens(block_text) > max_tokens:
            if current_blocks:
                flush()
            for piece in _split_text_semantically(block_text, max_tokens=max_tokens):
                current_blocks = [piece]
                current_heading_path = block_heading_path
                flush()
            continue

        current_blocks.append(block_text)

    flush()
    return sections


def _embed_texts(client: OpenAI, values: list[str], batch_size: int) -> list[list[float]]:
    vectors: list[list[float]] = []
    for offset in range(0, len(values), batch_size):
        vectors.extend(embed_batches(client, values[offset : offset + batch_size]))
    return vectors


def _write_index(vectors: list[list[float]], destination: Path) -> None:
    embeddings = np.array(vectors, dtype="float32")
    faiss.normalize_L2(embeddings)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    destination = destination.resolve()
    faiss.write_index(index, str(destination))


@retry_with_exponential_backoff(max_retries=3, initial_delay=1.0)
def embed_batches(client: OpenAI, chunks: List[str]) -> List[List[float]]:
    """
    Create embeddings for a batch of texts with retry logic.
    """
    resp = client.embeddings.create(model=EMBED_MODEL, input=chunks)
    return [item.embedding for item in resp.data]


def build_index(
    source: Path,
    index_path: Path,
    meta_path: Path,
    max_tokens: int = 500,
    overlap: int = 80,
    batch_size: int = 64,
    embed_max_tokens: int = DEFAULT_EMBED_MAX_TOKENS,
    section_index_path: Path | None = None,
    section_meta_path: Path | None = None,
    section_max_tokens: int = DEFAULT_SECTION_MAX_TOKENS,
    section_embed_max_tokens: int = DEFAULT_SECTION_EMBED_MAX_TOKENS,
):
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY not set. Add it to AI_Agent/.env or export it before running.")

    client = OpenAI()
    index_path = index_path.resolve()
    meta_path = meta_path.resolve()
    section_index_path = (section_index_path or derive_section_index_path(index_path)).resolve()
    section_meta_path = (section_meta_path or derive_section_meta_path(meta_path)).resolve()

    documents: list[dict] = []
    document_embeddings: list[str] = []
    sections: list[dict] = []
    section_embeddings: list[str] = []

    for md_path in iter_markdown_files(source):
        try:
            text = md_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"[warning] Encoding issue with {md_path}, trying latin-1")
            try:
                text = md_path.read_text(encoding="latin-1", errors="ignore")
            except Exception as exc:
                print(f"[error] Failed to read {md_path}: {exc}")
                continue
        except Exception as exc:
            print(f"[error] Failed to read {md_path}: {exc}")
            continue

        title, body = strip_front_matter(text)
        document_text = body.strip() or text.strip()

        is_valid, error_msg = validate_file_content(str(md_path), document_text)
        if not is_valid:
            print(f"[warning] {error_msg}")
            continue

        doc_path = _document_path(md_path, source)
        doc_title = title or md_path.stem
        document_record = {
            "path": doc_path,
            "title": doc_title,
            "text": document_text,
            "token_count": estimate_tokens(document_text),
            "source_kind": "document",
        }
        documents.append(document_record)
        document_embeddings.append(
            build_embedding_text(
                doc_path,
                document_text,
                doc_title,
                max_tokens=embed_max_tokens,
            )
        )

        for section_index, section in enumerate(
            split_structured_sections(
                doc_path,
                doc_title,
                document_text,
                max_tokens=section_max_tokens,
            ),
            start=1,
        ):
            section_record = {
                **section,
                "section_index": section_index,
            }
            sections.append(section_record)
            section_embeddings.append(
                build_section_embedding_text(
                    doc_path,
                    doc_title,
                    [item for item in section_record.get("section_heading", "").split(" > ") if item],
                    section_record["text"],
                    section_kind=str(section_record.get("section_kind", "section")),
                    max_tokens=section_embed_max_tokens,
                )
            )

    if not documents:
        raise RuntimeError("No documents were embedded. Check the source folder for Markdown files.")
    if not sections:
        raise RuntimeError("No semantic sections were created. Check the source folder for Markdown files.")

    document_vectors = _embed_texts(client, document_embeddings, batch_size)
    section_vectors = _embed_texts(client, section_embeddings, batch_size)

    _write_index(document_vectors, index_path)
    meta_path.write_bytes(pickle.dumps(documents))
    _write_index(section_vectors, section_index_path)
    section_meta_path.write_bytes(pickle.dumps(sections))

    print(
        f"[ok] Saved document index to {index_path} and metadata to {meta_path} "
        f"(documents={len(documents)})"
    )
    print(
        f"[ok] Saved semantic chunk index to {section_index_path} and metadata to {section_meta_path} "
        f"(sections={len(sections)})"
    )


def parse_args():
    ap = argparse.ArgumentParser(
        description="Build document-level and semantic-chunk FAISS indexes over the local solvency regulation Markdown corpus."
    )
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Directory with Markdown files")
    ap.add_argument("--index-path", type=Path, default=DEFAULT_INDEX, help="Output path for the document FAISS index")
    ap.add_argument("--meta-path", type=Path, default=DEFAULT_META, help="Output path for the document metadata pickle")
    ap.add_argument(
        "--section-index-path",
        type=Path,
        default=None,
        help="Output path for the semantic chunk FAISS index; defaults to a path derived from --index-path",
    )
    ap.add_argument(
        "--section-meta-path",
        type=Path,
        default=None,
        help="Output path for the semantic chunk metadata pickle; defaults to a path derived from --meta-path",
    )
    ap.add_argument("--max-tokens", type=int, default=500, help="Deprecated legacy chunk-size option; ignored in document mode")
    ap.add_argument("--overlap", type=int, default=80, help="Deprecated legacy overlap option; ignored in document mode")
    ap.add_argument(
        "--embed-max-tokens",
        type=int,
        default=DEFAULT_EMBED_MAX_TOKENS,
        help="Maximum tokens from each document used to build the document embedding",
    )
    ap.add_argument(
        "--section-max-tokens",
        type=int,
        default=DEFAULT_SECTION_MAX_TOKENS,
        help="Maximum tokens per semantic chunk before fallback splitting",
    )
    ap.add_argument(
        "--section-embed-max-tokens",
        type=int,
        default=DEFAULT_SECTION_EMBED_MAX_TOKENS,
        help="Maximum tokens from each semantic chunk used to build the chunk embedding",
    )
    ap.add_argument("--batch-size", type=int, default=64, help="Embedding batch size")
    return ap.parse_args()


def main():
    args = parse_args()
    build_index(
        source=args.source,
        index_path=args.index_path,
        meta_path=args.meta_path,
        max_tokens=args.max_tokens,
        overlap=args.overlap,
        batch_size=args.batch_size,
        embed_max_tokens=args.embed_max_tokens,
        section_index_path=args.section_index_path,
        section_meta_path=args.section_meta_path,
        section_max_tokens=args.section_max_tokens,
        section_embed_max_tokens=args.section_embed_max_tokens,
    )


if __name__ == "__main__":
    main()
