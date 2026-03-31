from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR.parent))

from scripts.common import KNOWLEDGE_BASE_ROOT, posix_rel


def build_manifest(knowledge_base_root: Path = KNOWLEDGE_BASE_ROOT, manifest_path: Path | None = None) -> list[dict[str, str]]:
    manifest_path = manifest_path or (knowledge_base_root / "manifest.json")
    entries: list[dict[str, str]] = []
    for path in sorted(knowledge_base_root.rglob("*.md")):
        if path.name.startswith("_"):
            continue
        text = path.read_text(encoding="utf-8")
        metadata = _parse_front_matter(text)
        entries.append(
            {
                "path": posix_rel(path.relative_to(knowledge_base_root)),
                "title": metadata.get("title", path.stem),
                "category": metadata.get("category", ""),
                "source_type": metadata.get("source_type", ""),
                "source_file": metadata.get("source_file", ""),
                "source_url": metadata.get("source_url", ""),
                "publish_date": metadata.get("publish_date", ""),
                "converted_engine": metadata.get("converted_engine", ""),
            }
        )

    manifest_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    return entries


def _parse_front_matter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    lines = text.splitlines()
    metadata: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"')
    return metadata


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build manifest.json for the final Markdown corpus.")
    parser.add_argument("--knowledge-base-root", type=Path, default=KNOWLEDGE_BASE_ROOT)
    parser.add_argument("--manifest-path", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    entries = build_manifest(args.knowledge_base_root, args.manifest_path)
    print(f"[ok] manifest entries={len(entries)} path={args.manifest_path or args.knowledge_base_root / 'manifest.json'}")


if __name__ == "__main__":
    main()
