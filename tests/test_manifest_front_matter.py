from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_manifest import build_manifest


def test_build_manifest_handles_bom_and_json_quoted_front_matter(tmp_path):
    kb_root = tmp_path / "Knowledge_Base_MarkDown"
    kb_root.mkdir()
    doc = kb_root / "rules" / "quoted.md"
    doc.parent.mkdir()
    doc.write_text(
        "\ufeff---\n"
        'title: "Title with \\"quotes\\" and \\\\slashes"\n'
        "category: rules\n"
        "---\n\n"
        "# Body\n",
        encoding="utf-8",
    )

    entries = build_manifest(kb_root)

    assert entries == [
        {
            "path": "rules/quoted.md",
            "title": 'Title with "quotes" and \\slashes',
            "category": "rules",
            "source_type": "",
            "source_file": "",
            "source_url": "",
            "publish_date": "",
            "converted_engine": "",
        }
    ]
