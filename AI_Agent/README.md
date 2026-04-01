# 中国偿二代问答系统

这个目录提供中国偿二代监管知识库的本地问答系统。

当前实现分成两层：

- Python 后端：复用现有 `scripts/ask.py` 与索引文件，提供 `/api/chat` 问答接口
- React 前端：基于 `assistant-ui LocalRuntime` 的聊天界面，负责对话交互、消息渲染、模型模式切换和本地会话恢复

## 目录

```text
AI_Agent/
  api_server.py
  frontend/
    src/
    package.json
  scripts/
    ask.py
    build_index.py
    agentic_rag.py
  tests/
    test_api_server.py
    test_rag_pipeline.py
  requirements.txt
  .env.example
```

## 快速开始

1. 安装 Python 依赖

```powershell
cd AI_Agent
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

2. 安装前端依赖

```powershell
cd frontend
npm install
cd ..
```

3. 构建索引

```powershell
python .\scripts\build_index.py --source ..\Knowledge_Base_MarkDown
```

4. 构建前端

```powershell
cd frontend
npm run build
cd ..
```

5. 启动服务

```powershell
uvicorn api_server:app --host 0.0.0.0 --port 8501
```

启动后访问：

- 本地：`http://127.0.0.1:8501`
- Codespaces：使用对应 `8501` 端口转发地址

## 开发模式

后端：

```powershell
uvicorn api_server:app --reload --host 0.0.0.0 --port 8501
```

前端：

```powershell
cd frontend
npm run dev
```

如果前端单独开发，需要把请求转到同机 Python 服务。

## 模型模式

聊天界面支持两种模式：

- `一般`：默认使用 `gpt-4.1`
- `推理`：默认使用 `gpt-5.4-mini`

可通过 `.env` 调整：

- `GENERAL_MODEL`
- `REASONING_MODEL`
- `DEFAULT_MODEL_MODE`

## 环境变量

| 变量 | 说明 | 默认值 |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API key | 必填 |
| `MODEL` | 默认问答模型 | `gpt-4.1` |
| `GENERAL_MODEL` | “一般”模式模型 | `gpt-4.1` |
| `REASONING_MODEL` | “推理”模式模型 | `gpt-5.4-mini` |
| `DEFAULT_MODEL_MODE` | 默认模型档位 | `general` |
| `EMBEDDING_MODEL` | 向量模型 | `text-embedding-3-large` |
| `RAG_MODE` | `agentic` 或 `standard` | `agentic` |
| `OUTPUT_LANGUAGE` | 输出语言 | `zh` |
| `SOURCE_DIR` | 知识库目录 | `../Knowledge_Base_MarkDown` |
| `INDEX_PATH` | 文档索引路径 | `knowledge_base.faiss` |
| `META_PATH` | 文档元数据路径 | `knowledge_base.meta.pkl` |
| `SECTION_INDEX_PATH` | 语义段索引路径 | `knowledge_base.sections.faiss` |
| `SECTION_META_PATH` | 语义段元数据路径 | `knowledge_base.meta.sections.pkl` |

## 测试

Python：

```powershell
python -m pytest tests
```

前端：

```powershell
cd frontend
npm test
npm run build
```

## 当前交付特点

- 不再依赖 Streamlit 的 iframe 富渲染
- 回答正文支持 Markdown、表格、公式和数字引用超链接
- 当前标签页内对话有连续记忆
- 页面刷新后会从浏览器本地恢复最近一次会话
