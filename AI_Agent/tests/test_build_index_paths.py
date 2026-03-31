from __future__ import annotations

import pickle
import sys
from pathlib import Path


AI_AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AI_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AI_AGENT_DIR))

from scripts import build_index as build_index_module


def _vectorize(text: str) -> list[float]:
    base = float(len(text))
    return [base, base + 1.0, base + 2.0, base + 3.0]


def test_build_index_uses_source_relative_paths_outside_repo(tmp_path, monkeypatch):
    class MockEncoder:
        def encode(self, text):
            return text.split()

        def decode(self, tokens):
            return " ".join(tokens)

    monkeypatch.setattr(build_index_module, "get_encoder", lambda: MockEncoder())

    repo_root = tmp_path / "repo"
    source_root = tmp_path / "external_corpus"
    (source_root / "nested").mkdir(parents=True)
    (source_root / "nested" / "outside.md").write_text(
        "Outside document with sufficient content for indexing.",
        encoding="utf-8",
    )

    index_path = repo_root / "AI_Agent" / "test.faiss"
    meta_path = repo_root / "AI_Agent" / "test.meta.pkl"
    index_path.parent.mkdir(parents=True)

    monkeypatch.setattr(build_index_module, "REPO_ROOT", repo_root)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setattr(
        build_index_module,
        "embed_batches",
        lambda client, chunks: [_vectorize(chunk) for chunk in chunks],
    )
    monkeypatch.setattr(build_index_module, "OpenAI", lambda: object())

    build_index_module.build_index(
        source=source_root,
        index_path=index_path,
        meta_path=meta_path,
        max_tokens=200,
        overlap=0,
        batch_size=2,
    )

    documents = pickle.loads(meta_path.read_bytes())
    assert documents[0]["path"] == "nested/outside.md"
