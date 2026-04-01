import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  ThreadPrimitive,
  useAssistantRuntime,
  useLocalRuntime,
  useThread,
  useThreadRuntime,
  type ChatModelAdapter,
  type ThreadMessage,
} from "@assistant-ui/react";
import { useEffect, useMemo, useRef, useState } from "react";

import { fetchConfig, sendChatRequest } from "./api";
import { MarkdownMessage } from "./markdown";
import type { ChatConfigResponse, ModelMode, SourceItem } from "./types";

const STORAGE_KEY = "cross2-assistant-ui-thread";
const EMPTY_STATE_SUGGESTIONS = [
  "认可资产都包含哪些种类？",
  "偿付能力监管规则第2号主要涉及什么内容？",
  "最低资本由哪些部分构成？",
  "流动性风险监管要求有哪些重点？",
];

function getPlainText(message: ThreadMessage): string {
  return message.content
    .filter((part) => part.type === "text" || part.type === "reasoning")
    .map((part) => ("text" in part ? part.text : ""))
    .join("\n")
    .trim();
}

function getMessageSources(message: ThreadMessage): SourceItem[] {
  const value = message.metadata.custom["sources"];
  if (!Array.isArray(value)) {
    return [];
  }
  return value as SourceItem[];
}

function PersistedThreadBridge() {
  const runtime = useAssistantRuntime();
  const messages = useThread((state) => state.messages);
  const restoredRef = useRef(false);

  useEffect(() => {
    if (restoredRef.current || typeof window === "undefined") {
      return;
    }
    restoredRef.current = true;

    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return;
    }

    try {
      runtime.thread.import(JSON.parse(raw));
    } catch {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  }, [runtime]);

  useEffect(() => {
    if (!restoredRef.current || typeof window === "undefined") {
      return;
    }
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(runtime.thread.export()));
  }, [messages, runtime]);

  return null;
}

function MessageBubble({ message }: { message: ThreadMessage }) {
  const text = getPlainText(message);
  const sources = getMessageSources(message);
  const isUser = message.role === "user";
  const isAssistant = message.role === "assistant";
  const isRunning = isAssistant && message.status.type === "running";

  if (!text && !isRunning) {
    return null;
  }

  return (
    <article className={`message-row ${isUser ? "message-row--user" : "message-row--assistant"}`}>
      <div className={`message-bubble ${isUser ? "message-bubble--user" : "message-bubble--assistant"}`}>
        <div className="message-bubble__meta">{isUser ? "你" : "助手"}</div>
        {isUser ? (
          <p className="message-bubble__plain">{text}</p>
        ) : text ? (
          <MarkdownMessage markdown={text} sources={sources} />
        ) : null}
        {isRunning && !text ? <div className="message-bubble__typing">正在生成回答...</div> : null}
      </div>
    </article>
  );
}

function EmptyState() {
  const threadRuntime = useThreadRuntime();

  return (
    <section className="empty-state">
      <p className="empty-state__eyebrow">中国偿二代问答系统</p>
      <h2 className="empty-state__title">面向偿付能力监管规则的研究型问答</h2>
      <p className="empty-state__description">
        回答会优先基于知识库中的规则、附件和通知生成，并保留可点击的数字引用。
      </p>
      <div className="empty-state__suggestions">
        {EMPTY_STATE_SUGGESTIONS.map((prompt) => (
          <button
            className="suggestion-chip"
            key={prompt}
            onClick={() =>
              threadRuntime.append({
                role: "user",
                content: [{ type: "text", text: prompt }],
                startRun: true,
              })
            }
            type="button"
          >
            {prompt}
          </button>
        ))}
      </div>
    </section>
  );
}

