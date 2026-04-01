from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

from scripts.ask import answer_from_hits, get_document_snippets, get_index_artifact_paths, refresh_cache, run_query
from scripts.build_index import DEFAULT_INDEX, DEFAULT_META, DEFAULT_SOURCE, build_index
from scripts.project_config import KNOWLEDGE_BASE_NAME, load_project_env
from scripts.rich_markdown import build_github_blob_url, render_rich_markdown


PROJECT_ROOT = Path(__file__).resolve().parent
DOCS_DIR = PROJECT_ROOT.parent / "Knowledge_Base_MarkDown"
PREVIEW_CHAR_LIMIT = 3000
MAX_HISTORY_TURNS = 6
MAX_HISTORY_CHARS = 12000
GENERAL_MODEL = os.getenv("GENERAL_MODEL", os.getenv("MODEL", "gpt-4.1"))
REASONING_MODEL = os.getenv("REASONING_MODEL", "gpt-5.4-mini")

load_project_env(PROJECT_ROOT)


def has_real_openai_api_key() -> bool:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    return bool(key) and key != "sk-your-key"


def build_index_from_ui() -> None:
    build_index(
        source=DEFAULT_SOURCE,
        index_path=DEFAULT_INDEX,
        meta_path=DEFAULT_META,
    )
    refresh_cache()


def all_index_artifacts_ready() -> bool:
    return all(path.exists() for path in get_index_artifact_paths())


def load_markdown_files() -> list[Path]:
    if not DOCS_DIR.exists():
        return []
    return sorted(DOCS_DIR.rglob("*.md"))


