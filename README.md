# c-ross-2

`c-ross-2` 的核心目标不是做一个单独的聊天前台，而是把监管材料加工成：

`Markdown -> chatbot-ready / AI-agent-ready 数据层 -> 可验证 RAG / consumer`

当前仓库围绕中国偿二代监管规则，提供三类主产物：

- 原始监管文件到标准化 Markdown 的转换与清洗
- 基于 Markdown 生成的 `ready_data` 数据层
- 一个可独立运行的 `chatbot / professional engine` 参考 consumer，用来验证数据层和 RAG 层是否可用

## 仓库主产物

### 1. 标准化 Markdown 知识库

- 位置：`Knowledge_Base_MarkDown/`
- 内容：`rules / notices / attachments`

### 2. ready-data 数据层

- 位置：`Knowledge_Base_MarkDown/ready_data/`
- 当前产物：
  - `doc_catalog.jsonl`
  - `title_aliases.jsonl`
  - `doc_summaries.jsonl`
  - `sections_structured.jsonl`
  - `formula_cards.jsonl`
  - `relations_graph.json`
  - `ready_data_manifest.json`

### 3. 验证 consumer

- 位置：`AI_Agent/`
- 作用：
  - 提供独立运行的 `chatbot`
  - 提供 `/api/engine/*` 专业引擎接口
  - 验证 `ready_data + 向量索引 + 回答链路` 是否真实可用

## 目录结构

```text
.
├─ source_regulation/         # 原始监管文件
├─ scripts/                   # 文档转换、清洗、manifest 构建脚本
├─ Knowledge_Base_MarkDown/   # 标准化 Markdown 主库
│  └─ ready_data/             # chatbot-ready / AI-agent-ready 数据层
├─ AI_Agent/                  # 参考 consumer、索引构建、API 与前端
├─ docs/                      # 设计、演进、验证记录
├─ skills/                    # 供 AI agent 使用的仓库内 skill
└─ tests/                     # 转换与清洗测试
```

## 常用工作流

### 1. 只更新数据层

当 `Knowledge_Base_MarkDown/` 内容变化，希望重建 agent/chatbot 可消费的数据层时：

```powershell
python AI_Agent\scripts\build_ready_data.py --source Knowledge_Base_MarkDown --output-root Knowledge_Base_MarkDown\ready_data
```

### 2. 更新向量索引

当需要让参考 consumer 使用最新 Markdown 语料时：

```powershell
python AI_Agent\scripts\build_index.py --source Knowledge_Base_MarkDown
```

### 3. 启动验证 chatbot / professional engine

详细说明见 [AI_Agent/README.md](./AI_Agent/README.md)。

最短流程：

```powershell
cd AI_Agent
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn api_server:app --host 0.0.0.0 --port 8501
```

当前仓库已包含：

- 预生成 `ready_data`
- 预生成向量索引
- 预构建前端静态产物

因此部署现有版本时，不需要现场重新构建所有产物。

## 文档

- [文档索引](./docs/README.md)
- [数据层 Schema 设计](./docs/project/数据层Schema设计.md)
- [数据层下一阶段实施计划](./docs/project/数据层下一阶段实施计划.md)
- [详细对比说明](./docs/project/详细对比说明.md)
- [AI_Agent 服务说明](./AI_Agent/README.md)

## 测试

```powershell
python -m pytest tests AI_Agent\tests
```

如果修改了前端：

```powershell
cd AI_Agent\frontend
npm test
npm run build
```
