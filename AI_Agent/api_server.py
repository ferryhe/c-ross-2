from __future__ import annotations

import os
import sys
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field

PROJECT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_ROOT.parent
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
MAX_HISTORY_TURNS = 6
MAX_HISTORY_CHARS = 12000

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.project_config import KNOWLEDGE_BASE_NAME, load_project_env

load_project_env(PROJECT_ROOT)

from scripts.ask import (
    DEFAULT_LANGUAGE,
    DEFAULT_MODE,
    get_index_artifact_paths,
    run_query,
)

DEFAULT_GENERAL_MODEL = os.getenv("GENERAL_MODEL", "gpt-4.1")
DEFAULT_REASONING_MODEL = os.getenv("REASONING_MODEL", "gpt-5.4-mini")
DEFAULT_MODEL_MODE = os.getenv("DEFAULT_MODEL_MODE", "general")


class ChatMessage(BaseModel):
    role: str
    content: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    messages: list[ChatMessage]
    model_mode: Literal["general", "reasoning"] = Field(default=DEFAULT_MODEL_MODE, alias="modelMode")
    language: Literal["zh", "en"] = DEFAULT_LANGUAGE if DEFAULT_LANGUAGE in {"zh", "en"} else "zh"
    rag_mode: Literal["agentic", "standard"] = Field(
        default=DEFAULT_MODE if DEFAULT_MODE in {"agentic", "standard"} else "agentic",
        alias="ragMode",
    )


class SourceItem(BaseModel):
    index: int
    path: str
    url: str
    snippet: str
    source_kind: str | None = None
    section_heading: str | None = None


class ChatResponse(BaseModel):
    text: str
    sources: list[SourceItem]
    model: str
    model_mode: str
    language: str
    rag_mode: str


def _has_real_openai_api_key() -> bool:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    return bool(key) and key != "sk-your-key"


def _index_artifacts_ready() -> bool:
    return all(path.exists() for path in get_index_artifact_paths())


def _frontend_built() -> bool:
    return (FRONTEND_DIST / "index.html").exists()


def _extract_text_from_parts(parts: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for part in parts:
        part_type = str(part.get("type", ""))
        if part_type in {"text", "reasoning"}:
            text = str(part.get("text", "")).strip()
            if text:
                chunks.append(text)
        elif part_type == "tool-call":
            tool_name = str(part.get("toolName", "")).strip()
            if tool_name:
                chunks.append(f"[tool:{tool_name}]")
        elif part_type == "source":
            title = str(part.get("title", "")).strip()
            url = str(part.get("url", "")).strip()
            if title:
                chunks.append(title)
            elif url:
                chunks.append(url)
    return "\n".join(chunk for chunk in chunks if chunk).strip()


def _extract_question_and_history(messages: list[ChatMessage]) -> tuple[str, str]:
    filtered: list[tuple[str, str]] = []
    for message in messages:
        if message.role not in {"user", "assistant"}:
            continue
        text = _extract_text_from_parts(message.content)
        if text:
            filtered.append((message.role, text))

    if not filtered or filtered[-1][0] != "user":
        raise HTTPException(status_code=400, detail="The last message must be a non-empty user message.")

    question = filtered[-1][1]
    history_items = filtered[:-1]
    if not history_items:
        return question, ""

    recent_items = history_items[-(MAX_HISTORY_TURNS * 2) :]
    rendered_turns = [
        "\n".join(
            [
                f"Turn {index}",
                f"Role: {role}",
                f"Text: {text}",
            ]
        )
        for index, (role, text) in enumerate(recent_items, start=1)
    ]
    history = "\n\n".join(rendered_turns)
    if len(history) > MAX_HISTORY_CHARS:
        history = history[-MAX_HISTORY_CHARS:]
    return question, history


def _run_git_command(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""
    return result.stdout.strip()


@lru_cache(maxsize=1)
def _github_blob_base_url() -> str:
    remote = _run_git_command("config", "--get", "remote.origin.url")
    branch = _run_git_command("rev-parse", "--abbrev-ref", "HEAD") or "main"

    if remote.startswith("git@github.com:"):
        repo = remote.removeprefix("git@github.com:")
    elif remote.startswith("https://github.com/"):
        repo = remote.removeprefix("https://github.com/")
    else:
        repo = "ferryhe/c-ross-2"

    if repo.endswith(".git"):
        repo = repo[:-4]
    if branch == "HEAD":
        branch = "main"

    return f"https://github.com/{repo}/blob/{branch}"


def build_github_blob_url(path: str) -> str:
    normalized = path.replace("\\", "/").lstrip("./")
    encoded_path = quote(normalized, safe="/-_.~")
    return f"{_github_blob_base_url()}/{encoded_path}"


def _model_name_for_mode(model_mode: str) -> str:
    return DEFAULT_REASONING_MODEL if model_mode == "reasoning" else DEFAULT_GENERAL_MODEL


def _snippet_from_hit(hit: dict[str, Any], limit: int = 700) -> str:
    text = str(hit.get("text", "")).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _sources_from_hits(hits: list[dict[str, Any]]) -> list[SourceItem]:
    sources: list[SourceItem] = []
    for index, hit in enumerate(hits, start=1):
        path = str(hit.get("path", "")).strip()
        if not path:
            continue
        sources.append(
            SourceItem(
                index=index,
                path=path,
                url=build_github_blob_url(path),
                snippet=_snippet_from_hit(hit),
                source_kind=str(hit.get("source_kind")) if hit.get("source_kind") is not None else None,
                section_heading=str(hit.get("section_heading")) if hit.get("section_heading") is not None else None,
            )
        )
    return sources


app = FastAPI(title=KNOWLEDGE_BASE_NAME)


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {
        "status": "ok" if _has_real_openai_api_key() and _index_artifacts_ready() else "degraded",
        "has_api_key": _has_real_openai_api_key(),
        "index_ready": _index_artifacts_ready(),
        "frontend_built": _frontend_built(),
    }


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return {
        "knowledge_base_name": KNOWLEDGE_BASE_NAME,
        "default_model_mode": DEFAULT_MODEL_MODE,
        "models": {
            "general": DEFAULT_GENERAL_MODEL,
            "reasoning": DEFAULT_REASONING_MODEL,
        },
        "rag_mode": DEFAULT_MODE,
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    if not _has_real_openai_api_key():
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured.")
    if not _index_artifacts_ready():
        raise HTTPException(status_code=503, detail="Knowledge base index is not ready.")

    question, history = _extract_question_and_history(request.messages)
    client = OpenAI()
    model_name = _model_name_for_mode(request.model_mode)

    result = run_query(
        client,
        question,
        language=request.language,
        mode=request.rag_mode,
        history=history or None,
        model=model_name,
    )
    sources = _sources_from_hits(result.get("hits", []))
    return ChatResponse(
        text=str(result.get("answer", "")),
        sources=sources,
        model=model_name,
        model_mode=request.model_mode,
        language=request.language,
        rag_mode=request.rag_mode,
    )


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend(full_path: str) -> Any:
    if not _frontend_built():
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Frontend assets are not built yet.",
                "expected": str(FRONTEND_DIST / "index.html"),
            },
        )

    target = (FRONTEND_DIST / full_path).resolve()
    if full_path and target.is_file() and FRONTEND_DIST in target.parents:
        return FileResponse(target)

    return FileResponse(FRONTEND_DIST / "index.html")
