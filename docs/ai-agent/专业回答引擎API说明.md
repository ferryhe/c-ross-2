# 专业回答引擎 API 说明

本文说明新增的法规专业回答引擎接口，以及它与现有 chatbot 接口的关系。

## 双模式

当前服务保留两种模式：

- `chatbot mode`
  - 接口：`/api/chat`
  - 作用：保持当前独立聊天机器人行为不变
- `professional engine mode`
  - 接口：`/api/engine/*`
  - 作用：为法规型问答、外部 agent、skills、工作流编排提供更可控的入口

## 接口列表

### `GET /api/engine/config`

返回专业引擎能力摘要。

典型用途：

- 前端决定是否展示专业模式
- 外部 agent 探测引擎能力

### `POST /api/engine/search/titles`

根据标题、规则编号、附件编号、别名做候选文档定位。

请求：

```json
{
  "query": "规则第2号",
  "limit": 5
}
```

适合问题：

- `规则第2号是哪份文件`
- `附件4是什么`
- `关于优化监管标准的通知`

### `POST /api/engine/search/summaries`

根据摘要层做文档级粗召回。

请求：

```json
{
  "query": "规则第2号主要内容是什么",
  "limit": 5
}
```

适合问题：

- `主要内容`
- `概览`
- `适用范围`
- `对比前先找相关文档`

### `POST /api/engine/search/sections`

根据 `sections_structured.jsonl` 做 section/article/table/threshold/formula-adjacent 证据检索。

请求：

```json
{
  "query": "最低资本由哪些部分组成？",
  "docId": "rules/保险公司偿付能力监管规则第2号：最低资本.md",
  "limit": 5
}
```

### `POST /api/engine/search/formulas`

根据 `formula_cards.jsonl` 定位公式卡，并返回过滤 LaTeX 控制词后的变量列表。

请求：

```json
{
  "query": "规则第2号最低资本公式",
  "docId": "rules/保险公司偿付能力监管规则第2号：最低资本.md",
  "limit": 5
}
```

### `POST /api/engine/explain/formula`

用公式卡定位公式，再回到匹配 section 解释变量和适用上下文。

请求：

```json
{
  "formulaId": "rules/保险公司偿付能力监管规则第2号：最低资本.md#formula-1"
}
```

### `POST /api/engine/trace/relations`

根据 `relations_graph.json` 追溯规则、通知、附件之间的导航关系。关系边只是导航提示，回答前仍应回到 section 或 Markdown 原文确认。

请求：

```json
{
  "docId": "rules/保险公司偿付能力监管规则第2号：最低资本.md",
  "direction": "both",
  "limit": 20
}
```

### `POST /api/engine/plan`

只做问题规划，不直接回答。

返回内容包括：

- `question_type`
- `retrieval_strategy`
- `evidence_plan`
- `scoped_queries`
- `recommended_paths`
- `title_hits`
- `summary_hits`

适合用途：

- agent 先规划再执行
- 前端展示“准备如何检索”
- 调试法规问答工作流

### `POST /api/engine/evidence`

只收集证据，不生成最终自然语言答案。返回 `summary / section / formula / relation` 四类证据集合。

### `POST /api/engine/answer`

基于 ready-data 做确定性 verified answer。它不调用在线模型，适合在 agent 自己组织最终回答前做证据闭环检查。

### `POST /api/engine/chat`

专业引擎完整回答入口。

在内部会做：

1. 问题分类
2. 标题检索
3. 摘要检索
4. section / formula / relation 证据收集
5. scoped retrieval
6. citation-grounded synthesis

返回内容除了标准回答字段，还包含：

- `engine_mode`
- `question_type`
- `retrieval_strategy`
- `evidence_plan`
- `scoped_queries`
- `recommended_paths`
- `title_hits`
- `summary_hits`

## 与现有 `/api/chat` 的关系

`/api/chat` 不被替代。

设计原则是：

- 旧接口继续提供当前 chatbot 能力
- 新接口为专业法规引擎和 skill/agent 场景服务
- 两者共用底层知识库和引用式回答能力

## 当前能力

当前专业引擎已经具备：

- title-first 检索
- 直接消费 `doc_summaries.jsonl` 的 summary-first 粗召回
- section / formula 检索
- 公式解释和变量噪声过滤
- relation trace 导航
- 问题类型规划
- evidence 收集
- 离线 retrieval eval
- 与现有 RAG 的集成

仍需注意：

- relation 边不能直接替代原文证据。
- `/api/engine/chat` 的最终自然语言合成仍依赖已配置的在线模型和向量索引。
- `/api/engine/answer` 是确定性 verified answer，适合做证据闭环，不替代人工法规判断。
