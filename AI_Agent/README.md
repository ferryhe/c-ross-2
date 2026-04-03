# 中国偿二代问答系统

这个目录提供问答服务层，负责：

- 构建知识库索引
- 执行文档级与语义分段检索
- 生成带引用的研究型回答
- 提供聊天界面
- 对外暴露 API 服务

## 架构

当前实现分为三层：

1. 检索与问答

- [`scripts/build_index.py`](./scripts/build_index.py)
- [`scripts/ask.py`](./scripts/ask.py)

这层负责：

- 文档级索引
- 语义分段索引
- 问题路由
- 引用编号
- 模型档位切换

2. API 服务

- [`api_server.py`](./api_server.py)

这层负责：

- `/healthz`
- `/api/config`
- `/api/chat`
- `/api/engine/config`
- `/api/engine/search/titles`
- `/api/engine/search/summaries`
- `/api/engine/plan`
- `/api/engine/chat`
- 托管前端静态文件

3. 前端界面

- [`frontend/src/App.tsx`](./frontend/src/App.tsx)
- [`frontend/src/markdown.tsx`](./frontend/src/markdown.tsx)

这层负责：

- 聊天界面
- 模型档位切换
- 表格渲染
- 公式渲染
- `[1]`、`[2]` 数字引用超链接
- 本次会话记忆和本地恢复

## 功能

- 知识库问答
- 法规专业回答引擎 API
- 文档级 + 语义分段混合检索
- 研究型回答风格
- `一般 = gpt-4.1`
- `推理 = gpt-5.4-mini`
- 回答中的数字引用可直接点击
- 前端对公式增加了 LaTeX 保护和常见 OCR 公式清洗

当前服务保留两种使用形态：

- `chatbot mode`
  - 继续使用 `/api/chat`
  - 适合当前前端和独立运行的聊天界面
- `professional engine mode`
  - 使用 `/api/engine/*`
  - 适合技能化 agent、外部工作流和更可控的法规问答编排

补充文档：

- [专业回答引擎 API 说明](./专业回答引擎API说明.md)
- [专业回答引擎演进记录](./专业回答引擎演进记录.md)
- [运行验证记录](./运行验证记录.md)

当前仓库已包含两类部署产物：

- 预构建前端：`frontend/dist/`
- 预生成索引：
  - `knowledge_base.faiss`
  - `knowledge_base.meta.pkl`
  - `knowledge_base.sections.faiss`
  - `knowledge_base.meta.sections.pkl`

因此在部署环境中可以直接运行服务，不需要现场构建前端，也不需要现场重建索引。

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
    query_enhancements.py
    project_config.py
  tests/
    test_api_server.py
    test_rag_pipeline.py
    test_prompt_consistency.py
  requirements.txt
  .env.example
```

## 本地启动

### 1. 安装 Python 依赖

```powershell
cd AI_Agent
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

### 2. 安装前端依赖

```powershell
cd frontend
npm install
cd ..
```

### 3. 构建索引

```powershell
python .\scripts\build_index.py --source ..\Knowledge_Base_MarkDown
```

### 4. 构建前端

```powershell
cd frontend
npm run build
cd ..
```

### 5. 启动服务

```powershell
uvicorn api_server:app --host 0.0.0.0 --port 8501
```

启动后访问：

- 本地：`http://127.0.0.1:8501`
- 服务器：通过反向代理域名访问

如果只是部署当前仓库版本，可直接跳到“启动服务”这一步。
只有在以下情况下才需要重新执行前端构建或索引构建：

- 修改了 `frontend/src/` 下的前端代码
- 更新了 `Knowledge_Base_MarkDown/` 中的知识库内容

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

## 模型模式

聊天界面支持两种模式：

- `一般`
  默认使用 `gpt-4.1`
- `推理`
  默认使用 `gpt-5.4-mini`

相关环境变量：

- `GENERAL_MODEL`
- `REASONING_MODEL`
- `DEFAULT_MODEL_MODE`

## 环境变量

主要变量如下：

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

## Ubuntu 部署指南

这里按 `Ubuntu + Docker + Caddy` 的常见部署方式说明流程，只讲主线，不绑定某一套具体环境细节。

### 适用场景

- Ubuntu 服务器
- 服务器上已有 `Docker`
- 服务器上已有 `Caddy`
- 问答服务作为一个独立 AI Agent 服务运行

### 推荐部署方式

建议拆成两个部分：

- `cross2-ai-agent`
  运行本项目服务
- `caddy`
  负责域名、HTTPS 和反向代理

### 部署流程

1. 准备代码与知识库

- 拉取仓库代码
- 确认 `Knowledge_Base_MarkDown/` 是要上线的版本
- 确认索引文件是随部署一起带上，还是在服务器现建

2. 准备环境变量

至少准备：

- `OPENAI_API_KEY`
- `GENERAL_MODEL`
- `REASONING_MODEL`
- `DEFAULT_MODEL_MODE`

建议使用：

- `.env`
- Docker secret
- 平台 secret

不要把真实 key 提交到仓库。

3. 准备运行依赖

如果不是完全容器化，Ubuntu 至少需要：

- Python 3.11+
- `venv`
- `pip`
- `libgomp1`

如果你只运行当前仓库自带产物，运行时不需要 Node。
只有在服务器现场重建前端时，才需要 Node 22。

如果走 Docker，建议把这些依赖放进镜像，不依赖宿主机环境。

4. 构建前端

前端需要生成 `frontend/dist/`，因为最终由 FastAPI 直接托管这份静态产物。

通常有两种方式：

- 在本地或 CI 先构建，再部署
- 在 Docker build 阶段构建

当前仓库已经包含预构建的 `frontend/dist/`，所以部署当前版本时可以跳过这一步。

5. 准备索引

推荐上线前准备好以下文件：

- `knowledge_base.faiss`
- `knowledge_base.meta.pkl`
- `knowledge_base.sections.faiss`
- `knowledge_base.meta.sections.pkl`

这样生产环境启动时不需要重新跑 embeddings。

当前仓库已经包含预生成索引，所以部署当前版本时可以直接使用这些文件，避免在服务器上重新消耗 embedding token。

如果知识库会持续更新，可以把“重建索引”单独做成一个任务，而不是放到服务启动流程里。

6. 启动应用服务

应用进程就是：

```bash
uvicorn api_server:app --host 0.0.0.0 --port 8501
```

启动前确认：

- `frontend/dist` 存在
- 索引文件存在
- `.env` 或环境变量存在

7. 配置 Caddy 反代

建议让 `Caddy` 负责：

- 域名绑定
- HTTPS 证书
- 反向代理到应用服务的 `8501`

应用本身只负责 HTTP 服务，不需要自己处理 TLS。

### 上线前检查

部署完成后，至少确认以下项目：

- `/healthz` 返回 `ok`
- `/api/config` 能返回模型配置
- 页面可以打开
- 一条真实问题能返回答案
- `[1]` 这类引用可以点击
- 表格和公式可以显示

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
