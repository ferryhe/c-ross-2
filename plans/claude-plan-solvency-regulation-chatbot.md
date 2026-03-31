# Claude Plan: 偿付能力监管资料 Markdown 与 AI Chatbot

## 元信息

- 目标：把 `source_regulation/` 里的监管资料批量转成 Markdown，并基于这些 Markdown 搭一个与 `C:\Projects\IAA_AI_Knowledge_Base` 同结构、同使用方式的 AI chatbot
- 计划模式：ECC `blueprint` 风格规划，先出可执行计划，不直接进入实现
- 执行方式：当前仓库走 direct mode，不依赖 PR 流程
- 参考实现：`C:\Projects\IAA_AI_Knowledge_Base`
- 转换工具：`C:\Projects\doc_to_md`

## 当前基线

当前仓库几乎还是空仓，只有原始资料目录：

- `source_regulation/`

资料格式分布已经确认：

- `26` 个 `.pdf`
- `7` 个 `.xlsx`
- `6` 个 `.mhtml`

关键约束已经确认：

- PDF 适合优先使用 `doc_to_md` 的 `opendataloader`
- XLSX 可以走 `doc_to_md` 的本地表格提取能力
- `doc_to_md` 明确支持 `.html/.htm`，但没有把 `.mhtml` 作为原生输入格式，因此 `.mhtml` 必须先做预处理
- `IAA_AI_Knowledge_Base` 的最小可复用骨架是：`Knowledge_Base_MarkDown/` + `AI_Agent/`

## 目标交付

本项目第一阶段建议只交付最小可用版本：

1. 保留 `source_regulation/` 作为只读原始资料区
2. 生成可索引的 `Knowledge_Base_MarkDown/`
3. 搭建可本地运行的 `AI_Agent/`
4. 支持本地索引构建、命令行问答、Streamlit 页面问答
5. 保留后续扩展位给 Open WebUI、自动目录、更多清洗规则

不放入第一阶段的内容：

- 外部联网检索原始来源补全
- 复杂部署脚本
- Hosted 版本上线
- 过度定制 UI

## 建议目录结构

```text
cross2/
|-- source_regulation/                 # 原始监管资料，只读
|-- Knowledge_Base_MarkDown/           # 最终知识库语料
|   |-- notices/                       # 通知、实施说明、过渡期说明等
|   |-- rules/                         # 偿二代规则正文
|   |-- attachments/                   # 附件、样表、附录
|   `-- manifest.json                  # 语料清单与元数据
|-- AI_Agent/                          # 复用 IAA 结构的聊天机器人
|   |-- scripts/
|   |-- tests/
|   |-- streamlit_app.py
|   |-- requirements.txt
|   |-- .env.example
|   |-- knowledge_base.faiss
|   `-- knowledge_base.meta.pkl
|-- scripts/                           # 本项目自己的加工流水线
|   |-- extract_mhtml_to_html.py
|   |-- convert_documents.py
|   |-- normalize_markdown.py
|   `-- build_manifest.py
|-- work/                              # 中间产物，不入库或按需清理
|   |-- mhtml_html/
|   |-- converted_raw/
|   `-- conversion_reports/
`-- plans/
    `-- claude-plan-solvency-regulation-chatbot.md
```

## 架构决策

### 决策 1：保留 `IAA_AI_Knowledge_Base` 的两层结构

原因：

- 你的目标不是重新发明一个 RAG 系统，而是尽快做出一个“同类可用版本”
- `IAA_AI_Knowledge_Base` 已经验证了 `Markdown corpus -> FAISS index -> ask.py/Streamlit` 这条链路
- 这样后续迁移 prompt、测试、UI 都最省力

结论：

- 顶层继续使用 `Knowledge_Base_MarkDown/`
- 聊天机器人目录继续使用 `AI_Agent/`

### 决策 2：按格式分流转换，而不是试图一把梭

原因：

- PDF、XLSX、MHTML 的最佳处理方式不同
- `.mhtml` 不在 `doc_to_md` 的原生输入清单中
- 一次性跑统一入口会让失败原因难以定位

结论：

- PDF: `opendataloader`
- XLSX: `local` + office 依赖
- MHTML: 先抽出 HTML，再走 `html_local`

### 决策 4：PDF 失败回退优先使用 `mistral`

原因：

- 你已经明确接受把个别失败样本回退到 `mistral AI`
- `doc_to_md` 已经内置 `mistral` 引擎
- API key 已存在于参考项目环境中，不需要另行设计第二套密钥管理方案

结论：

- 默认 PDF 路径仍然是 `opendataloader`
- 仅对失败或质量明显异常的 PDF 启用 `mistral` 回退
- 第一阶段直接复用现有项目里的 `MISTRAL_API_KEY` 配置

### 决策 3：先做本地最小可用 chatbot

原因：

- 你说的是“和 IAA 一样的一个 AI chatbot 就行”
- IAA 的最小可用面其实就是 CLI + Streamlit
- 先把语料质量和索引流程跑通，比先做部署更重要

结论：

