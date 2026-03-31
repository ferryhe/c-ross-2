# c-ross-2

`c-ross-2` 是一个面向中国偿二代监管规则的本地问答系统。

项目把 PDF、MHTML、Excel 等监管材料转换为结构化 Markdown，整理成知识库，再通过向量检索和 RAG 问答能力，提供针对中国偿二代规则、附件和通知文件的问答、检索与预览。

## 项目定位

- 面向中国偿二代监管语料的知识整理与问答
- 支持多格式监管文件转 Markdown
- 支持本地向量索引与问答
- 支持 Streamlit Web 界面、表格显示和公式渲染

## 目录结构

```text
.
├─ source_regulation/         # 原始监管文件
├─ Knowledge_Base_MarkDown/   # 标准化后的 Markdown 知识库
├─ AI_Agent/                  # 问答系统、索引构建、Streamlit UI
├─ scripts/                   # 文档转换、清洗、manifest 构建脚本
├─ tests/                     # 转换与清洗测试
├─ plans/                     # 项目规划文档
└─ .devcontainer/             # GitHub Codespaces 配置
```

## 核心能力

- 文档转换：将偿二代监管 PDF、MHTML、Excel 转为 Markdown
- 内容规范化：生成统一 front matter、附件目录和 `manifest.json`
- 监管问答：基于知识库进行检索增强问答
- 富文本展示：在 Web 界面中展示表格与公式
- 本地开发：支持 Windows 本地运行与 GitHub Codespaces

## 快速开始

### 1. 安装依赖

```powershell
cd AI_Agent
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

### 2. 构建索引

```powershell
python .\scripts\build_index.py --source ..\Knowledge_Base_MarkDown
```

### 3. 启动问答界面

```powershell
streamlit run .\streamlit_app.py
```

## Codespaces

仓库已包含 `.devcontainer`，可以直接在 GitHub Codespaces 中启动。

- Codespace Web IDE：打开对应 codespace 的 `github.dev` 地址
- Streamlit 服务：通过转发端口 `8501` 访问
- 访问地址格式通常为：
  `https://CODESPACENAME-8501.app.github.dev`
- 如果第一次进入 Codespace 还没有索引，请先在 `AI_Agent/.env` 配置有效的 `OPENAI_API_KEY`，然后在页面里点击“立即构建索引”，或者执行：

```bash
cd /workspaces/c-ross-2/AI_Agent || cd /workspaces/cross2/AI_Agent
python ./scripts/build_index.py --source ../Knowledge_Base_MarkDown
```

- 当前架构是 `Streamlit + Python + OpenAI` 的服务端应用，不适合直接部署成 GitHub Pages。短期试用建议直接公开 Codespaces 的 `8501` 端口。

## 环境变量

主要环境变量位于 `AI_Agent/.env.example`：

- `OPENAI_API_KEY`
- `MODEL`
- `EMBEDDING_MODEL`
- `RAG_MODE`
- `OUTPUT_LANGUAGE`
- `TOP_K`
- `SIMILARITY_THRESHOLD`

## 测试

```powershell
python -m pytest tests AI_Agent/tests
```

当前项目默认面向中文监管问答场景，重点覆盖中国偿二代规则、附件和相关监管通知。
