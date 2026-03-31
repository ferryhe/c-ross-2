from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from openai import OpenAI

from scripts.ask import INDEX_PATH, META_PATH, answer_from_hits, get_document_snippets, refresh_cache, run_query
from scripts.build_index import DEFAULT_INDEX, DEFAULT_META, DEFAULT_SOURCE, build_index
from scripts.project_config import KNOWLEDGE_BASE_NAME, load_project_env
from scripts.rich_markdown import build_github_blob_url, render_rich_markdown


PROJECT_ROOT = Path(__file__).resolve().parent
DOCS_DIR = PROJECT_ROOT.parent / "Knowledge_Base_MarkDown"
PREVIEW_CHAR_LIMIT = 3000

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

st.set_page_config(page_title=KNOWLEDGE_BASE_NAME, layout="wide")
st.title(KNOWLEDGE_BASE_NAME)
st.caption("基于本地监管 Markdown 语料的检索问答。回答只使用索引内容，并附带文件引用。")

has_api_key = has_real_openai_api_key()
index_ready = INDEX_PATH.exists() and META_PATH.exists()
chat_disabled = not (has_api_key and index_ready)

if not has_api_key:
    st.warning("未检测到 `OPENAI_API_KEY`。可以在 `AI_Agent/.env` 中配置，或复用参考项目环境。")
if not index_ready:
    st.warning("索引文件尚未生成。请先运行 `python .\\scripts\\build_index.py --source ..\\Knowledge_Base_MarkDown`。")
    if has_api_key:
        if st.button("立即构建索引", type="primary"):
            try:
                with st.spinner("正在构建索引，首次可能需要几分钟..."):
                    build_index_from_ui()
                st.success("索引构建完成，正在刷新页面。")
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(f"索引构建失败：{exc}")
    else:
        st.info("请先在 `AI_Agent/.env` 配置有效的 `OPENAI_API_KEY`，然后再构建索引。")

if "history" not in st.session_state:
    st.session_state.history = []


def load_markdown_files() -> list[Path]:
    if not DOCS_DIR.exists():
        return []
    return sorted(DOCS_DIR.rglob("*.md"))


def read_preview(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if len(text) <= PREVIEW_CHAR_LIMIT:
        return text
    return text[:PREVIEW_CHAR_LIMIT].rstrip() + "\n...\n[预览已截断]"


def render_sidebar() -> tuple[Path | None, str | None]:
    md_files = load_markdown_files()
    relative_options = [str(path.relative_to(DOCS_DIR)) for path in md_files]

    with st.sidebar:
        st.header("知识库文件")
        st.metric("Markdown 文件数", len(relative_options))
        keyword = st.text_input("筛选文件", placeholder="输入关键字")
        filtered = relative_options
        if keyword:
            lowered = keyword.lower()
            filtered = [item for item in relative_options if lowered in item.lower()]

        if not filtered:
            st.info("当前筛选条件下没有文件。")
            return None, None

        selected_label = st.selectbox("选择文件", filtered)
        selected_file = md_files[relative_options.index(selected_label)]

        with st.expander("文件预览", expanded=False):
            render_rich_markdown(read_preview(selected_file), height=420)

        return selected_file, selected_label


selected_file, selected_label = render_sidebar()
prompt = st.chat_input("请输入与偿付能力监管规则相关的问题", disabled=chat_disabled)

if prompt and not chat_disabled:
    try:
        with st.spinner("检索并生成答案中..."):
            client = OpenAI()
            result = run_query(client, prompt, language="zh", mode=os.getenv("RAG_MODE", "agentic"))
            st.session_state.history.append({"question": prompt, "answer": result["answer"], "hits": result["hits"]})
    except Exception as exc:  # noqa: BLE001
        st.error(f"问答失败：{exc}")

if selected_file and selected_label and st.button("只总结当前文件", disabled=chat_disabled):
    try:
        with st.spinner("总结当前文件中..."):
            doc_path = f"Knowledge_Base_MarkDown/{selected_label.replace(os.sep, '/')}"
            hits = get_document_snippets(doc_path)
            if not hits:
                raise FileNotFoundError(f"索引中未找到文件：{doc_path}")
            client = OpenAI()
            answer = answer_from_hits(
                client,
                f"请基于当前文件总结主要监管要求、适用范围和关键披露/报送要点：{selected_label}",
                hits,
                language="zh",
            )
            st.session_state.history.append({"question": f"总结文件：{selected_label}", "answer": answer, "hits": hits})
    except Exception as exc:  # noqa: BLE001
        st.error(f"文件总结失败：{exc}")

st.subheader("对话记录")
if not st.session_state.history:
    st.info("还没有问题。先在上方输入一个问题。")
else:
    for item in st.session_state.history:
        st.markdown(f"**你：** {item['question']}")
        st.markdown("**AI：**")
        render_rich_markdown(item["answer"], height=420)
        with st.expander("检索片段", expanded=False):
            for index, hit in enumerate(item["hits"], start=1):
                st.markdown(f"**[{index}]** [{hit['path']}]({build_github_blob_url(hit['path'])})")
                render_rich_markdown(hit["text"], height=320)