- 第一阶段保留 `ask.py` 和 `streamlit_app.py`
- `responses_pipeline.py` 作为第二阶段可选项

## 实施路径

### Phase 1：搭骨架

目标：先把仓库结构与复用边界定下来。

工作项：

- 创建 `Knowledge_Base_MarkDown/`、`AI_Agent/`、`scripts/`、`work/`、`plans/`
- 从 `C:\Projects\IAA_AI_Knowledge_Base\AI_Agent` 复制最小必需文件
- 初始只保留 chatbot 所需脚本，不复制无关的原始来源检索脚本

建议复制的最小文件集：

- `AI_Agent/scripts/build_index.py`
- `AI_Agent/scripts/ask.py`
- `AI_Agent/scripts/agentic_rag.py`
- `AI_Agent/scripts/query_enhancements.py`
- `AI_Agent/scripts/utils.py`
- `AI_Agent/tests/test_smoke.py`
- `AI_Agent/tests/test_rag_pipeline.py`
- `AI_Agent/streamlit_app.py`
- `AI_Agent/README.md`
- `AI_Agent/requirements.txt`
- `AI_Agent/.env.example`

退出标准：

- `AI_Agent/` 目录结构完整
- 所有引用关系能在本地解析

### Phase 2：处理 `.mhtml`

目标：把浏览器保存的网页归档先变成可被 `doc_to_md` 接收的 `.html`

背景：

- 这批 `.mhtml` 是 Blink 保存的 `multipart/related`
- 文件头里已经包含 `Snapshot-Content-Location`、`ArticleTitle`、`PubDate` 等可提取元数据

工作项：

- 新增 `scripts/extract_mhtml_to_html.py`
- 用 Python `email`/`mailbox` 兼容方式解析 MIME
- 提取主 `text/html` part 并解码 quoted-printable 内容
- 只保留正文区域，不保留站点导航、页眉页脚、脚本和样式
- 输出到 `work/mhtml_html/`
- 同时为每个文件产出一个元数据 JSON，保留原始 URL、标题、发布日期、原始文件名

正文提取原则：

- 优先抽取正文容器，而不是保存整页 HTML
- 目标是得到适合法规检索的正文文本，不追求网页视觉还原
- 若页面结构不稳定，则退化为删除导航区后的主体文本提取

退出标准：

- `6` 个 `.mhtml` 全部得到对应 `.html`
- 至少抽检 `2` 个文件，确认正文可读、不是整页 MIME 垃圾

### Phase 3：按格式批量转 Markdown

目标：把三类源文件稳定转成 Markdown 原始稿。

工作项：

- 新增 `scripts/convert_documents.py`
- 调用 `C:\Projects\doc_to_md` 的 CLI 或内部模块
- 分三次执行转换，分别落到 `work/converted_raw/`

转换策略：

- PDF -> `opendataloader`
- HTML -> `html_local`
- XLSX -> `local`

建议环境：

- Python 3.10/3.11 虚拟环境
- `doc_to_md` 安装 `requirements-recommended-pdf.txt`
- 补充 office 依赖以支持 `.xlsx`
- 系统安装 Java 11+

建议兜底策略：

- 若 PDF 个别文件被 `opendataloader` 转换失败，优先对失败样本回退到 `mistral`
- `mistral` 所需 key 直接复用现有参考项目中的配置
- 只有在 `mistral` 也不可用时，再考虑 `docling` 或 `markitdown`
- 若 HTML 提取正文过少，则在清洗阶段保留原始标题和来源元数据，不立刻丢弃

退出标准：

- 所有源文件都有对应的 Markdown 输出或明确失败报告
- 输出数与输入数可对账
- 失败列表单独记录到 `work/conversion_reports/`

### Phase 4：标准化知识库语料

目标：把转换原稿整理成适合索引与展示的 `Knowledge_Base_MarkDown/`

工作项：

- 新增 `scripts/normalize_markdown.py`
- 统一文件命名、目录分类、front matter、资源目录
- 把最终可索引文件写入 `Knowledge_Base_MarkDown/`
- 新增 `scripts/build_manifest.py` 生成清单文件

建议分类：

- `Knowledge_Base_MarkDown/rules/`
- `Knowledge_Base_MarkDown/notices/`
- `Knowledge_Base_MarkDown/attachments/`

建议 front matter：

```yaml
---
title:
category:
source_type:
source_file:
source_url:
publish_date:
converted_engine:
converted_at:
---
```

建议保留规则：

- 文件名保留中文标题，方便监管人员识别
- 配图或提取资产沿用 `document_assets/` 同级目录模式
- 清洗时只修正结构性噪音，不改写监管原文

退出标准：

- `Knowledge_Base_MarkDown/` 可以独立作为最终语料目录使用
- `manifest.json` 能枚举每份资料的来源与转换状态

### Phase 5：接入 AI Chatbot

目标：让最终 Markdown 语料可被检索问答。

工作项：

