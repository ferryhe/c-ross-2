from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "source_regulation"
WORK_ROOT = PROJECT_ROOT / "work"
MHTML_HTML_ROOT = WORK_ROOT / "mhtml_html"
RAW_MARKDOWN_ROOT = WORK_ROOT / "converted_raw"
REPORT_ROOT = WORK_ROOT / "conversion_reports"
KNOWLEDGE_BASE_ROOT = PROJECT_ROOT / "Knowledge_Base_MarkDown"
LOCAL_AI_AGENT_ENV = PROJECT_ROOT / "AI_Agent" / ".env"


def _prefer_existing(*paths: Path) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def _path_from_env(env_name: str, default: Path) -> Path:
    raw_value = os.getenv(env_name)
    if not raw_value:
        return default
    return Path(raw_value).expanduser()


def _default_reference_ai_agent_dir() -> Path:
    return _prefer_existing(
        PROJECT_ROOT.parent / "IAA_AI_Knowledge_Base" / "AI_Agent",
        Path(r"C:\Projects\IAA_AI_Knowledge_Base\AI_Agent"),
    )


def _default_doc_to_md_root() -> Path:
    return _prefer_existing(
        PROJECT_ROOT.parent / "doc_to_md",
        Path(r"C:\Projects\doc_to_md"),
    )


def _default_doc_to_md_python(root: Path) -> Path:
    return _prefer_existing(
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "bin" / "python",
        Path(sys.executable),
    )


REFERENCE_AI_AGENT_DIR = _path_from_env("REFERENCE_AI_AGENT_DIR", _default_reference_ai_agent_dir())
REFERENCE_AI_AGENT_ENV = _path_from_env("REFERENCE_AI_AGENT_ENV", REFERENCE_AI_AGENT_DIR / ".env")
DOC_TO_MD_ROOT = _path_from_env("DOC_TO_MD_ROOT", _default_doc_to_md_root())
DOC_TO_MD_PYTHON = _path_from_env("DOC_TO_MD_PYTHON", _default_doc_to_md_python(DOC_TO_MD_ROOT))


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def posix_rel(path: Path) -> str:
    return path.as_posix()


def categorize_source_path(relative_path: Path) -> str:
    parts = relative_path.parts
    if parts and parts[0] == "偿二代二期-规则":
        return "rules"
    if parts and parts[0] == "偿二代二期-附件":
        return "attachments"
    return "notices"


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_env_values(*paths: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for path in paths:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not key:
                continue
            value = _strip_inline_comment(value.strip())
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]
            values[key] = value
    return values


def merged_env(*paths: Path) -> dict[str, str]:
    env = os.environ.copy()
    for key, value in load_env_values(*paths).items():
        env.setdefault(key, value)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def _strip_inline_comment(value: str) -> str:
    quote_char: str | None = None
    result: list[str] = []
    for index, char in enumerate(value):
        if char in {'"', "'"}:
            if quote_char == char:
                quote_char = None
            elif quote_char is None:
                quote_char = char
        if char == "#" and quote_char is None:
            if index == 0 or value[index - 1].isspace():
                break
        result.append(char)
    return "".join(result).strip()
