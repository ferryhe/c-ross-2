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

### `POST /api/engine/plan`

只做问题规划，不直接回答。

返回内容包括：

- `question_type`
- `retrieval_strategy`
- `scoped_queries`
- `recommended_paths`
- `title_hits`
- `summary_hits`

适合用途：

- agent 先规划再执行
- 前端展示“准备如何检索”
- 调试法规问答工作流

### `POST /api/engine/chat`

专业引擎完整回答入口。

在内部会做：

1. 问题分类
2. 标题检索
3. 摘要检索
4. scoped retrieval
5. citation-grounded synthesis

返回内容除了标准回答字段，还包含：

- `engine_mode`
- `question_type`
- `retrieval_strategy`
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

## 当前限制

当前专业引擎还是第一版骨架，已经具备：

- title-first 检索
- summary-first 粗召回
- 问题类型规划
- 与现有 RAG 的集成

但还没有完整实现：

- article / formula / table / threshold 的独立索引层
- 规则、通知、附件之间的关系图
- 变量卡片和公式卡片

这些会在后续阶段继续补齐。
