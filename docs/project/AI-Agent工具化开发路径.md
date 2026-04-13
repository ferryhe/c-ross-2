# AI Agent 工具化开发路径

## 目标定位

`c-ross-2` 的最终形态不应优先定义为一个独立前端 chatbot，而应定义为：

`监管 Markdown -> ready_data 结构化数据层 -> CLI 工具 -> skill / agent tools -> 可验证回答`

也就是说，前端只是一个验证和展示 consumer。项目的核心产物是让 AI Agent 知道：当前 Markdown 不是普通文章，而是监管文件；面对这类文件时，要按监管规则、通知、附件、公式、关系和证据引用的方式处理。

这个定位和 Onyx 这类通用企业知识库不同。Onyx 的强项是连接器和通用 RAG 广度；`c-ross-2` 的强项应该是监管知识深度：

- 监管文档结构化
- 公式定位与变量解释
- 规则、通知、附件之间的关系追溯
- 带证据和引用的可验证回答
- 可被 AI Agent 编排调用的 CLI 和 skill

## Agent 处理契约

需要通过 skill 明确告诉 AI Agent：

> 这些 Markdown 是监管文件，不要把它们当作普通长文档自由总结。先识别文件身份，再判断问题类型，然后按标题、摘要、条文、公式、关系和原文证据逐层处理。

最低处理规则如下：

1. 遇到规则编号、附件编号、通知标题时，先用 `doc_catalog.jsonl` 和 `title_aliases.jsonl` 锁定目标文档。
2. 遇到“主要内容、概览、适用范围、附件是什么”时，先读 `doc_summaries.jsonl`，再按需要进入 section。
3. 遇到“第几条、由哪些部分组成、应当如何、按照哪项规则”时，以 `sections_structured.jsonl` 为主要证据。
4. 遇到公式问题时，用 `formula_cards.jsonl` 定位公式，但必须回到对应 section 解释变量、适用条件和上下文。
5. 遇到“通知调整了什么、过渡期影响什么、附件对应哪条规则”时，用 `relations_graph.json` 做导航，再回到 section 或原始 Markdown 确认证据。
6. 关系边和 `related_doc_ids` 只是导航提示，不能直接当作监管结论。
7. 最终回答必须带引用；证据不足时要明确说明不足，而不是补编答案。

## 主要工具构成

### 1. 数据构建工具

目标：把监管 Markdown 加工成稳定的 `ready_data`。

已有基础：

- `AI_Agent/scripts/build_ready_data.py`
- `Knowledge_Base_MarkDown/ready_data/doc_catalog.jsonl`
- `Knowledge_Base_MarkDown/ready_data/title_aliases.jsonl`
- `Knowledge_Base_MarkDown/ready_data/doc_summaries.jsonl`
- `Knowledge_Base_MarkDown/ready_data/sections_structured.jsonl`
- `Knowledge_Base_MarkDown/ready_data/formula_cards.jsonl`
- `Knowledge_Base_MarkDown/ready_data/relations_graph.json`

下一步应该把它包装成稳定 CLI：

```powershell
cross2 build-ready-data --source Knowledge_Base_MarkDown --output Knowledge_Base_MarkDown/ready_data
cross2 inspect-ready-data --root Knowledge_Base_MarkDown/ready_data
cross2 validate-ready-data --root Knowledge_Base_MarkDown/ready_data
```

验收标准：

- 所有产物可重复生成。
- manifest 包含文档数、摘要数、section 数、公式数、关系边数。
- 构建后能抽样检查摘要、公式卡、关系边和 section 质量。

### 2. 检索与定位工具

目标：让 Agent 不再只调用一个黑盒 `ask(question)`，而是能分步定位。

建议 CLI：

```powershell
cross2 search titles --query "规则第2号"
cross2 search summaries --query "规则第2号主要内容是什么"
cross2 search sections --query "最低资本由哪些部分组成" --doc-id "rules/保险公司偿付能力监管规则第2号：最低资本.md"
cross2 search formulas --query "最低资本计算公式" --doc-id "rules/保险公司偿付能力监管规则第2号：最低资本.md"
```

对应 API / 函数能力：

- `search_titles`
- `search_summaries`
- `search_sections`
- `search_formulas`
- `plan_regulatory_query`

