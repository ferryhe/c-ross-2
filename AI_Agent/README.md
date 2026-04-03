# AI_Agent

`AI_Agent/` 是这个仓库的数据层验证 consumer，不是仓库的唯一主产物。

它的职责是消费根目录下的：

- `Knowledge_Base_MarkDown/`
- `Knowledge_Base_MarkDown/ready_data/`
- 向量索引文件

并提供两种验证形态：

- 独立运行的 `chatbot`：`/api/chat`
- 面向 skill / workflow / AI agent 的 `professional engine`：`/api/engine/*`

## 这个目录负责什么

- 构建与加载向量索引
- 基于 `ready_data + 向量检索` 做法规回答
- 提供 FastAPI 服务
- 提供前端聊天界面
- 作为真实问答与回归验证层

## 双模式接口

### `chatbot mode`

- 接口：`/api/chat`
- 用途：保留当前独立 chatbot 体验，验证完整回答链路

### `professional engine mode`

- 接口：
  - `/api/engine/config`
  - `/api/engine/search/titles`
  - `/api/engine/search/summaries`
  - `/api/engine/plan`
  - `/api/engine/chat`
- 用途：让 skill 化 agent 先定位、再缩圈、再拿证据回答

## 依赖的输入

服务启动前通常需要以下内容存在：

- `../Knowledge_Base_MarkDown/`
- `../Knowledge_Base_MarkDown/ready_data/`
- `knowledge_base.faiss`
- `knowledge_base.meta.pkl`
- `knowledge_base.sections.faiss`
- `knowledge_base.meta.sections.pkl`
- `.env`

## 本地启动

### 1. 安装 Python 依赖

```powershell
cd AI_Agent
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

### 2. 启动服务

```powershell
uvicorn api_server:app --host 0.0.0.0 --port 8501
```

### 3. 可选：前端开发

只有在修改 `frontend/src/` 时才需要：

```powershell
cd frontend
npm install
npm run dev
```

如果要重新生成静态前端：

```powershell
cd frontend
npm run build
```

## 当知识库更新时

建议按下面顺序刷新：

1. 重建 `ready_data`

```powershell
python .\scripts\build_ready_data.py --source ..\Knowledge_Base_MarkDown --output-root ..\Knowledge_Base_MarkDown\ready_data
```

2. 重建向量索引

```powershell
python .\scripts\build_index.py --source ..\Knowledge_Base_MarkDown
```

3. 重启服务并做真实问题烟测

## 关键环境变量

| 变量 | 说明 | 默认值 |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI API key | 必填 |
| `GENERAL_MODEL` | 一般模式模型 | `gpt-4.1` |
| `REASONING_MODEL` | 推理模式模型 | `gpt-5.4-mini` |
| `DEFAULT_MODEL_MODE` | 默认模型档位 | `general` |
| `EMBEDDING_MODEL` | 向量模型 | `text-embedding-3-large` |
| `RAG_MODE` | `agentic` 或 `standard` | `agentic` |
| `OUTPUT_LANGUAGE` | 输出语言 | `zh` |
| `INDEX_PATH` | 文档索引路径 | `knowledge_base.faiss` |
| `META_PATH` | 文档元数据路径 | `knowledge_base.meta.pkl` |
| `SECTION_INDEX_PATH` | 语义段索引路径 | `knowledge_base.sections.faiss` |
| `SECTION_META_PATH` | 语义段元数据路径 | `knowledge_base.meta.sections.pkl` |

## 相关文档

- [专业回答引擎 API 说明](../docs/ai-agent/专业回答引擎API说明.md)
- [专业回答引擎演进记录](../docs/ai-agent/专业回答引擎演进记录.md)
- [运行验证记录](../docs/ai-agent/运行验证记录.md)
- [基于 ready_data 的 agent 模拟测试](../docs/ai-agent/基于ready_data的agent模拟测试.md)
- [真实问答验证记录](../docs/ai-agent/真实问答验证记录-gpt-5.4-mini.md)
- [数据层 Schema 设计](../docs/project/数据层Schema设计.md)

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
