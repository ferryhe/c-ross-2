from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

AI_AGENT_DIR = Path(__file__).resolve().parents[1]
if str(AI_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AI_AGENT_DIR))

from scripts import ask as ask_module
from scripts import build_index as build_index_module


def _vectorize(text: str) -> list[float]:
    """Deterministic toy embedding so smoke tests stay offline."""
    base = float(len(text))
    return [base, base + 1.0, base + 2.0, base + 3.0]


def test_build_and_retrieve(tmp_path, monkeypatch):
    # Mock tiktoken encoder
    class MockEncoder:
        def encode(self, text):
            return text.split()
        def decode(self, tokens):
            return " ".join(tokens)
    
    monkeypatch.setattr(build_index_module, "get_encoder", lambda: MockEncoder())
    
    repo_root = tmp_path / "repo"
    corpus_dir = repo_root / "Knowledge_Base_MarkDown"
    corpus_dir.mkdir(parents=True)
    doc_path = corpus_dir / "smoke_doc.md"
    doc_text = "Short governance overview for smoke testing."
    doc_path.write_text(doc_text, encoding="utf-8")

    index_path = repo_root / "AI_Agent" / "smoke.faiss"
    meta_path = repo_root / "AI_Agent" / "smoke.meta.pkl"
    index_path.parent.mkdir(parents=True)

    monkeypatch.setattr(build_index_module, "REPO_ROOT", repo_root, raising=False)
    monkeypatch.setattr(ask_module, "REPO_ROOT", repo_root, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")  # Mock API key
    monkeypatch.setattr(
        build_index_module,
        "embed_batches",
        lambda client, chunks: [_vectorize(chunk) for chunk in chunks],
        raising=False,
    )
    monkeypatch.setattr(build_index_module, "OpenAI", lambda: object(), raising=False)

    build_index_module.build_index(
        source=corpus_dir,
        index_path=index_path,
        meta_path=meta_path,
        max_tokens=200,
        overlap=0,
        batch_size=2,
    )

    monkeypatch.setattr(ask_module, "INDEX_PATH", index_path, raising=False)
    monkeypatch.setattr(ask_module, "META_PATH", meta_path, raising=False)
    monkeypatch.setattr(ask_module, "_INDEX_CACHE", None, raising=False)
    monkeypatch.setattr(ask_module, "_DOCS_CACHE", None, raising=False)

    class DummyEmbeddings:
        def create(self, model, input):
            data = [SimpleNamespace(embedding=_vectorize(item)) for item in input]
            return SimpleNamespace(data=data)

    dummy_client = SimpleNamespace(embeddings=DummyEmbeddings())
    
    # Patch the _create_embedding function
    monkeypatch.setattr(ask_module, "_create_embedding", lambda client, text: _vectorize(text))

    hits = ask_module.retrieve(dummy_client, doc_text, k=1)
    assert hits, "Expected at least one retrieved chunk"
    assert hits[0]["path"].endswith("smoke_doc.md")
    assert "governance overview" in hits[0]["text"]