def read_preview(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if len(text) <= PREVIEW_CHAR_LIMIT:
        return text
    return text[:PREVIEW_CHAR_LIMIT].rstrip() + "\n...\n[预览已截断]"


def build_history_context(history: list[dict], *, max_turns: int = MAX_HISTORY_TURNS, max_chars: int = MAX_HISTORY_CHARS) -> str:
    if not history:
        return ""

    rendered_turns = []
    for index, item in enumerate(history[-max_turns:], start=1):
        rendered_turns.append(
            "\n".join(
                [
                    f"Turn {index}",
                    f"User: {item['question']}",
                    f"Assistant: {item['answer']}",
                ]
            )
        )

    joined = "\n\n".join(rendered_turns)
    if len(joined) <= max_chars:
        return joined
    return joined[-max_chars:]


def append_history(question: str, answer: str, hits: list[dict]) -> None:
    st.session_state.history.append(
        {
            "question": question,
            "answer": answer,
            "hits": hits,
        }
    )
    st.session_state.scroll_to_latest = True


def build_citation_links(hits: list[dict]) -> dict[int, str]:
    return {
        index: build_github_blob_url(hit["path"])
        for index, hit in enumerate(hits, start=1)
        if hit.get("path")
    }


def get_selected_model() -> tuple[str, str]:
    mode = st.session_state.get("chat_model_mode", "一般")
    if mode == "推理":
        return mode, REASONING_MODEL
    return "一般", GENERAL_MODEL


def render_scroll_to_latest() -> None:
    components.html(
        """
        <script>
          const parentDoc = window.parent.document;
          const appRoot = parentDoc.querySelector('[data-testid="stAppViewContainer"]');
          const blocks = parentDoc.querySelectorAll('[data-testid="stVerticalBlock"]');
          if (blocks.length) {
            blocks[blocks.length - 1].scrollIntoView({ behavior: 'smooth', block: 'end' });
          } else if (appRoot) {
            appRoot.scrollTo({ top: appRoot.scrollHeight, behavior: 'smooth' });
          } else {
            window.parent.scrollTo({ top: parentDoc.body.scrollHeight, behavior: 'smooth' });
          }
        </script>
        """,
        height=0,
    )


def render_sidebar() -> tuple[Path | None, str | None]:
    md_files = load_markdown_files()
    relative_options = [str(path.relative_to(DOCS_DIR)) for path in md_files]

    with st.sidebar:
        st.header("知识库文件")
        st.metric("Markdown 文件数", len(relative_options))
        st.radio(
            "回答模式",
            ("一般", "推理"),
            key="chat_model_mode",
            horizontal=True,
        )
        _, selected_model = get_selected_model()
        st.caption(f"当前模型：`{selected_model}`")
        keyword = st.text_input("筛选文件", placeholder="输入关键词")
        filtered = relative_options
        if keyword:
            lowered = keyword.lower()
            filtered = [item for item in relative_options if lowered in item.lower()]

        if st.button("清空本次对话", use_container_width=True):
            st.session_state.history = []
            st.session_state.scroll_to_latest = False
            st.rerun()

        if not filtered:
            st.info("当前筛选条件下没有文件。")
            return None, None

        selected_label = st.selectbox("选择文件", filtered)
        selected_file = md_files[relative_options.index(selected_label)]

        with st.expander("文件预览", expanded=False):
            render_rich_markdown(read_preview(selected_file), min_height=96, max_height=520)

        return selected_file, selected_label


def render_history() -> None:
    if not st.session_state.history:
        st.info("还没有问题。先在下方输入一个问题。")
        return

    for item in st.session_state.history:
        with st.chat_message("user"):
            st.markdown(item["question"])

        with st.chat_message("assistant"):
            render_rich_markdown(
                item["answer"],
                min_height=120,
                max_height=None,
                citation_links=build_citation_links(item["hits"]),
            )
            with st.expander("引用与检索片段", expanded=False):
                for index, hit in enumerate(item["hits"], start=1):
                    heading = hit["path"]
                    if hit.get("source_kind") == "section":
                        heading += f" | {hit.get('section_heading', 'Section')}"
                    st.markdown(f"**[{index}]** [{heading}]({build_github_blob_url(hit['path'])})")
                    render_rich_markdown(hit["text"], min_height=88, max_height=720)


st.set_page_config(page_title=KNOWLEDGE_BASE_NAME, layout="wide")
st.title(KNOWLEDGE_BASE_NAME)
st.caption("基于本地监管 Markdown 语料的混合检索问答。整篇文档与结构化 section 会联合检索，并保留本次会话上下文。")

if "history" not in st.session_state:
    st.session_state.history = []
if "scroll_to_latest" not in st.session_state:
    st.session_state.scroll_to_latest = False

has_api_key = has_real_openai_api_key()
index_ready = all_index_artifacts_ready()
chat_disabled = not (has_api_key and index_ready)

if not has_api_key:
    st.warning("未检测到 `OPENAI_API_KEY`。可以在 `AI_Agent/.env` 中配置，或复用参考项目环境。")

if not index_ready:
    st.warning("索引文件尚未生成。请先运行 `python .\\scripts\\build_index.py --source ..\\Knowledge_Base_MarkDown`。")
    if has_api_key and st.button("立即构建索引", type="primary"):
        try:
            with st.spinner("正在构建文档索引与 section 索引，首次可能需要几分钟..."):
                build_index_from_ui()
            st.success("索引构建完成，正在刷新页面。")
            st.rerun()
        except Exception as exc:  # noqa: BLE001
            st.error(f"索引构建失败：{exc}")

selected_file, selected_label = render_sidebar()

if selected_file and selected_label:
    if st.button("只总结当前文件", disabled=chat_disabled):
        try:
            with st.spinner("正在总结当前文件..."):
                doc_path = f"Knowledge_Base_MarkDown/{selected_label.replace(os.sep, '/')}"
                hits = get_document_snippets(doc_path)
                if not hits:
                    raise FileNotFoundError(f"索引中未找到文件：{doc_path}")
                client = OpenAI()
                history_context = build_history_context(st.session_state.history)
                _, selected_model = get_selected_model()
                answer = answer_from_hits(
                    client,
                    f"请基于当前文件总结主要监管要求、适用范围、关键定义、计算或报告要求、例外情况与实践要点：{selected_label}",
                    hits,
                    language="zh",
                    history=history_context or None,
                    model=selected_model,
                )
                append_history(f"总结文件：{selected_label}", answer, hits)
        except Exception as exc:  # noqa: BLE001
            st.error(f"文件总结失败：{exc}")

render_history()

prompt = st.chat_input("请输入与偿付能力监管规则相关的问题", disabled=chat_disabled)

if prompt and not chat_disabled:
    try:
        with st.spinner("正在检索证据并生成回答..."):
            client = OpenAI()
            history_context = build_history_context(st.session_state.history)
            _, selected_model = get_selected_model()
            result = run_query(
                client,
                prompt,
                language="zh",
                mode=os.getenv("RAG_MODE", "agentic"),
                history=history_context or None,
                model=selected_model,
            )
            append_history(prompt, result["answer"], result["hits"])
        st.rerun()
    except Exception as exc:  # noqa: BLE001
        st.error(f"问答失败：{exc}")

if st.session_state.scroll_to_latest:
    render_scroll_to_latest()
    st.session_state.scroll_to_latest = False