当前项目已有 `search_titles / search_summaries / plan_regulatory_query`，下一步重点是补 `search_sections / search_formulas`，并让摘要检索直接使用 `doc_summaries.jsonl` 的 `focus_points` 和 `related_doc_ids`。

验收标准：

- 明确规则号的问题能严格锁定对应 `doc_id`。
- 概览类问题先走摘要层。
- 条文和公式问题能转入结构化 section 和公式卡。

### 3. 公式解释工具

目标：公式不是只被渲染出来，还要能解释变量含义、适用范围和引用条文。

建议 CLI：

```powershell
cross2 explain formula --query "规则第2号最低资本公式"
cross2 explain formula --formula-id "rules/保险公司偿付能力监管规则第2号：最低资本.md#formula-1"
```

工具行为：

1. 从 `formula_cards.jsonl` 定位公式。
2. 找到同文档、同条文或同 section 的 `sections_structured` 记录。
3. 用 section 文本解释变量，而不是只信公式卡里的变量列表。
4. 过滤 LaTeX 技术词，例如 `begin`、`leq`、`times`、`operatorname`。
5. 输出公式、变量含义、适用条件、引用来源。

验收标准：

- `MC`、`LA`、`Stress_t`、`Spread_t` 等真实变量能保留。
- LaTeX 控制词不作为变量进入最终解释。
- 回答中能说明变量来自哪条或哪一段证据。

### 4. 关系追溯工具

目标：把规则、通知、附件之间的关系从“提到了谁”升级为“是什么关系”。

建议 CLI：

```powershell
cross2 trace relations --doc-id "rules/保险公司偿付能力监管规则第2号：最低资本.md"
cross2 trace notices --rule "规则第2号"
cross2 trace adjustments --notice "国家金融监督管理总局关于优化保险公司偿付能力监管标准的通知"
```

关系类型演进：

- 当前基础边：`mentions_rule`、`mentions_attachment`
- 下一步语义边：`adjusts_rule`、`extends_transition`、`clarifies_formula`、`applies_to_rule`、`requires_attachment`、`implements_rule_set`

每条强语义边应尽量带：

- `source`
- `target`
- `relation`
- `label`
- `evidence_section_id`
- `evidence_text_preview`
- `effective_date`
- `confidence`

验收标准：

- 通知影响规则的问题能返回规则清单和证据片段。
- 附件对应规则的问题能追溯到原文说明。
- relation 不能直接替代原文证据，回答前必须确认 section 或 Markdown 内容。

### 5. 可验证回答工具

目标：让 Agent 在生成答案前完成规划、证据收集和引用约束。

建议 CLI：

```powershell
cross2 answer --question "最低资本由哪些部分组成？" --mode verified
cross2 plan --question "规则第2号主要内容是什么"
cross2 evidence --question "控制风险最低资本按照哪一项规则计量？"
```

工具行为：

1. `plan`：判断问题类型、目标文档和检索策略。
2. `evidence`：返回 title、summary、section、formula、relation 的证据集合。
3. `answer`：只基于证据生成带引用回答。

验收标准：

- `answer` 的每个核心结论都能回到证据。
- 无证据时返回“不足以回答”，并推荐最相关 Markdown。
- Agent 可以选择只调用 `plan/evidence`，自己组织最终回答。

### 6. 评测与反馈工具

目标：把“回答不错”变成可回归验证。

建议 CLI：

```powershell
cross2 eval retrieval --cases AI_Agent/eval/cases.jsonl
cross2 eval answers --model gpt-5.4-mini --compare-agentic
cross2 feedback add --question "..." --expected-doc "..." --note "..."
```

评测集应覆盖：

- 规则数量类
- 单规则概览类
- 条文结论类
- 公式解释类
- 阈值类
- 附件定位类
- 通知调整类
- 跨规则关系类

验收标准：

- 至少一组离线检索测试不依赖在线模型。
- 在线模型评测只作为补充，不能替代检索和证据测试。
- 用户纠正过的问题能沉淀为回归 case。

## Skill 设计路径

现有 skill：

- `skills/regulatory-ready-data-builder/SKILL.md`
- `skills/regulatory-markdown-answering/SKILL.md`

建议不要一开始拆太多 skill。先把两个核心 skill 做扎实：

