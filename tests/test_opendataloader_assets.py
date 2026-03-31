from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.convert_documents import repair_opendataloader_assets


def test_repair_opendataloader_assets_copies_images_for_multiple_references(tmp_path):
    output_dir = tmp_path / "converted"
    output_dir.mkdir()
    markdown_path = output_dir / "document.md"
    markdown_path.write_text(
        "![a](alpha_images/image1.png)\n![b](beta_images/image1.png)",
        encoding="utf-8",
    )

    images_dir = output_dir / "images"
    images_dir.mkdir()
    (images_dir / "image1.png").write_bytes(b"png")

    repaired_dirs = repair_opendataloader_assets(markdown_path, output_dir)

    assert repaired_dirs == ["alpha_images", "beta_images"]
    assert not images_dir.exists()
    assert (output_dir / "alpha_images" / "image1.png").exists()
    assert (output_dir / "beta_images" / "image1.png").exists()
