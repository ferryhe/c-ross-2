from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR.parent))

from scripts.common import (
    DOC_TO_MD_PYTHON,
    LOCAL_AI_AGENT_ENV,
    MHTML_HTML_ROOT,
    RAW_MARKDOWN_ROOT,
    REFERENCE_AI_AGENT_ENV,
    REPORT_ROOT,
    SOURCE_ROOT,
    categorize_source_path,
    ensure_parent,
    merged_env,
    now_iso,
    posix_rel,
)


@dataclass(slots=True)
class ConversionJob:
    input_path: Path
    original_source_path: Path
    relative_source_path: Path
    source_type: str
    preferred_engines: list[str]
    title: str = ""
    source_url: str = ""
    publish_date: str = ""
    content_source: str = ""


@dataclass(slots=True)
class ConversionResult:
    source_file: str
    source_type: str
    category: str
    status: str
    engine: str | None
    output_markdown: str | None = None
    asset_dirs: list[str] | None = None
    error: str | None = None


def repair_opendataloader_assets(markdown_path: Path, output_dir: Path) -> list[str]:
    markdown = markdown_path.read_text(encoding="utf-8")
    referenced_dirs = sorted(set(re.findall(r"\(([^)]+?_images)/[^)]+\)", markdown)))
    images_dir = output_dir / "images"
    if not referenced_dirs or not images_dir.is_dir():
        return []

    if len(referenced_dirs) == 1:
        target_dir = output_dir / referenced_dirs[0]
        if target_dir.exists():
            return []
        images_dir.rename(target_dir)
        return [referenced_dirs[0]]

    renamed_dirs: list[str] = []
    for directory_name in referenced_dirs:
        target_dir = output_dir / directory_name
        if target_dir.exists():
            continue
        shutil.copytree(images_dir, target_dir)
        renamed_dirs.append(directory_name)
    shutil.rmtree(images_dir)
    return renamed_dirs


def collect_jobs(source_root: Path = SOURCE_ROOT, mhtml_html_root: Path = MHTML_HTML_ROOT) -> list[ConversionJob]:
    jobs: list[ConversionJob] = []

    for path in sorted(source_root.rglob("*.pdf")):
        relative = path.relative_to(source_root)
        jobs.append(
            ConversionJob(
                input_path=path,
                original_source_path=path,
                relative_source_path=relative,
                source_type=".pdf",
                preferred_engines=["opendataloader", "mistral"],
                title=path.stem,
            )
        )

    for path in sorted(source_root.rglob("*.xlsx")):
        relative = path.relative_to(source_root)
        jobs.append(
            ConversionJob(
                input_path=path,
                original_source_path=path,
                relative_source_path=relative,
                source_type=".xlsx",
                preferred_engines=["local"],
                title=path.stem,
            )
        )

    for html_path in sorted(mhtml_html_root.rglob("*.html")):
        meta_path = html_path.with_suffix(".meta.json")
        metadata = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        original_relative = Path(metadata.get("original_relative_path", html_path.relative_to(mhtml_html_root)))
        original_source = source_root / original_relative
        jobs.append(
            ConversionJob(
                input_path=html_path,
                original_source_path=original_source,
                relative_source_path=original_relative,
                source_type=".mhtml",
                preferred_engines=["html_local"],
                title=metadata.get("title", original_relative.stem),
                source_url=metadata.get("source_url", ""),
                publish_date=metadata.get("publish_date", ""),
                content_source=metadata.get("content_source", ""),
            )
        )

    return jobs


