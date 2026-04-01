import type { ThreadMessage } from "@assistant-ui/react";

import type { ChatConfigResponse, ChatResponse, ModelMode } from "./types";

export async function fetchConfig(signal?: AbortSignal): Promise<ChatConfigResponse> {
  const response = await fetch("/api/config", {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
    signal,
  });

  if (!response.ok) {
    throw new Error(`Failed to load config: ${response.status}`);
  }

  return (await response.json()) as ChatConfigResponse;
}

export async function sendChatRequest(options: {
  messages: readonly ThreadMessage[];
  modelMode: ModelMode;
  signal: AbortSignal;
}): Promise<ChatResponse> {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      messages: options.messages,
      modelMode: options.modelMode,
      language: "zh",
      ragMode: "agentic",
    }),
    signal: options.signal,
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail || `Chat request failed: ${response.status}`);
  }

  return (await response.json()) as ChatResponse;
}