- 把 `AI_Agent` 的默认 `SOURCE_DIR` 指向 `..\Knowledge_Base_MarkDown`
- 修改 prompt，让系统身份从 IAA AI 知识库切换成“偿付能力监管知识库”
- 默认输出语言改成中文
- 保留标准 RAG 与 agentic RAG 两种模式
- 保留 Streamlit 页面，作为第一阶段默认 UI

需要调整的重点：

- `build_index.py` 里的默认语料目录
- `ask.py` 里的系统提示词、知识库名称、输出语言默认值
- `streamlit_app.py` 里的标题、文案、仓库说明
- 测试中的示例文本可以从 AI 主题改成监管主题，但不必改测试结构

退出标准：

- `python .\scripts\build_index.py --source ..\Knowledge_Base_MarkDown` 可执行
- `python .\scripts\ask.py --language zh "核心偿付能力监管规则有哪些"` 可返回带引用答案
- `streamlit run .\streamlit_app.py` 可启动

### Phase 6：验证与交付

目标：确保这不是“能跑一次”的样板，而是能重复更新的工作流。

工作项：

- 保留并跑通 `AI_Agent/tests/test_smoke.py`
- 若需要，增加一个针对中文法规文件名的 smoke case
- 手工抽查至少 `5` 个问答问题
- 输出一份运行说明

建议验证问题：

- “偿二代二期最低资本相关规则主要有哪些”
- “压力测试相关要求在哪些文件里出现”
- “偿付能力报告样表和正文规则分别在哪里”
- “2023 年优化监管标准通知与 2021 年规则体系是什么关系”

退出标准：

- 索引构建成功
- smoke tests 通过
- 至少 `5` 个核心问题能返回可追溯引用

## 文件计划

预计新增：

- `scripts/extract_mhtml_to_html.py`
- `scripts/convert_documents.py`
- `scripts/normalize_markdown.py`
- `scripts/build_manifest.py`
- `Knowledge_Base_MarkDown/`
- `AI_Agent/`

预计复用并修改：

- `AI_Agent/scripts/build_index.py`
- `AI_Agent/scripts/ask.py`
- `AI_Agent/streamlit_app.py`
- `AI_Agent/README.md`
- `AI_Agent/.env.example`
- `AI_Agent/tests/test_smoke.py`
- `AI_Agent/tests/test_rag_pipeline.py`

## 风险与缓解

### 风险 1：`.mhtml` 提取后正文不干净

缓解：

- 单独做预处理层，不把问题混进 RAG 层
- 优先利用文件头元数据补标题、来源、发布日期
- 预处理目标限定为“正文部分”，不保留整页结构，减少导航和模板噪音

### 风险 2：`opendataloader` 产出图片过多或个别 PDF 失败

缓解：

- 保留 `opendataloader -> mistral` 的失败回退策略
- 资产目录按文件隔离，避免污染最终知识库

### 风险 3：XLSX 转 Markdown 后表格过宽

缓解：

- 第一阶段先保留原始表格文本，不做复杂重排
- 后续如检索效果差，再对样表单独加清洗规则

### 风险 4：语料数量增长后 embedding 成本上升

缓解：

- 先沿用 IAA 的 chunking 方案
- 第二阶段再视索引体积调整 chunk size 与 overlap

## 回滚策略

- 原始资料始终保留在 `source_regulation/`
- 中间产物全部写入 `work/`
- 最终语料与 AI_Agent 分离，任何阶段失败都不会破坏原始资料
- chatbot 层如果不稳定，仍可先只交付 Markdown 知识库

## 推荐实施顺序

1. 先搭 `AI_Agent` 骨架与目录
2. 再做 `.mhtml -> .html`
3. 再跑批量转换
4. 再做 Markdown 标准化
5. 最后接 chatbot、构建索引、跑验证

## 我建议你现在确认的事项

- 确认 1：第一阶段只做本地 CLI + Streamlit，不做 Open WebUI
- 确认 2：沿用 `Knowledge_Base_MarkDown/` 和 `AI_Agent/` 命名，不另起新结构
- 确认 3：`.mhtml` 单独预处理，不直接硬喂给 `doc_to_md`
- 确认 4：文件名保留中文标题，便于业务识别
- 确认 5：PDF 失败样本优先回退到 `mistral`
- 确认 6：`.mhtml` 只提取正文部分

## 实施后的首批验证命令

```powershell
# 1. 预处理 mhtml
python .\scripts\extract_mhtml_to_html.py

# 2. 批量转换
python .\scripts\convert_documents.py

# 3. 构建索引
cd AI_Agent
python .\scripts\build_index.py --source ..\Knowledge_Base_MarkDown

# 4. 运行测试
pytest tests/test_smoke.py tests/test_rag_pipeline.py

# 5. 本地问答
python .\scripts\ask.py --language zh "偿付能力监管规则第2号讲什么"

# 6. 启动 UI
streamlit run .\streamlit_app.py
```

## 下一步

如果你确认这份计划，我下一步就按这个计划开始落第一阶段骨架：

- 建目录
- 迁移最小 `AI_Agent`
- 写 `.mhtml` 预处理脚本
- 再接文档转换流水线