def convert_all(
    source_root: Path = SOURCE_ROOT,
    mhtml_html_root: Path = MHTML_HTML_ROOT,
    output_root: Path = RAW_MARKDOWN_ROOT,
    report_root: Path = REPORT_ROOT,
) -> list[ConversionResult]:
    results: list[ConversionResult] = []
    for job in collect_jobs(source_root, mhtml_html_root):
        results.append(convert_job(job, output_root))

    report_root.mkdir(parents=True, exist_ok=True)
    report_path = report_root / "conversion_report.json"
    report_path.write_text(
        json.dumps([asdict(item) for item in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return results


def convert_job(job: ConversionJob, output_root: Path = RAW_MARKDOWN_ROOT) -> ConversionResult:
    env = merged_env(LOCAL_AI_AGENT_ENV, REFERENCE_AI_AGENT_ENV)
    category = categorize_source_path(job.relative_source_path)
    target_md = output_root / job.relative_source_path.with_suffix(".md")
    ensure_parent(target_md)

    last_error: str | None = None
    for engine in job.preferred_engines:
        try:
            with tempfile.TemporaryDirectory(prefix="doc_to_md_stage_") as temp_root_str:
                temp_root = Path(temp_root_str)
                stage_input = temp_root / "input"
                stage_output = temp_root / "output"
                stage_input.mkdir(parents=True, exist_ok=True)
                stage_output.mkdir(parents=True, exist_ok=True)

                staged_source = stage_input / job.input_path.name
                shutil.copy2(job.input_path, staged_source)

                _run_doc_to_md(stage_input, stage_output, engine, env)
                stage_markdown = _find_single_markdown(stage_output)
                asset_dirs = []
                if engine == "opendataloader":
                    asset_dirs = repair_opendataloader_assets(stage_markdown, stage_output)
                copied_asset_dirs = _copy_outputs(stage_markdown, stage_output, target_md)
                if copied_asset_dirs:
                    asset_dirs = copied_asset_dirs

                metadata = {
                    "title": job.title or job.relative_source_path.stem,
                    "category": category,
                    "source_type": job.source_type,
                    "source_file": posix_rel(job.relative_source_path),
                    "source_url": job.source_url,
                    "publish_date": job.publish_date,
                    "content_source": job.content_source,
                    "converted_engine": engine,
                    "converted_at": now_iso(),
                    "asset_dirs": copied_asset_dirs,
                }
                target_md.with_suffix(".meta.json").write_text(
                    json.dumps(metadata, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                return ConversionResult(
                    source_file=posix_rel(job.relative_source_path),
                    source_type=job.source_type,
                    category=category,
                    status="converted",
                    engine=engine,
                    output_markdown=posix_rel(target_md.relative_to(output_root)),
                    asset_dirs=copied_asset_dirs,
                )
        except Exception as exc:  # noqa: BLE001
            last_error = f"{engine}: {exc}"

    return ConversionResult(
        source_file=posix_rel(job.relative_source_path),
        source_type=job.source_type,
        category=category,
        status="failed",
        engine=None,
        error=last_error,
    )


def _run_doc_to_md(stage_input: Path, stage_output: Path, engine: str, env: dict[str, str]) -> None:
    python_executable = DOC_TO_MD_PYTHON if DOC_TO_MD_PYTHON.exists() else Path(shutil.which("python") or "python")
    command = [
        str(python_executable),
        "-m",
        "doc_to_md.cli",
        "convert",
        "--input-path",
        str(stage_input),
        "--output-path",
        str(stage_output),
        "--engine",
        engine,
    ]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", env=env, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "doc_to_md conversion failed").strip())


def _find_single_markdown(output_dir: Path) -> Path:
    markdown_files = sorted(output_dir.rglob("*.md"))
    if len(markdown_files) != 1:
        raise RuntimeError(f"Expected exactly one Markdown output, found {len(markdown_files)} in {output_dir}")
    return markdown_files[0]


def _copy_outputs(stage_markdown: Path, stage_output: Path, target_markdown: Path) -> list[str]:
    shutil.copy2(stage_markdown, target_markdown)
    copied_dirs: list[str] = []
    for child in sorted(stage_output.iterdir()):
        if child == stage_markdown:
            continue
        target_child = target_markdown.parent / child.name
        if child.is_dir():
            if target_child.exists():
                shutil.rmtree(target_child)
            shutil.copytree(child, target_child)
            copied_dirs.append(child.name)
        elif child.is_file() and child.suffix.lower() != ".md":
            shutil.copy2(child, target_child)
    return copied_dirs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert regulation source files to raw Markdown.")
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    parser.add_argument("--mhtml-html-root", type=Path, default=MHTML_HTML_ROOT)
    parser.add_argument("--output-root", type=Path, default=RAW_MARKDOWN_ROOT)
    parser.add_argument("--report-root", type=Path, default=REPORT_ROOT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = convert_all(args.source_root, args.mhtml_html_root, args.output_root, args.report_root)
    converted = sum(1 for item in results if item.status == "converted")
    failed = sum(1 for item in results if item.status == "failed")
    print(f"[ok] converted={converted} failed={failed} report={args.report_root / 'conversion_report.json'}")


if __name__ == "__main__":
    main()
