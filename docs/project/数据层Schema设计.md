# 数据层 Schema 设计

目标：把 `Knowledge_Base_MarkDown/` 中的法规 Markdown 加工成同时适配 `chatbot` 和 `AI agent` 的 ready-data 产物。

## 设计原则

1. 数据层优先，问答层次之。
2. 所有产物尽量由 Markdown 确定性生成，避免构建时强依赖在线模型。
3. 产物要同时支持：
   - 文档级定位
   - 摘要级粗召回
   - section/article/formula/table 级证据定位
   - 通知、附件、规则之间的关系扩展
4. 产物既能被当前 chatbot/RAG 消费，也能被 skill 化 agent 直接调用。

## 输出目录

建议默认输出到：

`Knowledge_Base_MarkDown/ready_data/`

## 产物列表

### 1. `doc_catalog.jsonl`

作用：

- 统一文档主索引
- title search / summary search 的基础数据

建议字段：

```json
{
  "doc_id": "rules/保险公司偿付能力监管规则第2号：最低资本.md",
  "path": "Knowledge_Base_MarkDown/rules/保险公司偿付能力监管规则第2号：最低资本.md",
  "title": "保险公司偿付能力监管规则第2号：最低资本",
  "category": "rules",
  "source_type": ".pdf",
  "publish_date": "",
  "aliases": ["规则第2号", "第2号规则", "最低资本规则"],
  "summary_short": "简短摘要",
  "summary_structured": "结构化摘要",
  "headings": ["第一章 总则", "第二章 计量原则"],
  "keywords": ["最低资本", "保险风险", "市场风险"]
}
```

### 2. `title_aliases.jsonl`

作用：

- 标题、编号、别名、口语简称映射

建议字段：

```json
{
  "alias": "规则第2号",
  "normalized_alias": "规则第2号",
  "doc_id": "rules/保险公司偿付能力监管规则第2号：最低资本.md",
  "title": "保险公司偿付能力监管规则第2号：最低资本",
  "category": "rules",
  "alias_type": "rule_number"
}
```

### 3. `doc_summaries.jsonl`

作用：

- 摘要层检索
- “主要内容/概览/适用范围/总结”类问题的首轮候选

建议字段：

```json
{
  "doc_id": "rules/保险公司偿付能力监管规则第2号：最低资本.md",
  "title": "保险公司偿付能力监管规则第2号：最低资本",
  "category": "rules",
  "summary_short": "简短摘要",
  "summary_structured": "结构化摘要",
  "focus_points": ["最低资本构成", "计量原则", "核心公式"],
  "related_doc_ids": ["rules/保险公司偿付能力监管规则第12号：偿付能力风险管理要求与评估.md"]
}
```

### 4. `sections_structured.jsonl`

作用：

- 结构化 section 检索
- article/table/formula/obligation/threshold 等粒度的统一证据层

建议字段：

```json
{
  "section_id": "rules/保险公司偿付能力监管规则第2号：最低资本.md#section-15-1",
  "doc_id": "rules/保险公司偿付能力监管规则第2号：最低资本.md",
  "path": "Knowledge_Base_MarkDown/rules/保险公司偿付能力监管规则第2号：最低资本.md",
  "title": "保险公司偿付能力监管规则第2号：最低资本",
  "heading_path": ["第三章 计量方法"],
  "section_heading": "第三章 计量方法",
  "article_no": "第十五条",
  "section_kind": "semantic",
  "content_type": "formula",
  "text": "原始文本",
  "token_count": 123,
  "has_formula": true,
  "has_table": false,
  "mentions_rules": ["规则第12号"],
  "mentions_attachments": [],
  "keywords": ["最低资本", "相关系数矩阵法"]
}
```

### 5. `formula_cards.jsonl`

作用：

- 公式、变量、上下限、相关系数检索
- 公式解释型问答

建议字段：

```json
{
  "formula_id": "rules/保险公司偿付能力监管规则第2号：最低资本.md#formula-1",
  "doc_id": "rules/保险公司偿付能力监管规则第2号：最低资本.md",
  "title": "保险公司偿付能力监管规则第2号：最低资本",
  "article_no": "第十五条",
  "section_heading": "第三章 计量方法",
  "formula_text": "$$ ... $$",
  "variables": ["MC", "LA", "rho"],
  "variable_hints": ["MC", "LA", "rho"],
  "keywords": ["最低资本", "相关系数矩阵法", "损失吸收效应"]
}
```

### 6. `relations_graph.json`

作用：

- 支持规则、通知、附件之间的扩展检索
- 为 AI agent 提供关系跳转能力

建议结构：

```json
{
  "nodes": [
    {
      "id": "rules/保险公司偿付能力监管规则第2号：最低资本.md",
      "type": "document",
      "title": "保险公司偿付能力监管规则第2号：最低资本",
      "category": "rules"
    }
  ],
  "edges": [
    {
      "source": "rules/保险公司偿付能力监管规则第2号：最低资本.md",
      "target": "rules/保险公司偿付能力监管规则第12号：偿付能力风险管理要求与评估.md",
      "relation": "mentions_rule"
    }
  ]
}
```

### 7. `ready_data_manifest.json`

作用：

- 统计产物规模和构建时间
- 供 consumer 快速自检

建议字段：

- `built_at`
- `source_root`
- `doc_count`
- `summary_count`
- `section_count`
- `formula_count`
- `relation_edge_count`
- `artifact_files`

## 消费方式

### chatbot-ready

- 优先读取 `doc_catalog.jsonl`
- 摘要类问题用 `doc_summaries.jsonl`
- 证据类问题用 `sections_structured.jsonl`

### AI-agent-ready

- 标题定位：`title_aliases.jsonl`
- 规划与候选收缩：`doc_catalog.jsonl` + `doc_summaries.jsonl`
- 细节证据：`sections_structured.jsonl` + `formula_cards.jsonl`
- 关系扩展：`relations_graph.json`

## 下一阶段实施顺序

1. 先生成 `doc_catalog.jsonl`
2. 再生成 `title_aliases.jsonl`
3. 再生成 `doc_summaries.jsonl`
4. 再生成 `sections_structured.jsonl`
5. 再补 `formula_cards.jsonl`
6. 最后补 `relations_graph.json`

## 当前阶段目标

本阶段不追求一次性把“法规知识图谱”做满，而是先把以下能力稳定交付：

- 标题级定位
- 摘要级召回
- section/article/formula/table 粒度切分
- 基础关系扩展

做到这一层，当前 repo 就已经具备了清晰的：

`MD -> chatbot-ready / AI-agent-ready 数据层`

主链路。
