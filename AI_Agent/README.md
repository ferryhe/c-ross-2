# 偿付能力监管知识库 AI Agent

这个目录提供一个本地 RAG chatbot，面向 `../Knowledge_Base_MarkDown/` 下的监管 Markdown 语料。

支持两种问答模式：

- `agentic`：规划子查询、分轮检索、反思后综合作答
- `standard`：单轮检索后直接作答

## 目录

```text
AI_Agent/
  scripts/
    build_index.py
    ask.py
    agentic_rag.py
    query_enhancements.py
    utils.py
    project_config.py
  tests/
    test_smoke.py
    test_rag_pipeline.py
  streamlit_app.py
  requirements.txt
  .env.example
```

## 快速开始

1. 准备依赖

```powershell
cd AI_Agent
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

2. 构建索引

```powershell
python .\scripts\build_index.py --source ..\Knowledge_Base_MarkDown
```

3. 命令行问答

```powershell
python .\scripts\ask.py --language zh "核心偿付能力监管规则有哪些"
python .\scripts\ask.py --mode standard --language zh "压力测试要求主要在哪些文件里"
python .\scripts\ask.py --mode agentic --show-trace --language zh "偿付能力报告、压力测试和信息披露之间是什么关系"
```

4. 启动本地 UI

```powershell
streamlit run .\streamlit_app.py
```

5. 在 Codespaces 中启动

- 第一次进入如果页面提示没有索引，先在 `AI_Agent/.env` 配置有效的 `OPENAI_API_KEY`
- 然后直接在页面点击“立即构建索引”，或者手动执行：

```bash
python ./scripts/build_index.py --source ../Knowledge_Base_MarkDown
```

## 环境变量

| 变量 | 说明 | 默认值 |
|---|---|---|
| `OPENAI_API_KEY` | Embedding 与问答模型使用的 API key | 必填 |
| `MODEL` | 问答模型 | `gpt-4.1` |
| `GENERAL_MODEL` | “一般”档位模型 | `gpt-4.1` |
| `REASONING_MODEL` | “推理”档位模型 | `gpt-5.4-mini` |
| `EMBEDDING_MODEL` | 向量模型 | `text-embedding-3-large` |
| `RAG_MODE` | `agentic` 或 `standard` | `agentic` |
| `OUTPUT_LANGUAGE` | 回答语言 | `zh` |
| `TOP_K` | 检索条数 | `8` |
| `SIMILARITY_THRESHOLD` | 最低相似度阈值 | `0.0` |
| `SOURCE_DIR` | Markdown 语料目录 | `../Knowledge_Base_MarkDown` |
| `INDEX_PATH` | 向量索引文件 | `knowledge_base.faiss` |
| `META_PATH` | 元数据文件 | `knowledge_base.meta.pkl` |

说明：

- 本项目会优先读取 `AI_Agent/.env`
- 如果本地未配置，也会尝试复用 `C:\Projects\IAA_AI_Knowledge_Base\AI_Agent\.env`

## 测试

```powershell
python -m pytest tests/test_smoke.py tests/test_rag_pipeline.py
```

测试会 monkeypatch OpenAI 调用，所以不依赖真实网络请求。