1. `regulatory-ready-data-builder`
   - 负责告诉 Agent 如何重建和检查 ready-data。
   - 重点是稳定产物契约，而不是回答问题。

2. `regulatory-markdown-answering`
   - 负责告诉 Agent 如何回答监管问题。
   - 重点是标题定位、摘要缩圈、section 证据、公式解释、关系追溯和引用。

后续当 CLI 工具稳定后，再按能力拆分轻量 profile：

- `formula_explainer`
- `notification_reviewer`
- `threshold_checker`
- `comparison_engineer`

拆分条件不是“概念上好看”，而是这些 profile 已经有明确 CLI 或 API 工具可以调用。

## 前端定位

当前前端应该独立出来，继续作为干净的展示和验证 consumer。

它已经具备 citation 和数学公式展示能力，这一点很适合作为当前项目的展示层优势保留。它的未来价值不是替代带 skill 的 AI 工具，也不需要承担专业引擎模式切换。

前端侧的原则是：

- 保持当前默认 chatbot 外观和交互。
- 保留已有 citation、来源和公式渲染体验。
- 只消费 API 返回结果，不混入 Markdown 清洗、ready-data 构建、结构化解析或 skill 编排逻辑。
- 不把专业引擎模式开关作为开发任务。
- 不让前端需求反过来决定 CLI、ready-data 和 skill 的设计。

专业引擎能力主要服务 CLI、skill 和 API 调试；如果后续确实需要可视化调试，可以单独做开发页或独立 consumer，而不是作为主前端的必选开关。

因此前端可以作为独立包或独立 consumer 维护。核心工具链仍然是 CLI、ready-data 和 skill；前端只负责把现有回答、citation 和公式展示好，不承接监管 Markdown 处理链路。

## 分阶段开发路径

### Phase 1：冻结 ready-data 契约

目标：

- 明确 `ready_data` 是主产物。
- 让 CLI、skill、professional engine 都围绕它工作。

任务：

- 补充 schema 文档中的必填字段和兼容规则。
- 增加 `validate-ready-data` 检查。
- 修公式变量提取噪声。
- 让摘要检索直接消费 `doc_summaries.jsonl`。

### Phase 2：补 Agent 可调用 CLI

目标：

- 让 AI Agent 可以分步调用工具，而不是只调用黑盒问答。

任务：

- 增加统一 CLI 入口。
- 封装 `build-ready-data`、`search titles`、`search summaries`。
- 新增 `search sections`、`search formulas`。
- 输出 JSON，方便 Agent 消费。

### Phase 3：增强专业引擎工具层

目标：

- 让 `/api/engine/*` 和 CLI 能力保持一致。

任务：

- API 增加 section / formula 检索能力。
- `plan_regulatory_query` 返回更明确的 scope 和证据计划。
- `engine/chat` 先按 plan 收证据，再生成回答。

### Phase 4：关系追溯语义化

目标：

- 从轻量 mentions 图升级到监管语义关系图。

任务：

- 为通知和规则建立 `adjusts_rule`、`extends_transition` 等语义边。
- 每条强语义边带证据位置。
- 增加 relation trace CLI 和 API。

### Phase 5：可验证回答闭环

目标：

- 让回答质量可回归、可追踪、可改进。

任务：

- 固化 `AI_Agent/eval/cases.jsonl`。
- 增加检索质量测试。
- 记录用户反馈和人工修正。
- 把失败 case 映射到 schema、retrieval、prompt 或 relation 的具体问题。

### Phase 6：前端保持现状

目标：

- 前端独立维护，保持当前默认体验，不把前端作为监管 Markdown 处理链路的一部分。

任务：

- 保持当前默认前端状态。
- 保留已有 citation 和公式展示能力。
- 避免把 Markdown 清洗、ready-data 构建、结构化解析或 skill 编排逻辑放进前端。
- 后续 CLI、ready-data 和 skill 的开发不依赖前端改造。

## 最小可交付版本

第一轮最小可交付不需要做完整平台，只需要完成：

1. `cross2 search sections`
2. `cross2 search formulas`
3. `cross2 explain formula`
4. `cross2 plan`
5. `cross2 answer --mode verified`
6. `cross2 eval retrieval`

这 6 个工具跑通后，Agent 就能把监管 Markdown 当成监管文件处理，而不是当成普通文档做泛化 RAG。
