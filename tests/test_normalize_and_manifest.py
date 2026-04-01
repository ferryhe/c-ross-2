from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_manifest import build_manifest
from scripts.normalize_markdown import normalize_corpus, normalize_math_entities


def test_normalize_corpus_writes_front_matter_and_assets(tmp_path):
    raw_root = tmp_path / "work" / "converted_raw"
    output_root = tmp_path / "Knowledge_Base_MarkDown"

    raw_file = raw_root / "偿二代二期-规则" / "监管规则第2号.md"
    raw_file.parent.mkdir(parents=True)
    raw_file.write_text("# 正文\n\n![图](监管规则第2号_images/image1.png)", encoding="utf-8")

    asset_dir = raw_root / "偿二代二期-规则" / "监管规则第2号_images"
    asset_dir.mkdir()
    (asset_dir / "image1.png").write_bytes(b"png")

    meta = {
        "title": "监管规则第2号",
        "category": "rules",
        "source_type": ".pdf",
        "source_file": "偿二代二期-规则/监管规则第2号.pdf",
        "source_url": "",
        "publish_date": "2021-12-30",
        "converted_engine": "opendataloader",
        "converted_at": "2026-03-31T11:00:00",
        "asset_dirs": ["监管规则第2号_images"],
    }
    raw_file.with_suffix(".meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    outputs = normalize_corpus(raw_root, output_root)

    target = output_root / "rules" / "监管规则第2号.md"
    assert len(outputs) == 1
    assert target.exists()
    assert (output_root / "rules" / "监管规则第2号_images" / "image1.png").exists()

    text = target.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "title: 监管规则第2号" in text
    assert "# 正文" in text


def test_normalize_corpus_strips_bom_and_dedupes_title_heading(tmp_path):
    raw_root = tmp_path / "work" / "converted_raw"
    output_root = tmp_path / "Knowledge_Base_MarkDown"

    raw_file = raw_root / "偿二代二期-规则" / "监管规则第10号.md"
    raw_file.parent.mkdir(parents=True)
    raw_file.write_text(
        "\ufeff# 监管规则第10号\n\n# 监管规则第10号\n\n## 第一章 总则\n\n正文",
        encoding="utf-8",
    )
    raw_file.with_suffix(".meta.json").write_text(
        json.dumps({"title": "监管规则第10号", "category": "rules"}, ensure_ascii=False),
        encoding="utf-8",
    )

    normalize_corpus(raw_root, output_root)

    text = (output_root / "rules" / "监管规则第10号.md").read_text(encoding="utf-8")
    assert not text.startswith("\ufeff")
    assert text.startswith("---\n")
    assert text.count("# 监管规则第10号") == 1


def test_normalize_corpus_dedupes_plain_title_after_h1(tmp_path):
    raw_root = tmp_path / "work" / "converted_raw"
    output_root = tmp_path / "Knowledge_Base_MarkDown"

    raw_file = raw_root / "偿二代二期-规则" / "监管规则第1号.md"
    raw_file.parent.mkdir(parents=True)
    raw_file.write_text(
        "# 监管规则第1号\n\n监管规则第1号\n\n第一章 总则\n\n正文",
        encoding="utf-8",
    )
    raw_file.with_suffix(".meta.json").write_text(
        json.dumps({"title": "监管规则第1号", "category": "rules"}, ensure_ascii=False),
        encoding="utf-8",
    )

    normalize_corpus(raw_root, output_root)

    text = (output_root / "rules" / "监管规则第1号.md").read_text(encoding="utf-8")
    assert text.count("# 监管规则第1号") == 1
    assert "\n\n监管规则第1号\n\n" not in text


def test_build_manifest_collects_normalized_files(tmp_path):
    kb_root = tmp_path / "Knowledge_Base_MarkDown"
    kb_root.mkdir()
    doc = kb_root / "rules" / "监管规则第2号.md"
    doc.parent.mkdir()
    doc.write_text(
        "---\n"
        "title: 监管规则第2号\n"
        "category: rules\n"
        "source_type: .pdf\n"
        "source_file: 偿二代二期-规则/监管规则第2号.pdf\n"
        "source_url: \n"
        "publish_date: 2021-12-30\n"
        "converted_engine: opendataloader\n"
        "converted_at: 2026-03-31T11:00:00\n"
        "---\n\n"
        "# 正文\n",
        encoding="utf-8",
    )

    manifest_path = kb_root / "manifest.json"
    entries = build_manifest(kb_root, manifest_path)

    assert manifest_path.exists()
    assert len(entries) == 1
    assert entries[0]["title"] == "监管规则第2号"
    assert entries[0]["path"] == "rules/监管规则第2号.md"
