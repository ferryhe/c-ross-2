# assistant-ui 实施方案

## 目标

将当前 `AI_Agent` 的前端交互层从 Streamlit 聊天界面迁移为基于 `assistant-ui` 的 React 聊天界面，同时保留现有 Python 检索问答核心：

- 保留现有 `scripts/ask.py`、`scripts/build_index.py`、索引文件和问答逻辑
- 新增一个 Python API 层，向前端暴露稳定的问答接口
- 新增一个 `assistant-ui` React 前端，替换现有 Streamlit 聊天体验
- 最终通过单一服务端口提供：
  - 静态前端页面
  - `/api/*` 后端接口
  - `/healthz` 健康检查

## 方案选择

### 采用

`assistant-ui LocalRuntime + 自定义 REST API`

原因：

- `LocalRuntime` 是 assistant-ui 官方建议的“最快接入自定义后端”的路径
- 它天然支持对话消息状态、重试、编辑、重新生成和基础会话历史
- 不要求我们重写现有 Python RAG 为流式协议
- 可以先用非流式 API 跑通，再逐步加流式输出

### 不采用

`Assistant Transport`

原因：

- 需要实现状态快照流协议和前端状态转换器
- 对当前项目来说工程复杂度明显更高
- 当前问题核心是 UI 可靠性，不是 agent 状态流编排

## 目录设计

新增目录：

- `AI_Agent/api_server.py`
  - FastAPI 服务入口
- `AI_Agent/frontend/`
  - assistant-ui React 前端源码
- `AI_Agent/frontend/src/`
  - React 页面、运行时、样式、渲染器
- `AI_Agent/frontend/dist/`
  - 前端构建产物，由 FastAPI 静态托管

保留现有目录：

- `AI_Agent/scripts/`
- `AI_Agent/tests/`

## 后端设计

### 1. FastAPI 服务

新增接口：

- `GET /healthz`
  - 返回服务状态、索引是否存在、API key 是否存在
- `GET /api/config`
  - 返回知识库名称、可用模型档位、默认模型档位
- `POST /api/chat`
  - 输入 assistant-ui 前端消息数组
  - 输出问答结果、来源列表、模型信息

### 2. 消息转换

`assistant-ui LocalRuntime` 会把整段会话消息传给后端，后端处理方式：

- 取最后一条 user message 作为当前问题
- 将前序 user/assistant 消息转换为 `history` 字符串
- 调用现有 `run_query(...)`
- 返回：
  - `text`
  - `sources`
  - `model`
  - `mode`

### 3. 引用与来源

后端返回 `sources` 数组：

- `index`
- `path`
- `url`
- `snippet`

前端将回答正文中的 `[1]`、`[2]` 自动改写为可点击链接。

## 前端设计

### 1. 运行时

采用：

- `@assistant-ui/react`
- `useLocalRuntime`

自定义 `ChatModelAdapter`：

- 请求 `POST /api/chat`
- 传入消息数组和当前模型档位
- 获取 JSON 响应
- 返回 assistant-ui 标准消息内容

### 2. UI 结构

页面分为三块：

- 顶部栏
  - 项目标题
  - 模型档位切换：`一般` / `推理`
  - 新会话按钮
- 主聊天区
  - assistant-ui 消息线程
  - 自动滚动
  - 自适应高度
- 右侧来源栏或消息下折叠区
  - 展示本次回答命中的来源和片段

### 3. 消息渲染

回答正文采用 React 原生 DOM 渲染，不再依赖 Streamlit iframe：

- Markdown：`react-markdown`
- 表格：`remark-gfm`
- 公式：`remark-math + rehype-katex`
- 代码块：原生 `<pre><code>`
- 数字引用：前端改写为 GitHub 原文链接

## 会话记忆

第一阶段：

- 由 `LocalRuntime` 负责页面内会话状态
- 当前标签页内连续问答天然保留上下文

第二阶段：

- 加本地持久化
- 使用浏览器 `localStorage` 保存单线程对话
- 页面刷新后自动恢复最近一次会话

本次实施至少完成第一阶段，并优先争取第二阶段。

## 测试策略

### Python

- 为 `api_server.py` 增加 FastAPI 接口测试
- 验证：
  - `/healthz`
  - `/api/config`
  - `/api/chat` 参数和返回结构

### Frontend

- 使用 `vitest` 做基础单元测试
- 验证：
  - 回答正文中的 `[n]` 正确转成超链接
  - markdown + math 渲染入口正常
  - model mode 切换会影响请求体

### 集成

- `npm run build`
- `python -m pytest`
- 启动 FastAPI 后实际请求一次 `/api/chat`

## 迁移步骤

1. 新增 FastAPI 服务与 API schema
2. 复用 `ask.py` 构建问答接口
3. 初始化 React 前端并接入 assistant-ui
4. 实现 markdown / math / citation 渲染
5. 加模型模式切换与来源展示
6. 加本地单线程会话恢复
7. 构建前端并由 FastAPI 托管
8. 本地测试、Codespace 测试、服务重启

## 验收标准

- 页面能稳定显示任何回答，不再出现“回答区空白”
- 长回答不会被裁切或覆盖
- 公式、表格、链接可正常显示
- `[1]`、`[2]` 等引用可直接点击跳 GitHub 原文
- `一般` / `推理` 模式切换有效
- 当前会话具备上下文记忆
- Codespace 服务重启后可访问
