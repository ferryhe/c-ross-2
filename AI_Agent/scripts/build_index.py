import argparse
import os
import pickle
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


DEFAULT_SOURCE = _resolve_path(os.getenv("SOURCE_DIR"), REPO_ROOT / "Knowledge_Base_MarkDown")
DEFAULT_INDEX = _resolve_path(os.getenv("INDEX_PATH"), PROJECT_ROOT / "knowledge_base.faiss")
DEFAULT_META = _resolve_path(os.getenv("META_PATH"), PROJECT_ROOT / "knowledge_base.meta.pkl")
EMBED_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")

# Lazy-load tiktoken encoder to avoid network calls during import
_enc = None

def get_encoder():
    """Get tiktoken encoder, loading it lazily."""
    global _enc
    if _enc is None:
        _enc = tiktoken.get_encoding("cl100k_base")
    return _enc


def iter_markdown_files(source: Path) -> Iterable[Path]:
    """Iterate over markdown files with validation."""
    if not source.exists():
        raise FileNotFoundError(f"Source directory not found: {source}")
    for path in sorted(source.rglob("*.md")):
        if path.is_file():
            # Skip empty files
            if path.stat().st_size == 0:
                print(f"[warning] Skipping empty file: {path}")
                continue
            yield path.resolve()


def chunk_text(text: str, max_tokens: int = 500, overlap: int = 80) -> Iterable[str]:
    """
    Chunk text with semantic boundary awareness.
    
    Strategy:
    - Uses token-based chunking with configurable overlap to prevent semantic breaks
    - 500 token chunks with 80 token overlap provides good balance between
      context preservation and retrieval granularity
    - Overlap helps maintain semantic continuity across chunk boundaries
    """
    enc = get_encoder()
    tokens = enc.encode(text)
    if not tokens:
        return []
    step = max(1, max_tokens - overlap)
    for i in range(0, len(tokens), step):
        chunk = enc.decode(tokens[i : i + max_tokens])
        # Only yield non-empty chunks
        if chunk.strip():
            yield chunk


@retry_with_exponential_backoff(max_retries=3, initial_delay=1.0)
def embed_batches(client: OpenAI, chunks: List[str]) -> List[List[float]]:
    """
    Create embeddings for a batch of text chunks with retry logic.
    
    Includes exponential backoff for handling rate limits and transient errors.
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
):
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY not set. Add it to AI_Agent/.env or export it before running.")

    client = OpenAI()

    documents = []
    vectors: List[List[float]] = []
    buffer: List[str] = []

    for md_path in iter_markdown_files(source):
        try:
            text = md_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"[warning] Encoding issue with {md_path}, trying latin-1")
            try:
                text = md_path.read_text(encoding="latin-1", errors="ignore")
            except Exception as e:
                print(f"[error] Failed to read {md_path}: {e}")
                continue
        except Exception as e:
            print(f"[error] Failed to read {md_path}: {e}")
            continue

        # Validate file content
        is_valid, error_msg = validate_file_content(str(md_path), text)
        if not is_valid:
            print(f"[warning] {error_msg}")
            continue

        for chunk in chunk_text(text, max_tokens=max_tokens, overlap=overlap):
            rel_path = md_path.relative_to(REPO_ROOT)
            documents.append({"path": str(rel_path), "text": chunk})
            buffer.append(chunk)

            if len(buffer) == batch_size:
                vectors.extend(embed_batches(client, buffer))
                buffer = []

    if buffer:
        vectors.extend(embed_batches(client, buffer))

    if not vectors:
        raise RuntimeError("No text chunks were embedded. Check the source folder for Markdown files.")

    embeddings = np.array(vectors, dtype="float32")
    faiss.normalize_L2(embeddings)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    index_path = index_path.resolve()
    faiss.write_index(index, str(index_path))

    meta_path = meta_path.resolve()
    meta_path.write_bytes(pickle.dumps(documents))
    print(f"[ok] Saved index to {index_path} and metadata to {meta_path} (chunks={len(documents)})")


def parse_args():
    ap = argparse.ArgumentParser(description="Build a FAISS index over the local solvency regulation Markdown corpus.")
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Directory with Markdown files")
    ap.add_argument("--index-path", type=Path, default=DEFAULT_INDEX, help="Output path for FAISS index")
    ap.add_argument("--meta-path", type=Path, default=DEFAULT_META, help="Output path for metadata pickle")
    ap.add_argument("--max-tokens", type=int, default=500, help="Chunk size in tokens")
    ap.add_argument("--overlap", type=int, default=80, help="Token overlap between consecutive chunks")
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
    )


if __name__ == "__main__":
    main()
