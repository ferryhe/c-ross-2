# c-ross-2

`c-ross-2` 是一个面向中国偿二代监管规则的问答系统。

项目将 `PDF`、`MHTML`、`Excel` 等监管材料转换为结构化 Markdown，整理为知识库后，再通过向量检索和 RAG 问答能力，提供针对规则、附件和通知的检索、预览与问答。

## 当前功能

- 监管文档转换为 Markdown 知识库
- 文档级索引与语义分段索引
- 面向规则、附件、通知的研究型问答
- `一般 / 推理` 两种模型档位切换
- 表格、公式、数字引用超链接展示
- 本次会话记忆与本地恢复
- 保留独立 chatbot，并新增专业法规回答引擎 API

仓库当前已包含：

- 预生成索引文件
- 预构建前端静态产物

因此部署时不需要现场重建索引，也不需要现场重新构建前端。

## 目录结构

```text
.
├─ source_regulation/         # 原始监管文件
├─ Knowledge_Base_MarkDown/   # 标准化后的 Markdown 知识库
├─ AI_Agent/                  # 问答系统、索引构建、前后端实现
├─ scripts/                   # 文档转换、清洗、manifest 构建脚本
├─ tests/                     # 转换与清洗测试
└─ .devcontainer/             # Codespaces 配置
```

## 快速开始

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

只有在以下场景才需要额外执行：

- 修改前端代码：进入 `frontend/` 后执行 `npm install`、`npm run build`
- 更新知识库内容：执行 `python .\scripts\build_index.py --source ..\Knowledge_Base_MarkDown`

## Ubuntu 部署

如果要部署到 Ubuntu 服务器，尤其是 `Docker + Caddy` 环境，直接看：

- [AI_Agent/README.md](./AI_Agent/README.md)

里面已经包含：

- 运行依赖
- 启动流程
- 索引准备方式
- Docker/Caddy 场景下的部署步骤

## 测试

```powershell
python -m pytest tests AI_Agent/tests
cd AI_Agent\frontend
npm test
```
