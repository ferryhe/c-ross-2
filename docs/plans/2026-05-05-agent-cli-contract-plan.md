# c-ross-2 接入 md_to_rag/rag_to_agent 迁移计划 Implementation Plan

> **For Hermes/Codex:** Use the project-isolated Codex worker pattern. Read `AGENTS.md` and `.hermes/project-status.md` before each run. Do not commit, push, or open PRs without explicit approval.

**Goal:** 保留法规 ready_data 壁垒，同时减少自带 RAG 底层重复实现。

**Architecture:** Knowledge_Base_MarkDown 仍是领域源；md_to_rag 负责通用 chunks/index；rag_to_agent regulatory adapter 负责法规 ready_data；AI_Agent 逐步成为 consumer。

**Tech Stack:** Project-native stack plus CLI-first JSON/JSONL manifests. Python projects should use Typer/Pydantic where already present; TypeScript projects should preserve pnpm/OpenAPI workflow.

---

## Context

This repository is one module in the broader agent-operated knowledge pipeline:

```text
web_listening -> doc_to_md -> md_to_rag -> rag_to_agent/domain adapters -> ai_interface
```

Current project role: 保险精算法规领域样板，展示法规 Markdown/RAG 如何变成 professional engine。

Current planning scope: 逐步从自带 RAG 基础设施迁移为消费 md_to_rag + rag_to_agent 的领域样板。

## Non-Negotiable Contracts

1. CLI outputs must be machine-readable and stable (`--json` where applicable).
2. Artifacts must be path-portable and manifest-driven.
3. Reruns must be idempotent.
4. Every derived artifact must preserve provenance back to its input.
5. Secrets/API keys must never be written into manifests or committed files.
6. Cross-repo integration happens through files/manifests/tool specs, not hidden imports.

## Proposed Tasks

### Task 1: 盘点现有 ready_data 与索引

**Objective:** 阅读 README、scripts/build_ready_data.py、AI_Agent 索引脚本，列出现有产物和 API。

**Files:**
- Modify/Create project-specific files identified during the task.
- Update tests or fixtures for the changed contract.

**Steps:**
1. Inspect the current implementation and write down exact files touched.
2. Add or update the smallest contract/test fixture first.
3. Implement the minimal change.
4. Run the focused verification command.
5. Update `.hermes/project-status.md` with result and next action.

**Verification:** 运行现有 tests/ 或最小 ready_data build。

### Task 2: 定义 domain_profile.yaml

**Objective:** 新增 docs/plans 或 config 示例，描述 regulatory_zh chunk/profile/enrichers。

**Files:**
- Modify/Create project-specific files identified during the task.
- Update tests or fixtures for the changed contract.

**Steps:**
1. Inspect the current implementation and write down exact files touched.
2. Add or update the smallest contract/test fixture first.
3. Implement the minimal change.
4. Run the focused verification command.
5. Update `.hermes/project-status.md` with result and next action.

**Verification:** 不改变运行时，仅文档和 fixture。

### Task 3: 准备 md_to_rag 输入 fixture

**Objective:** 选 3-5 个法规 Markdown 文件作为小样本，用于 md_to_rag build smoke。

**Files:**
- Modify/Create project-specific files identified during the task.
- Update tests or fixtures for the changed contract.

**Steps:**
1. Inspect the current implementation and write down exact files touched.
2. Add or update the smallest contract/test fixture first.
3. Implement the minimal change.
4. Run the focused verification command.
5. Update `.hermes/project-status.md` with result and next action.

**Verification:** 记录 expected doc/chunk/formula counts。

### Task 4: 替换索引构建入口

**Objective:** 新增实验脚本调用 md-to-rag build，生成 rag_artifacts，不删除旧 FAISS。

**Files:**
- Modify/Create project-specific files identified during the task.
- Update tests or fixtures for the changed contract.

**Steps:**
1. Inspect the current implementation and write down exact files touched.
2. Add or update the smallest contract/test fixture first.
3. Implement the minimal change.
4. Run the focused verification command.
5. Update `.hermes/project-status.md` with result and next action.

**Verification:** 测试旧 chatbot 仍可运行。

### Task 5: 接 rag_to_agent ready_data

**Objective:** 让 build_ready_data 可读 rag_manifest 或由 rag_to_agent adapter 生成等价 ready_data。

**Files:**
- Modify/Create project-specific files identified during the task.
- Update tests or fixtures for the changed contract.

**Steps:**
1. Inspect the current implementation and write down exact files touched.
2. Add or update the smallest contract/test fixture first.
3. Implement the minimal change.
4. Run the focused verification command.
5. Update `.hermes/project-status.md` with result and next action.

**Verification:** 对比 JSONL 字段与数量。

### Task 6: professional engine adapter

**Objective:** 让 /api/engine/search/chat 逐步消费 rag_to_agent toolspec。

**Files:**
- Modify/Create project-specific files identified during the task.
- Update tests or fixtures for the changed contract.

**Steps:**
1. Inspect the current implementation and write down exact files touched.
2. Add or update the smallest contract/test fixture first.
3. Implement the minimal change.
4. Run the focused verification command.
5. Update `.hermes/project-status.md` with result and next action.

**Verification:** 浏览器/API smoke 确认可回答法规问题。


---

## Acceptance Criteria

- A Codex worker can understand this repo's boundary from `AGENTS.md`.
- A future implementation branch can start from this plan without needing cross-chat context.
- The module's input/output contract is explicit enough for the next module in the chain.
- All new behavior is testable through CLI commands and fixture manifests.

## Recommended First PR

Start with documentation/contracts and fixture-only changes. Do not implement all runtime behavior in the first PR. The first PR should make the intended contract reviewable before code follows.
