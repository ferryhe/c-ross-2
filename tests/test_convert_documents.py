from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.convert_documents import repair_opendataloader_assets


def test_repair_opendataloader_assets_renames_images_folder(tmp_path):
    output_dir = tmp_path / "converted"
    output_dir.mkdir()
    markdown_path = output_dir / "监管规则.md"
    markdown_path.write_text("![img](监管规则_images/image1.png)", encoding="utf-8")

    images_dir = output_dir / "images"
    images_dir.mkdir()
    (images_dir / "image1.png").write_bytes(b"png")

    renamed_dirs = repair_opendataloader_assets(markdown_path, output_dir)

    assert renamed_dirs == ["监管规则_images"]
    assert not images_dir.exists()
    assert (output_dir / "监管规则_images" / "image1.png").exists()


def test_repair_opendataloader_assets_is_noop_without_images(tmp_path):
    output_dir = tmp_path / "converted"
    output_dir.mkdir()
    markdown_path = output_dir / "监管规则.md"
    markdown_path.write_text("纯文本输出", encoding="utf-8")

    renamed_dirs = repair_opendataloader_assets(markdown_path, output_dir)

    assert renamed_dirs == []