function ChatShell(props: {
  config: ChatConfigResponse | null;
  configError: string | null;
  modelMode: ModelMode;
  setModelMode: (mode: ModelMode) => void;
}) {
  const runtime = useAssistantRuntime();
  const threadRuntime = useThreadRuntime();
  const messages = useThread((state) => state.messages);
  const isRunning = useThread((state) => state.isRunning);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, isRunning]);

  return (
    <div className="app-shell">
      <PersistedThreadBridge />

      <header className="app-header">
        <div>
          <p className="app-header__eyebrow">assistant-ui</p>
          <h1 className="app-header__title">{props.config?.knowledge_base_name ?? "中国偿二代问答系统"}</h1>
        </div>
        <div className="app-header__controls">
          <div className="mode-switch" role="tablist" aria-label="模型模式">
            <button
              className={props.modelMode === "general" ? "mode-switch__button is-active" : "mode-switch__button"}
              onClick={() => props.setModelMode("general")}
              type="button"
            >
              一般
              <span>{props.config?.models.general ?? "gpt-4.1"}</span>
            </button>
            <button
              className={props.modelMode === "reasoning" ? "mode-switch__button is-active" : "mode-switch__button"}
              onClick={() => props.setModelMode("reasoning")}
              type="button"
            >
              推理
              <span>{props.config?.models.reasoning ?? "gpt-5.4-mini"}</span>
            </button>
          </div>

          <button
            className="secondary-button"
            onClick={() => {
              runtime.thread.reset();
              if (typeof window !== "undefined") {
                window.localStorage.removeItem(STORAGE_KEY);
              }
            }}
            type="button"
          >
            新会话
          </button>
        </div>
      </header>

      {props.configError ? <div className="status-banner status-banner--error">{props.configError}</div> : null}

      <ThreadPrimitive.Root className="chat-stage">
        <ThreadPrimitive.Viewport
          autoScroll
          className="chat-stage__viewport"
          scrollToBottomOnInitialize
          scrollToBottomOnRunStart
        >
          {messages.length === 0 ? <EmptyState /> : null}
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          <div ref={bottomRef} />
        </ThreadPrimitive.Viewport>
      </ThreadPrimitive.Root>

      <footer className="composer-shell">
        <ComposerPrimitive.Root className="composer-card">
          <ComposerPrimitive.Input
            className="composer-input"
            minRows={1}
            maxRows={10}
            placeholder="请输入与偿付能力监管规则相关的问题"
          />
          <div className="composer-actions">
            {isRunning ? (
              <button className="secondary-button" onClick={() => threadRuntime.cancelRun()} type="button">
                停止
              </button>
            ) : null}
            <ComposerPrimitive.Send className="primary-button">发送</ComposerPrimitive.Send>
          </div>
        </ComposerPrimitive.Root>
      </footer>
    </div>
  );
}

export default function App() {
  const [config, setConfig] = useState<ChatConfigResponse | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [modelMode, setModelMode] = useState<ModelMode>("general");
  const modelModeRef = useRef<ModelMode>("general");

  useEffect(() => {
    modelModeRef.current = modelMode;
  }, [modelMode]);

  useEffect(() => {
    const controller = new AbortController();
    fetchConfig(controller.signal)
      .then((result) => {
        setConfig(result);
        setModelMode(result.default_model_mode);
      })
      .catch((error: Error) => {
        setConfigError(error.message);
      });

    return () => controller.abort();
  }, []);

  const adapter = useMemo<ChatModelAdapter>(
    () => ({
      async run({ messages, abortSignal }) {
        const response = await sendChatRequest({
          messages,
          modelMode: modelModeRef.current,
          signal: abortSignal,
        });

        return {
          content: [
            {
              type: "text",
              text: response.text,
            },
          ],
          metadata: {
            custom: {
              sources: response.sources,
              model: response.model,
              modelMode: response.model_mode,
              ragMode: response.rag_mode,
            },
          },
        };
      },
    }),
    [],
  );

  const runtime = useLocalRuntime(adapter);

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ChatShell
        config={config}
        configError={configError}
        modelMode={modelMode}
        setModelMode={setModelMode}
      />
    </AssistantRuntimeProvider>
  );
}
